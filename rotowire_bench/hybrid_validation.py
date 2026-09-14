"""Frozen hybrid-only runs; no known schema is passed to inference."""
from __future__ import annotations

import random
import statistics
import time
import zipfile
from collections import Counter
from pathlib import Path

from .data import prepared
from .evaluation import aggregate_counts, counts, field_id, score_output, scores, sets, table_id
from .pipelines import SUCCESS, execute
from .reporting import latency_stats, write_csv
from .runner import campaign_mutex, environment, preflight, source_hashes
from .schemas import ProposedExtractionSchema, TableOutput
from .snippets import select_snippet
from .utils import atomic_write, digest, read_json, read_jsonl, utc_now, write_json, write_jsonl


def schema_coverage(schema, gold):
    """Evaluation only: measure declared fields even if later extraction fails."""
    predicted = set()
    if schema is not None:
        parsed = ProposedExtractionSchema.model_validate(schema)
        predicted = {(table_id(t.table_name), field_id(table_id(t.table_name), f.name))
                     for t in parsed.tables for f in t.fields}
    target = sets(gold)
    c = counts(predicted, target["fields"])
    return dict(**c, **scores(**c), gold_count=len(target["fields"]),
        missing_fields=sorted(target["fields"]-predicted), extra_fields=sorted(predicted-target["fields"]),
        gold_facts_with_declared_field=sum((f[0], f[2]) in predicted for f in target["facts"]),
        gold_fact_count=len(target["facts"]))


def run_validation(config, out, *, limit=30, resume=False):
    return run_hybrid(config, out, split="validation", limit=limit, resume=resume)


def run_test(config, out, *, resume=False, max_tasks=None):
    return run_hybrid(config, out, split="test", limit=None, resume=resume, max_tasks=max_tasks)


def run_hybrid(config, out, *, split, limit, resume=False, max_tasks=None):
    if (split not in ("test", "validation") or config["gpt"]["execution_mode"] != "codex_cli"
        or (split == "validation" and limit not in (3, 30)) or (split == "test" and limit is not None)
        or (max_tasks is not None and max_tasks < 1)):
        raise ValueError("Hybrid requires Codex CLI, validation limit 3/30 or all 200 test IDs, and positive max-tasks")
    dest = Path(out)
    if dest.exists() and not resume:
        raise ValueError("Output exists; use a new directory or --resume")
    dest.mkdir(parents=True, exist_ok=True)
    with campaign_mutex(dest / ".runner.lock"):
        inputs, gold, manifest = prepared(config, split)
        required = 200 if split == "test" else 30
        if len(inputs) != required or len({i.sample_id for i in inputs}) != required:
            raise ValueError(f"Requires the frozen {required} {split} samples")
        if limit is not None:
            inputs = inputs[:limit]
        ids = [i.sample_id for i in inputs]
        lock = dict(kind=f"hybrid_{split}", split=split, sample_ids=ids,
            config=config, source_sha256=source_hashes(), manifest_sha256=digest(manifest),
            environment=environment(config), arm="B_HYBRID_SHORT",
            timing="Sequential shuffled documents; full application e2e; model setup and scoring excluded")
        if resume:
            old = read_json(dest / "protocol.lock.json")
            if old.get("parent_protocol_sha256"):
                raise ValueError("Use snippet-comparison with the parent directory to resume paired experiments")
            for k in ("kind", "split", "sample_ids", "config", "source_sha256", "manifest_sha256", "arm"):
                if old[k] != lock[k]:
                    raise ValueError(f"Resume mismatch: {k}")
            lock = old
        else:
            write_json(dest / "protocol.lock.json", lock)
            write_json(dest / "sample_manifest.json", manifest)
            write_jsonl(dest / "inputs.jsonl", [i.model_dump() for i in inputs])
            write_jsonl(dest / "evaluation_gold.jsonl", [gold[s].model_dump() for s in ids])
            write_jsonl(dest / "snippets.jsonl", [dict(sample_id=i.sample_id, **select_snippet(i).to_dict()) for i in inputs])
            with zipfile.ZipFile(dest / "source_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                for name in lock["source_sha256"]:
                    archive.write(Path(__file__).parent / name, "rotowire_bench/" + name)
        order = list(ids)
        random.Random(config["run"]["order_seed"]).shuffle(order)
        write_json(dest / "schedule.json", order)
        pending = []
        for sid in order:
            path = dest / "results" / f"{sid}.json"
            if path.exists():
                existing = read_json(path)
                if existing["protocol_sha256"] != digest(lock):
                    raise ValueError("Result protocol mismatch")
                if existing["attempted"]:
                    continue
            event_dir = dest / "events" / sid
            if event_dir.exists() and any(event_dir.iterdir()):
                raise ValueError("Interrupted task has events; use a new run, never silently retry")
            pending.append(sid)
        if not pending:
            return report_hybrid(dest)
        if max_tasks is not None:
            pending = pending[:max_tasks]
        # Each resume gets its own setup/probe log; no historical events overwritten.
        setup_dir = dest / "setup" / str(len(list((dest / "setup").glob("*"))))
        setup, model, gpt = preflight(config, setup_dir / "preflight.json", load_models=True, local_files_only=True)
        if setup["gpt"]["status"] != "ready" or model is None:
            write_json(dest / "blocked.json", setup)
            raise ValueError(f"Preflight blocked; see {setup_dir}/preflight.json")
        started = time.perf_counter_ns()
        items = {i.sample_id: i for i in inputs}
        for sid in pending:
            path = dest / "results" / f"{sid}.json"
            if path.exists() and read_json(path)["attempted"]:
                if read_json(path)["protocol_sha256"] != digest(lock):
                    raise ValueError("Result protocol mismatch")
                continue
            event_dir = dest / "events" / sid
            if event_dir.exists() and any(event_dir.iterdir()):
                raise ValueError("Interrupted task has events; use a new run, never silently retry")
            def emit(kind, data):
                suffix = (f"{data['request_sha256'][:16]}-{data['attempt']}" if kind in ("request_started", "attempt")
                          else str(data["index"]) if kind == "gliner_chunk" else "0")
                write_json(event_dir / f"{kind}-{suffix}.json", data)
            result = execute(items[sid], "B_HYBRID_SHORT", config, model, gpt, emit)
            result["protocol_sha256"] = digest(lock)
            write_json(path, result)
            print(f"{sid}: {result['status']}; schema={result['schema'] is not None}; "
                  f"GPT={result['n_codex_attempts']}; forwards={result['n_forward_passes']}", flush=True)
            if gpt.blocked_reason:
                break
        write_json(dest / "last_session.json", dict(finished_at=utc_now(),
            execution_ms=(time.perf_counter_ns()-started)/1e6))
        write_json(setup_dir / "execution.json", read_json(dest / "last_session.json"))
        return report_hybrid(dest)


def report_validation(out):
    return report_hybrid(out)


def report_hybrid(out):
    dest = Path(out)
    lock = read_json(dest / "protocol.lock.json")
    split = lock["split"]
    if split not in ("test", "validation"):
        raise ValueError("Unsupported hybrid split")
    manifest = read_json(dest / "sample_manifest.json")
    if digest(manifest) != lock["manifest_sha256"]:
        raise ValueError("Manifest changed")
    expected = {x["sample_id"]: x for x in manifest["samples" if split == "test" else "validation_samples"]}
    gold = {x["sample_id"]: TableOutput.model_validate(x["tables"]) for x in read_jsonl(dest / "evaluation_gold.jsonl")}
    if set(gold) != set(lock["sample_ids"]):
        raise ValueError("Gold IDs changed")
    if split == "test" and (len(gold) != 200 or set(gold) != set(expected)):
        raise ValueError("Hybrid test must preserve all 200 frozen IDs")
    for sid, table in gold.items():
        if digest(table.model_dump()) != expected[sid]["gold_sha256"]:
            raise ValueError("Gold changed")
    rows = [read_json(p) for p in sorted((dest / "results").glob("*.json"))]
    seen = set()
    detail, coverage, samples = {}, {}, []
    for r in rows:
        sid = r["sample_id"]
        if (sid not in gold or sid in seen or r.get("simulated") or r["arm"] != lock["arm"]
            or r["protocol_sha256"] != digest(lock) or r["text_sha256"] != expected[sid]["text_sha256"]):
            raise ValueError("Invalid hybrid result")
        seen.add(sid)
        if r["status"] in SUCCESS and (r.get("codex_audit") or {}).get("status") != "verified":
            raise ValueError("Successful hybrid result lacks verified Codex audit")
        pred = TableOutput.model_validate(r["output"]) if r["status"] in SUCCESS else TableOutput(tables=[])
        detail[sid] = score_output(pred, gold[sid])
        coverage[sid] = schema_coverage(r["schema"], gold[sid])
        samples.append(dict(sample_id=sid, status=r["status"], schema_valid=r["schema"] is not None,
            **{f"fact_{k}": v for k, v in detail[sid]["facts"].items()},
            schema_field_recall=coverage[sid]["recall"], **r["timings"],
            n_codex_attempts=r["n_codex_attempts"], n_forward_passes=r["n_forward_passes"]))
    complete = seen == set(gold) and all(r["attempted"] for r in rows)
    fact_counts = aggregate_counts(list(detail.values()))
    field_counts = {k: sum(c[k] for c in coverage.values()) for k in ("tp", "fp", "fn")}
    auxiliary = [read_json(p) for p in (dest / "setup").glob("*/preflight_codex_events.json")]
    result = dict(complete=complete, split=split, n_expected=len(gold), n_completed=len(rows),
        n_attempted=sum(r["attempted"] for r in rows), statuses=dict(Counter(r["status"] for r in rows)),
        n_schema_valid=sum(r["schema"] is not None for r in rows),
        schema_valid_rate=sum(r["schema"] is not None for r in rows)/len(gold),
        n_schema_nonempty=sum(bool(r["schema"] and any(t["fields"] for t in r["schema"]["tables"])) for r in rows),
        n_codex_attempts=sum(r["n_codex_attempts"] for r in rows),
        n_auxiliary_codex_attempts=sum(e["kind"] == "request_started" for entries in auxiliary for e in entries),
        n_forward_passes=sum(r["n_forward_passes"] for r in rows),
        facts=dict(**fact_counts, **scores(**fact_counts)),
        macro_fact_f1=statistics.mean(d["facts"]["f1"] for d in detail.values()) if detail else None,
        output_fields=scores(**aggregate_counts(list(detail.values()), "fields")),
        entities=scores(**aggregate_counts(list(detail.values()), "entities")),
        exact_document_rate=sum(d["exact"] for d in detail.values())/len(rows) if rows else None,
        n_valid_outputs=sum(r["status"] in SUCCESS for r in rows),
        proposed_fields=dict(**field_counts, **scores(**field_counts)),
        gold_facts_with_declared_field=sum(c["gold_facts_with_declared_field"] for c in coverage.values()),
        gold_fact_count=sum(c["gold_fact_count"] for c in coverage.values()),
        field_metrics_include_schema_even_when_extraction_fails=True,
        **latency_stats([r["timings"]["latency_e2e_ms"] for r in rows if r["timings"]["latency_e2e_ms"] is not None], "all"),
        **latency_stats([r["timings"]["latency_e2e_ms"] for r in rows if r["status"] in SUCCESS], "success"))
    write_json(dest / "metrics.json", result)
    write_json(dest / "scores_per_sample.json", detail)
    write_json(dest / "schema_coverage.json", coverage)
    write_csv(dest / "metrics_per_sample.csv", samples)
    if split == "test":
        write_json(dest / "campaign.json", dict(complete=complete, n_expected=len(gold),
            n_attempted=result["n_attempted"], n_codex_attempts=result["n_codex_attempts"],
            n_auxiliary_codex_attempts=result["n_auxiliary_codex_attempts"],
            remaining=[sid for sid in lock["sample_ids"] if sid not in seen
                       or not next(r["attempted"] for r in rows if r["sample_id"]==sid)]))
        breakdown = {}
        for kind in ("players", "teams"):
            part = [score_output(TableOutput.model_validate(r["output"]) if r["status"] in SUCCESS else TableOutput(tables=[]),
                                 gold[r["sample_id"]], kind) for r in rows]
            c = aggregate_counts(part)
            breakdown[kind] = dict(**c, **scores(**c), gold_fact_count=sum(d["facts"]["gold_count"] for d in part))
        write_json(dest / "table_breakdown.json", breakdown)
    atomic_write(dest / "report.md", "\n".join([
        f"# Hybrid GPT 5.5 + GLiNER2 — {split}", "",
        f"Hoàn tất: {complete}; {len(rows)}/{len(gold)} mẫu; schema hợp lệ: {result['n_schema_valid']}/{len(gold)}.",
        f"Fact precision/recall/F1: {result['facts']['precision']:.6f} / {result['facts']['recall']:.6f} / {result['facts']['f1']:.6f}.",
        f"Recall trường schema: {result['proposed_fields']['recall']:.6f}; số trường thiếu (tính theo tài liệu): {field_counts['fn']}.",
        f"Mean e2e toàn lượt (ms): {result['all_mean_ms']}; mean hợp lệ (ms): {result['success_mean_ms']}.",
        f"GPT tasks/attempts đo: {result['n_codex_attempts']}; probe riêng: {result['n_auxiliary_codex_attempts']}.", "",
        ("GPT nhận các mảnh đầu–giữa–cuối nguyên văn, tổng tối đa 10% số từ và 80 từ, ghép bằng dòng trống."
         if lock.get("snippet_strategy") == "head_middle_tail" else
         "GPT chỉ thấy đoạn giữa nguyên văn, tối đa 10% số từ và 80 từ.") + " GLiNER2 đọc toàn bài theo schema đó.",
        "Tên có nghĩa, mô tả gọn, tách bảng; ngưỡng 0.5. Giữ nguyên scorer, aliases và gold.",
        "Schema rỗng hợp lệ không đồng nghĩa có trường hữu ích. Chỉ số bao phủ trường được chấm riêng trước GLiNER2.",
        "Điểm tính cả mẫu lỗi như dự đoán rỗng; nếu chưa hoàn tất thì chỉ là điểm tạm trên các kết quả đã ghi.",
        ("Đủ 200 ID test gốc, cấu hình chọn trước bằng validation; không chỉnh theo kết quả test."
         if split == "test" else "Validation dùng phát triển; chưa loại sạch trùng trận với test. Không phải điểm test độc lập."),
        ("So sánh ghép cặp hai cách chọn đoạn ở thư mục cha; prompt và mô hình giống nhau."
         if lock.get("parent_protocol_sha256") else
         "GPT trực tiếp không chạy lại. Số đo cũ, nếu đối chiếu, là baseline lịch sử; không diễn giải chênh lệch thời gian như phép đo xen kẽ cùng thời điểm."
         if split == "test" else
         "Không chạy baseline prompt cũ ghép cặp, nên chưa tách được tác động từng thay đổi hoặc khẳng định mức tăng so với run cũ."), ""]))
    return result
