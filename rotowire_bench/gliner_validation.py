"""Paired, validation-only GLiNER diagnostics. Never constructs a GPT client."""
from __future__ import annotations

import copy
import random
import time
import zipfile
from collections import Counter
from pathlib import Path

from .data import prepared
from .evaluation import aggregate_counts, paired_bootstrap, score_output, scores
from .pipelines import SUCCESS, execute
from .reporting import latency_stats, write_csv
from .runner import campaign_mutex, environment, source_hashes
from .schemas import TableOutput, known_schema
from .utils import digest, read_json, read_jsonl, utc_now, write_json, write_jsonl, atomic_write

VARIANTS = {
    "legacy": dict(schema_labels="opaque", schema_descriptions="full", table_execution="joint"),
    "semantic": dict(schema_labels="semantic", schema_descriptions="full", table_execution="joint"),
    "compact": dict(schema_labels="semantic", schema_descriptions="compact", table_execution="joint"),
    "separate": dict(schema_labels="semantic", schema_descriptions="compact", table_execution="separate"),
}


class NoGPT:
    def request(self, *args, **kwargs):
        raise AssertionError("GPT inference is forbidden in GLiNER validation")


def run_validation(config, out, *, resume=False, local_files_only=True):
    dest = Path(out)
    if dest.exists() and not resume:
        raise ValueError("Output already exists; use a new directory or --resume")
    dest.mkdir(parents=True, exist_ok=True)
    with campaign_mutex(dest / ".runner.lock"):
        return _run_validation(config, dest, resume=resume, local_files_only=local_files_only)


def _run_validation(config, dest, *, resume, local_files_only):
    inputs, gold, manifest = prepared(config, "validation")
    ids = [i.sample_id for i in inputs]
    if len(ids) != 30:
        raise ValueError("Diagnostic requires the 30 frozen validation IDs")
    lock = dict(kind="gliner_validation_only", split="validation", sample_ids=ids,
        config=config, variants=VARIANTS, variant_order=list(VARIANTS), source_sha256=source_hashes(),
        manifest_sha256=digest(manifest), selection="highest fact_micro_f1; tie: lower all_mean_ms; validation only",
        environment=environment(config))
    lock_path = dest / "protocol.lock.json"
    if resume:
        previous = read_json(lock_path)
        for key in ("kind", "split", "sample_ids", "config", "variants", "variant_order", "source_sha256", "manifest_sha256"):
            if previous[key] != lock[key]:
                raise ValueError(f"Diagnostic resume mismatch: {key}")
        lock = previous
    else:
        write_json(lock_path, lock)
        write_json(dest / "sample_manifest.json", manifest)
        write_jsonl(dest / "inputs.jsonl", [x.model_dump() for x in inputs])
        write_jsonl(dest / "evaluation_gold.jsonl", [gold[s].model_dump() for s in ids])
        # Preserve the implementation even after selecting defaults for a new run.
        with zipfile.ZipFile(dest / "source_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name in lock["source_sha256"]:
                archive.write(Path(__file__).parent / name, "rotowire_bench/" + name)
    order = list(ids)
    random.Random(44).shuffle(order)
    variants = list(VARIANTS)
    schedule = [(sid, name) for i, sid in enumerate(order)
                for name in variants[i % len(variants):] + variants[:i % len(variants)]]
    write_json(dest / "schedule.json", schedule)
    items = {x.sample_id: x for x in inputs}
    from .models.gliner2_adapter import GLiNER2Adapter
    model = GLiNER2Adapter(config["gliner"], local_files_only=local_files_only)
    write_json(dest / "model_setup.json", model.metadata)
    started = time.perf_counter_ns()
    for sid, variant in schedule:
        path = dest / "results" / f"{sid}__{variant}.json"
        if path.exists():
            if read_json(path)["protocol_sha256"] != digest(lock):
                raise ValueError("Result protocol mismatch")
            continue
        event_dir = dest / "events" / f"{sid}__{variant}"
        if event_dir.exists() and any(event_dir.iterdir()):
            raise ValueError("Interrupted diagnostic task; use a new run directory, do not silently retry")
        run_config = copy.deepcopy(config)
        run_config["gliner"].update(VARIANTS[variant])
        model.config = run_config["gliner"]
        def emit(kind, value):
            suffix = value["index"] if kind == "gliner_chunk" else 0
            write_json(event_dir / f"{kind}-{suffix}.json", value)
        result = execute(items[sid], "A_GLINER_KNOWN", run_config, model, NoGPT(), emit,
                         known_schema_factory=lambda: known_schema(gold[sid]))
        result.update(variant=variant, protocol_sha256=digest(lock))
        write_json(path, result)
        print(f"{sid} {variant}: {result['status']} ({result['n_forward_passes']} forward)", flush=True)
    recorded = [read_json(p) for p in (dest / "results").glob("*.json")]
    n_attempted = sum(r["attempted"] for r in recorded)
    write_json(dest / "campaign.json", dict(complete=n_attempted==120, n_expected=120, n_attempted=n_attempted,
        n_gpt_calls=0, split="validation", finished_at=utc_now(),
        last_session_execution_ms=(time.perf_counter_ns()-started)/1e6))
    return report_validation(dest)


def report_validation(out):
    dest = Path(out)
    lock = read_json(dest / "protocol.lock.json")
    gold = {x["sample_id"]: TableOutput.model_validate(x["tables"])
            for x in read_jsonl(dest / "evaluation_gold.jsonl")}
    manifest = read_json(dest / "sample_manifest.json")
    if digest(manifest) != lock["manifest_sha256"]:
        raise ValueError("Diagnostic manifest changed")
    expected = {x["sample_id"]: x for x in manifest["validation_samples"]}
    if set(gold) != set(lock["sample_ids"]):
        raise ValueError("Diagnostic gold IDs changed")
    for sid, value in gold.items():
        if digest(value.model_dump()) != expected[sid]["gold_sha256"]:
            raise ValueError("Diagnostic gold changed")
    rows = [read_json(p) for p in (dest / "results").glob("*.json")]
    identities = set()
    for row in rows:
        identity = (row["sample_id"], row["variant"])
        if (row.get("simulated") or row["protocol_sha256"] != digest(lock)
            or row["sample_id"] not in gold or row["variant"] not in lock["variants"]
            or row["n_codex_attempts"] != 0 or identity in identities):
            raise ValueError("Invalid diagnostic result")
        identities.add(identity)
    complete = len(rows) == 120 and all(r["attempted"] for r in rows)
    summaries, details, latencies, sample_rows = [], {}, {}, []
    for variant in lock["variant_order"]:
        group = [r for r in rows if r["variant"] == variant]
        detail, times = {}, {}
        for r in group:
            pred = TableOutput.model_validate(r["output"]) if r["status"] in SUCCESS else TableOutput(tables=[])
            score = score_output(pred, gold[r["sample_id"]])
            detail[r["sample_id"]] = score
            if r["status"] in SUCCESS and r["timings"]["latency_e2e_ms"] is not None:
                times[r["sample_id"]] = r["timings"]["latency_e2e_ms"]
            sample_rows.append(dict(sample_id=r["sample_id"], variant=variant, status=r["status"],
                n_forward_passes=r["n_forward_passes"], latency_e2e_ms=r["timings"]["latency_e2e_ms"],
                **{f"fact_{k}": v for k, v in score["facts"].items()}))
        details[variant], latencies[variant] = detail, times
        counts = aggregate_counts(list(detail.values()))
        summaries.append(dict(variant=variant, n_expected=30, n_attempted=len(group),
            n_success=len(times), statuses=dict(Counter(r["status"] for r in group)),
            **counts, **scores(**counts),
            entity_f1=scores(**aggregate_counts(list(detail.values()),"entities"))["f1"],
            n_forward_passes=sum(r["n_forward_passes"] for r in group),
            **latency_stats([r["timings"]["latency_e2e_ms"] for r in group
                            if r["timings"]["latency_e2e_ms"] is not None],"all"),
            **latency_stats(list(times.values()),"success")))
    comparisons = []
    if complete:
        for variant in lock["variant_order"][1:]:
            comparisons.append(dict(left=variant,right="legacy",**paired_bootstrap(
                details[variant],details["legacy"],latencies[variant],latencies["legacy"],
                seed=2026,repetitions=2000)))
    selected = max(summaries,key=lambda s:(s["f1"],-s["all_mean_ms"]))["variant"] if complete else None
    result = dict(complete=complete, split="validation", n_gpt_calls=0, summary=summaries,
                  comparisons=comparisons, selected_variant=selected,
                  selection_is_validation_not_test_performance=True)
    write_json(dest / "metrics.json", result)
    write_json(dest / "scores_per_sample.json", details)
    write_csv(dest / "summary.csv", summaries)
    write_csv(dest / "metrics_per_sample.csv", sample_rows)
    lines = ["# Chẩn đoán GLiNER2 trên 30 mẫu validation", "",
        f"Trạng thái: {'hoàn tất 120/120' if complete else 'chưa hoàn tất'}; GPT calls: 0.", "",
        "Bốn cấu hình chọn trước, thứ tự luân phiên; cùng checkpoint/ngưỡng/bộ chấm/gold.",
        "Đây là tập dùng chọn cấu hình, không phải kết quả test hoặc so sánh mới với GPT.", "",
        "| Cấu hình | Hợp lệ/30 | Precision | Recall | Fact F1 | Mean hợp lệ (s) | Forward |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for s in summaries:
        mean = f"{s['success_mean_ms']/1000:.3f}" if s['success_mean_ms'] is not None else "null"
        lines.append(f"| {s['variant']} | {s['n_success']} | {s['precision']:.6f} | {s['recall']:.6f} | {s['f1']:.6f} | {mean} | {s['n_forward_passes']} |")
    lines += ["", f"Cấu hình được chọn theo fact F1 validation, hòa điểm dùng mean toàn lượt: `{selected}`.", "",
        "legacy: tên t0/f0, mô tả đầy đủ, gộp bảng. semantic: đổi tên có nghĩa, giữ mô tả.",
        "compact: thêm rút gọn mô tả. separate: thêm tách bảng, mỗi bảng đọc đủ toàn bài.", "",
        "CI bootstrap ghép cặp và thời gian toàn lượt/thành công có trong metrics.json/summary.csv.",
        "Kết quả bao gồm lỗi. Chưa sửa alias, đơn vị hoặc nhãn; không dùng gold để ghép bản ghi.",
        "Validation chỉ loại trùng văn bản, chưa loại sạch trùng trận. CI không điều chỉnh việc chọn",
        "cấu hình trên cùng tập; cần chạy test mới sau khi khóa để đánh giá độc lập.", ""]
    atomic_write(dest / "report.md", "\n".join(lines))
    return result
