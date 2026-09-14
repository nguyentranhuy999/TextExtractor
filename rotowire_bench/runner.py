from __future__ import annotations

import contextlib
import fcntl
import importlib.metadata
import os
import platform
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from .config import ARMS
from .data import prepared
from .evaluation import ALIASES_PATH
from .models.codex_gpt55_adapter import CodexGPT55Adapter, PROMPTS, build_request
from .pipelines import execute
from .schemas import known_schema, ProposedExtractionSchema
from .utils import digest, read_json, utc_now, write_json, write_jsonl

ROOT = Path(__file__).parent


def source_hashes():
    return {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(ROOT.rglob("*")) if p.suffix in (".py",".txt",".json")}


def environment(config):
    versions = {}
    for name in ("rotowire-bench", "gliner2", "gliner", "torch", "transformers", "openai", "pydantic", "PyYAML", "tokenizers", "huggingface-hub", "numpy"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    def system(cmd):
        try:
            return subprocess.check_output(cmd,stderr=subprocess.DEVNULL,text=True).strip()
        except (OSError,subprocess.CalledProcessError):
            return None
    return dict(utc=utc_now(),python=sys.version,platform=platform.platform(),machine=platform.machine(),cpu=system(["sysctl","-n","machdep.cpu.brand_string"]) or platform.processor(),
        logical_cpus=os.cpu_count(),ram_bytes=os.sysconf("SC_PAGE_SIZE")*os.sysconf("SC_PHYS_PAGES"),
        cpu_threads=config["gliner"]["cpu_threads"],versions=versions,pythonhashseed=os.environ.get("PYTHONHASHSEED"),
        git_commit=system(["git","rev-parse","HEAD"]),execution_mode=config["gpt"]["execution_mode"],codex_cli_version=config["gpt"].get("codex_cli_version"),service_tier="Codex default; internal server timings unknown")


def protocol(config,manifest,split,ids,env):
    return dict(protocol_version=2,config=config,source_sha256=source_hashes(),manifest_sha256=digest(manifest),
        split=split,sample_ids=ids,prompt_sha256={k:digest(v) for k,v in PROMPTS.items()},
        aliases_sha256=digest(ALIASES_PATH.read_bytes()),library_versions=env["versions"],python=sys.version,
        pythonhashseed=env["pythonhashseed"],git_commit=env["git_commit"],
        normalization="NFC + casefold + whitespace; scoped fixed aliases; Decimal; percent never rescaled; unique identity abbreviation in scorer only",
        timing="perf_counter_ns; serial Latin square; stage times disjoint except e2e; loading/warmup excluded",
        alias_reproducibility_warning=config["gpt"]["model"] == "gpt-5.5")


def schedule(ids,seed=44):
    order = list(ids)
    random.Random(seed).shuffle(order)
    return [(sid,arm) for i,sid in enumerate(order) for arm in ARMS[i%4:]+ARMS[:i%4]]


def preflight(config, path, *, load_models=False, local_files_only=False, max_requests=None, deadline=None):
    report = dict(utc=utc_now(),environment=environment(config),gliner=dict(status="not_loaded"))
    gliner = None
    if config["gpt"]["execution_mode"] == "codex_ui_import":
        from .external_tasks import ExternalAdapter
        gpt = ExternalAdapter(Path(path).parent/"external_answers")
        report["gpt"] = dict(status="pending_external",execution_mode="codex_ui_import")
    else:
        gpt = CodexGPT55Adapter(config["gpt"],max_requests=max_requests)
        gpt.deadline = deadline
        report["gpt"] = gpt.inspect() if load_models else dict(status="not_verified",reason="Offline validation does not invoke Codex")
    if load_models:
        try:
            from .models.gliner2_adapter import GLiNER2Adapter
            gliner = GLiNER2Adapter(config["gliner"],local_files_only=local_files_only)
            report["gliner"] = dict(status="ready",**gliner.metadata)
        except Exception as exc:
            report["gliner"] = dict(status="blocked",reason=f"{type(exc).__name__}: {exc}")
        if config["gpt"]["execution_mode"] == "codex_cli" and not gpt.blocked_reason:
            entries = []
            def emit(kind,data):
                entries.append(dict(kind=kind,**data))
                write_json(Path(path).parent/"preflight_codex_events.json",entries)
            try:
                payload = build_request(config["gpt"],"schema","A basketball game report contains no numerical facts.")
                parsed = ProposedExtractionSchema.model_validate_json(gpt.request(payload,emit))
                report["gpt"] = dict(**gpt.metadata,probe_schema=parsed.model_dump(),audit=gpt.last_audit)
                report["gpt"]["status"] = "ready"
            except Exception as exc:
                report["gpt"] = dict(status="blocked",reason=f"{type(exc).__name__}: {exc}")
                gpt.blocked_reason = report["gpt"]["reason"]
    write_json(path,report)
    return report,gliner,gpt


@contextlib.contextmanager
def campaign_mutex(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with Path(path).open("a") as f:
        try:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another runner holds this campaign lock") from exc
        try:
            yield
        finally:
            fcntl.flock(f,fcntl.LOCK_UN)


def dry_run(config):
    inputs,_,manifest = prepared(config)
    result = dict(status="dry_run",simulated=False,model_requests=0,n_samples=len(inputs),n_jobs=len(inputs)*4,
                  expected_codex_tasks=len(inputs)*3,gliner_document_jobs=len(inputs)*2,
                  manifest_sha256=digest(manifest),execution_mode=config["gpt"]["execution_mode"],
                  note="Không suy luận; số đoạn GLiNER2 phụ thuộc schema và giới hạn checkpoint.")
    write_json(Path(config["dataset"]["prepared_dir"])/"dry_run.json",result)
    return result


def run(config, *, run_id=None, resume=False, split="test", limit=None, max_requests=None, local_files_only=False, max_seconds=None):
    inputs,gold,manifest = prepared(config,split)
    if limit is not None:
        if split != "validation" or limit < 1 or limit > len(inputs):
            raise ValueError("Only validation pilot accepts limit (1..30)")
        inputs = inputs[:limit]
    if run_id is None and resume:
        candidates = []
        for p in Path(config["run"]["output_root"]).glob("*/protocol.lock.json"):
            frozen = read_json(p)
            if frozen["split"] == split and frozen["config"] == config:
                env_path = p.parent/"environment.json"
                created = read_json(env_path)["utc"] if env_path.exists() else ""
                candidates.append((created,p.parent.name))
        if not candidates:
            raise ValueError("No compatible campaign to resume; supply an existing --run-id or start a new run")
        run_id = max(candidates)[1]
    run_id = run_id or ("pilot-" if split == "validation" else "run-")+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
    if not all(c.isalnum() or c in "-_" for c in run_id):
        raise ValueError("Unsafe run_id")
    dest = Path(config["run"]["output_root"])/run_id
    if dest.exists() and not resume:
        raise ValueError("Existing run_id; use --resume or choose a new run_id")
    dest.mkdir(parents=True,exist_ok=True)
    with campaign_mutex(dest/".runner.lock"):
        return _run(config,dest,inputs,gold,manifest,split,max_requests,local_files_only,max_seconds)


def _run(config,dest,inputs,gold,manifest,split,max_requests,local_files_only,max_seconds=None):
    deadline = time.monotonic()+max_seconds if max_seconds is not None else None
    env = environment(config)
    ids = [i.sample_id for i in inputs]
    lock = protocol(config,manifest,split,ids,env)
    lock_path = dest/"protocol.lock.json"
    if lock_path.exists() and read_json(lock_path) != lock:
        raise ValueError("Protocol/code/environment changed; create a new run_id")
    write_json(lock_path,lock)
    write_json(dest/"environment.json",env) if not (dest/"environment.json").exists() else None
    write_json(dest/"sample_manifest.json",manifest)
    write_jsonl(dest/"inputs.jsonl",[i.model_dump() for i in inputs])
    write_jsonl(dest/"evaluation_gold.jsonl",[gold[sid].model_dump() for sid in ids])
    from .snippets import select_snippet
    write_jsonl(dest/"snippets.jsonl",[dict(sample_id=i.sample_id,**select_snippet(i).to_dict()) for i in inputs])
    write_json(dest/"manual_review.json",dict(ids=[sid for sid in manifest["manual_review_ids"] if sid in ids],status="pending",categories=["schema","snippet_missing_field","wrong_entity","wrong_value","wrong_time_scope","suspected_gold_error"])) if not (dest/"manual_review.json").exists() else None
    order = schedule(ids,config["run"]["order_seed"])
    write_json(dest/"schedule.json",order)
    prior_started = list((dest/"events").glob("*/request_started-*.json"))
    previous_probe = read_json(dest/"preflight_codex_events.json") if (dest/"preflight_codex_events.json").exists() else []
    archived_probes = [e for p in dest.glob("preflight_codex_events_archive_*.json") for e in read_json(p)]
    probe_used = sum(e["kind"] == "request_started" for e in previous_probe+archived_probes)
    remaining_budget = None if max_requests is None else max(0,max_requests-len(prior_started)-probe_used)
    if previous_probe:
        write_json(dest/f"preflight_codex_events_archive_{len(list(dest.glob('preflight_codex_events_archive_*.json')))}.json",previous_probe)
    report,gliner,gpt = preflight(config,dest/"preflight.json",load_models=True,local_files_only=local_files_only,max_requests=remaining_budget,deadline=deadline)
    (dest/"results").mkdir(exist_ok=True)
    gpt.requests_used += len(prior_started)+probe_used
    gpt.max_requests = max_requests
    item_map = {i.sample_id:i for i in inputs}
    started = time.perf_counter_ns()
    session_utc = utc_now()
    stopped = False
    for sid,arm in order:
        if deadline is not None and time.monotonic() >= deadline:
            stopped = True
            break
        key = f"{sid}__{arm}"
        path = dest/"results"/f"{key}.json"
        # Blocked jobs may become runnable; attempted results are immutable.
        if path.exists() and read_json(path)["status"] not in ("blocked", "pending_external"):
            cached = read_json(path)
            if cached.get("protocol_sha256") and cached["protocol_sha256"] != digest(lock):
                raise ValueError("Cached result protocol hash differs")
            continue
        event_dir = dest/"events"/key
        event_dir.mkdir(parents=True,exist_ok=True)
        existing_events = list(event_dir.glob("request_started-*.json")) + list(event_dir.glob("gliner_chunk-*.json"))
        if existing_events:
            # Do not silently repeat a billed/measured request after process death.
            write_json(path,dict(run_id=dest.name,sample_id=sid,arm=arm,status="incomplete",attempted=True,simulated=False,protocol_sha256=digest(lock),
                cache_key=digest([sid,arm,lock]),text_sha256=digest(item_map[sid].full_text),schema=None,output={"tables":[]},normalized=None,
                timings={"latency_e2e_ms":None},errors=["Interrupted before document checkpoint; attempt logs preserved. New run_id required for remeasurement."],n_codex_attempts=len(list(event_dir.glob("request_started-*.json")))))
            continue
        def emit(kind,data):
            if kind in ("request_started","attempt"):
                suffix = f"{data['request_sha256'][:16]}-{data['attempt']}"
            elif kind == "gliner_chunk":
                suffix = str(data["index"])
            else:
                suffix = "0"
            write_json(event_dir/f"{kind}-{suffix}.json",dict(sample_id=sid,arm=arm,**data))
            if kind == "predicted_schema":
                write_json(dest/"predicted_schemas"/f"{key}.json",data)
        result = execute(item_map[sid],arm,config,gliner,gpt,emit,
                         known_schema_factory=(lambda:known_schema(gold[sid])) if arm.startswith("A_") else None)
        result.update(run_id=dest.name,cache_key=digest([sid,arm,lock,result["schema_sha256"]]),protocol_sha256=digest(lock),
                      model_versions={"gliner":config["gliner"],"gpt":config["gpt"]},prompt_sha256=lock["prompt_sha256"],evidence_path=str(event_dir.relative_to(dest)))
        write_json(path,result)
        print(f"{sid} {arm}: {result['status']}",flush=True)
        if max_requests is not None and gpt.requests_used >= max_requests:
            stopped = True
            break
    attempts = []
    for path in sorted((dest/"events").glob("*/attempt-*.json")):
        attempts.append(read_json(path))
    write_jsonl(dest/"codex_attempts.jsonl",attempts)
    # A checkpoint always has an explicit status for every scheduled job, even after
    # an operator budget stops the run. These placeholders are eligible for resume.
    for sid,arm in order:
        path = dest/"results"/f"{sid}__{arm}.json"
        if not path.exists():
            write_json(path,dict(run_id=dest.name,sample_id=sid,arm=arm,status="blocked",attempted=False,simulated=False,
                protocol_sha256=digest(lock),execution_mode="local" if arm == ARMS[0] else config["gpt"]["execution_mode"],
                text_sha256=digest(item_map[sid].full_text),schema=None,output={"tables":[]},normalized=None,
                timings={"latency_e2e_ms":None},errors=["Campaign budget/checkpoint; task not launched"],n_codex_attempts=0,n_forward_passes=0))
    results = [read_json(p) for p in (dest/"results").glob("*.json")]
    state_path = dest/"campaign.json"
    sessions = read_json(state_path).get("sessions",[]) if state_path.exists() else []
    sessions.append(dict(started_at=session_utc,finished_at=utc_now(),execution_ms=(time.perf_counter_ns()-started)/1e6,
                         setup_gliner_load_ms=gliner.load_ms if gliner else None,setup_gliner_warmup_ms=gliner.warmup_ms if gliner else None))
    state = dict(run_id=dest.name,split=split,n_expected=len(order),n_attempted=sum(r["attempted"] for r in results),
                 n_blocked=sum(r["status"] == "blocked" for r in results),complete=sum(r["attempted"] for r in results)==len(order),
                 operator_budget_reached=stopped,request_budget_reached=max_requests is not None and gpt.requests_used >= max_requests,
                 sessions=sessions,remaining=[dict(sample_id=sid,arm=arm) for sid,arm in order if not (dest/"results"/f"{sid}__{arm}.json").exists() or read_json(dest/"results"/f"{sid}__{arm}.json")["status"] in ("blocked", "pending_external")])
    write_json(state_path,state)
    return dict(run_dir=str(dest),**state)
