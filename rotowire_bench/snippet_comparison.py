"""Paired validation ablation: source position changes, word budget stays fixed."""
from __future__ import annotations

from functools import partial
from pathlib import Path
import random
import time
import zipfile

from .data import prepared
from .evaluation import paired_bootstrap, quantile
from .hybrid_validation import report_validation
from .pipelines import SUCCESS, execute
from .reporting import write_csv
from .runner import campaign_mutex, environment, preflight, source_hashes
from .snippets import select_experiment_snippet
from .utils import atomic_write, digest, read_json, utc_now, write_json, write_jsonl

STRATEGIES = ("center_contiguous", "head_middle_tail")
RULES = dict(budget="B=min(80,N//10), whitespace words",
    center="one middle range, identical to main protocol",
    distributed="q,r=divmod(B,3); lengths=[q+(r==2),q+(r>=1),q]; head at 0, middle at (N-length)//2, tail at N-length",
    small_budget="B<3 falls back to the original middle range; B<1 insufficient_fragment",
    separator="two newlines; no inserted words; preserve each range verbatim",
    main_protocol_changed=False, selection_uses_gold=False)


def schedule(ids, seed=44):
    order = list(ids)
    random.Random(seed).shuffle(order)
    return [(sid, variant) for i, sid in enumerate(order)
            for variant in (STRATEGIES if i % 2 == 0 else STRATEGIES[::-1])]


def run_comparison(config, out, *, resume=False, max_pairs=30):
    if not 1 <= max_pairs <= 30 or config["gpt"]["execution_mode"] != "codex_cli":
        raise ValueError("Requires Codex CLI and max-pairs between 1 and 30")
    dest = Path(out)
    if dest.exists() and not resume:
        raise ValueError("Output exists; use a new directory or --resume")
    dest.mkdir(parents=True, exist_ok=True)
    with campaign_mutex(dest / ".runner.lock"):
        return _run(config, dest, resume=resume, max_pairs=max_pairs)


def _run(config, dest, *, resume, max_pairs):
    inputs, gold, manifest = prepared(config, "validation")
    ids = [i.sample_id for i in inputs]
    if len(ids) != 30 or len(set(ids)) != 30:
        raise ValueError("Requires the 30 frozen validation IDs")
    lock = dict(kind="paired_snippet_validation", split="validation", sample_ids=ids,
        config=config, source_sha256=source_hashes(), manifest_sha256=digest(manifest),
        strategies=list(STRATEGIES), rules=RULES, environment=environment(config),
        timing="Shuffled documents, alternating paired strategy order; serial inference; setup excluded")
    if resume:
        old = read_json(dest / "protocol.lock.json")
        for k in ("kind", "split", "sample_ids", "config", "source_sha256", "manifest_sha256", "strategies", "rules"):
            if old[k] != lock[k]:
                raise ValueError(f"Resume mismatch: {k}")
        lock = old
    else:
        write_json(dest / "protocol.lock.json", lock)
        with zipfile.ZipFile(dest / "source_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name in lock["source_sha256"]:
                archive.write(Path(__file__).parent / name, "rotowire_bench/" + name)
    for strategy in STRATEGIES:
        child = dest / strategy
        child_lock = dict(kind="hybrid_validation", split="validation", sample_ids=ids,
            config=config, source_sha256=lock["source_sha256"], manifest_sha256=digest(manifest),
            environment=lock["environment"], arm="B_HYBRID_SHORT", snippet_strategy=strategy,
            parent_protocol_sha256=digest(lock), timing=lock["timing"])
        if resume:
            if read_json(child / "protocol.lock.json") != child_lock:
                raise ValueError("Child protocol changed")
        else:
            write_json(child / "protocol.lock.json", child_lock)
            write_json(child / "sample_manifest.json", manifest)
            write_jsonl(child / "inputs.jsonl", [i.model_dump() for i in inputs])
            write_jsonl(child / "evaluation_gold.jsonl", [gold[s].model_dump() for s in ids])
            write_jsonl(child / "snippets.jsonl", [dict(sample_id=i.sample_id,
                **select_experiment_snippet(i, strategy=strategy).to_dict()) for i in inputs])
    order = schedule(ids, config["run"]["order_seed"])
    write_json(dest / "schedule.json", order)
    pending = [(sid, s) for sid, s in order[:2*max_pairs]
               if not (dest/s/"results"/f"{sid}.json").exists()
               or not read_json(dest/s/"results"/f"{sid}.json")["attempted"]]
    if pending:
        setup_dir = dest / "setup" / str(len(list((dest / "setup").glob("*"))))
        setup, model, gpt = preflight(config, setup_dir / "preflight.json", load_models=True, local_files_only=True)
        if setup["gpt"]["status"] != "ready" or model is None:
            write_json(dest / "blocked.json", setup)
            raise ValueError(f"Preflight blocked; see {setup_dir}/preflight.json")
        started = time.perf_counter_ns()
        items = {i.sample_id: i for i in inputs}
        for sid, strategy in pending:
            child = dest / strategy
            event_dir = child / "events" / sid
            if event_dir.exists() and any(event_dir.iterdir()):
                raise ValueError("Interrupted task has events; do not silently retry, use a new run")
            def emit(kind, data):
                suffix = (f"{data['request_sha256'][:16]}-{data['attempt']}" if kind in ("request_started", "attempt")
                          else str(data["index"]) if kind == "gliner_chunk" else "0")
                write_json(event_dir / f"{kind}-{suffix}.json", data)
            result = execute(items[sid], "B_HYBRID_SHORT", config, model, gpt, emit,
                             snippet_selector=partial(select_experiment_snippet, strategy=strategy))
            result["protocol_sha256"] = digest(read_json(child / "protocol.lock.json"))
            write_json(child / "results" / f"{sid}.json", result)
            print(f"{sid} {strategy}: {result['status']}; GPT={result['n_codex_attempts']}; "
                  f"forwards={result['n_forward_passes']}", flush=True)
            if gpt.blocked_reason:
                break
        write_json(setup_dir / "execution.json", dict(finished_at=utc_now(),
            execution_ms=(time.perf_counter_ns()-started)/1e6))
    return report_comparison(dest)


def coverage_bootstrap(left, right, *, repetitions=2000, seed=2026):
    ids = sorted(left)
    if set(ids) != set(right) or not ids:
        raise ValueError("Coverage comparison requires identical nonempty IDs")
    def fraction(rows, members):
        denominator = sum(rows[s]["gold_fact_count"] for s in members)
        return sum(rows[s]["gold_facts_with_declared_field"] for s in members)/denominator if denominator else 1.0
    rng = random.Random(seed)
    differences = []
    for _ in range(repetitions):
        sample = rng.choices(ids, k=len(ids))
        differences.append(fraction(left, sample)-fraction(right, sample))
    return dict(difference=fraction(left, ids)-fraction(right, ids),
        ci95=[quantile(differences, .025), quantile(differences, .975)],
        seed=seed, repetitions=repetitions, resampling="document")


def report_comparison(out):
    dest = Path(out)
    lock = read_json(dest / "protocol.lock.json")
    summaries, details, coverages, times = {}, {}, {}, {}
    for strategy in lock["strategies"]:
        child = dest / strategy
        child_lock = read_json(child / "protocol.lock.json")
        if (child_lock["parent_protocol_sha256"] != digest(lock)
            or child_lock["sample_ids"] != lock["sample_ids"] or child_lock["snippet_strategy"] != strategy
            or child_lock["config"] != lock["config"] or child_lock["source_sha256"] != lock["source_sha256"]):
            raise ValueError("Child protocol differs from parent")
        summaries[strategy] = report_validation(child)
        details[strategy] = read_json(child / "scores_per_sample.json")
        coverages[strategy] = read_json(child / "schema_coverage.json")
        rows = [read_json(p) for p in (child / "results").glob("*.json")]
        times[strategy] = {r["sample_id"]: r["timings"]["latency_e2e_ms"] for r in rows if r["status"] in SUCCESS}
    complete = all(s["complete"] for s in summaries.values())
    comparison = None
    if complete:
        base, alternate = STRATEGIES
        params = dict(seed=lock["config"]["evaluation"]["bootstrap_seed"],
                      repetitions=lock["config"]["evaluation"]["bootstrap_repetitions"])
        comparison = dict(left=alternate, right=base, **paired_bootstrap(
            details[alternate], details[base], times[alternate], times[base], **params),
            gold_fact_schema_coverage=coverage_bootstrap(coverages[alternate], coverages[base], **params))
    auxiliary = [read_json(p) for p in (dest / "setup").glob("*/preflight_codex_events.json")]
    result = dict(complete=complete, n_expected=60, n_attempted=sum(s["n_attempted"] for s in summaries.values()),
        n_codex_attempts=sum(s["n_codex_attempts"] for s in summaries.values()),
        n_auxiliary_codex_attempts=sum(e["kind"] == "request_started" for entries in auxiliary for e in entries),
        summary=summaries, comparison=comparison, supplementary_not_main_protocol=True)
    write_json(dest / "metrics.json", result)
    flat = [dict(strategy=k, schema_valid=v["n_schema_valid"], schema_nonempty=v["n_schema_nonempty"],
        **v["facts"], schema_field_recall=v["proposed_fields"]["recall"],
        schema_gold_fact_coverage=v["gold_facts_with_declared_field"]/v["gold_fact_count"] if v["gold_fact_count"] else None,
        all_mean_ms=v["all_mean_ms"], success_mean_ms=v["success_mean_ms"], n_forward_passes=v["n_forward_passes"])
        for k, v in summaries.items()]
    write_csv(dest / "summary.csv", flat)
    lines = ["# So sánh đoạn giữa với đầu–giữa–cuối", "",
        f"Hoàn tất: {complete}; {result['n_attempted']}/60 lượt. Tác vụ GPT đo: {result['n_codex_attempts']}; probe riêng: {result['n_auxiliary_codex_attempts']}.", "",
        "Cùng 30 ID validation, cùng prompt/JSON Schema/GLiNER2/scorer. Hai phiên GPT mới mỗi mẫu, chạy xen kẽ theo cặp.",
        "B=min(80,N//10) từ dữ liệu ở cả hai cách. Ba mảnh giữ nguyên văn, ghép bằng hai dòng mới, không thêm từ.",
        "Phần dư ưu tiên giữa rồi đầu. Mảnh ngắn có thể cắt câu/mất chủ ngữ; dòng trống không bảo đảm GPT hiểu đúng sự gián đoạn.", "",
        "| Cách lấy đoạn | Schema hợp lệ | Bao phủ dữ kiện bằng schema | Precision | Recall | F1 | Mean e2e (s) |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for s in flat:
        ratio = f"{s['schema_gold_fact_coverage']:.4%}" if s['schema_gold_fact_coverage'] is not None else "null"
        mean = f"{s['all_mean_ms']/1000:.3f}" if s['all_mean_ms'] is not None else "null"
        lines.append(f"| {s['strategy']} | {s['schema_valid']}/30 | {ratio} | {s['precision']:.4%} | {s['recall']:.4%} | {s['f1']:.4%} | {mean} |")
    if comparison:
        lines += ["", f"Chênh lệch F1 (đầu–giữa–cuối trừ giữa): {comparison['f1_difference']:.6f}; CI95 {comparison['f1_difference_ci95']}.",
            f"Tỷ số e2e trên {comparison['n_success_pairs']} cặp hợp lệ: {comparison['latency_ratio']}; CI95 {comparison['latency_ratio_ci95']}.",
            f"Chênh lệch bao phủ dữ kiện bằng schema: {comparison['gold_fact_schema_coverage']}."]
    lines += ["", "Đây là thí nghiệm bổ sung; SPEC chính vẫn dùng đoạn giữa liên tục. Không đổi cấu hình chính theo kết quả này.",
        "Điểm chất lượng gồm mẫu lỗi. Khi chưa đủ 60 lượt, các điểm là tạm tính trên phần đã có, không phải so sánh hoàn tất.",
        "CI bootstrap 2000 lần theo tài liệu, seed 2026; không đo biến thiên qua nhiều lần gọi GPT. Validation chưa loại sạch trùng trận.", ""]
    atomic_write(dest / "report.md", "\n".join(lines))
    return result
