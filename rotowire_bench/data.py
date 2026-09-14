from __future__ import annotations

import random
import re
import urllib.request
from pathlib import Path
from .schemas import Cell, EvaluationGold, InferenceInput, Row, Table, TableOutput
from .snippets import select_snippet
from .utils import digest, read_json, read_jsonl, utc_now, write_json, write_jsonl


def parse_table_line(line: str) -> TableOutput:
    """Verified upstream format: Team:/Player:, <NEWLINE>, pipe-delimited cells."""
    tables, current, headers = [], None, None
    for segment in line.split("<NEWLINE>"):
        segment = segment.strip()
        if not segment:
            continue
        if segment in ("Team:", "Player:"):
            name = "teams" if segment == "Team:" else "players"
            current = Table(table_name=name, entity_type="basketball team" if name == "teams" else "basketball player", field_names=[], rows=[])
            tables.append(current)
            headers = None
            continue
        if current is None or not segment.startswith("|") or not segment.endswith("|"):
            raise ValueError(f"Unknown Text-to-Table serialization: {segment[:80]}")
        values = [s.strip() for s in segment[1:-1].split("|")]
        if headers is None:
            if values[0] or any(not v for v in values[1:]):
                raise ValueError("Invalid column header")
            headers = values[1:]
            if len(set(headers)) != len(headers):
                raise ValueError("Duplicate gold headers")
            current.field_names = headers
        else:
            if len(values) != len(headers) + 1 or not values[0]:
                raise ValueError("Misaligned gold row")
            current.rows.append(Row(entity_name=values[0], cells=[Cell(field_name=f, raw_values=[v]) for f, v in zip(headers, values[1:]) if v]))
    if not tables:
        raise ValueError("No gold tables")
    return TableOutput(tables=tables)


def load_split(raw_dir, split):
    stem = {"test": "test", "validation": "valid"}[split]
    raw_dir = Path(raw_dir)
    texts = (raw_dir / f"{stem}.text").read_text(encoding="utf-8").splitlines()
    labels = (raw_dir / f"{stem}.data").read_text(encoding="utf-8").splitlines()
    if len(texts) != len(labels):
        raise ValueError("Text/gold line count mismatch")
    inputs, gold = [], []
    for i, (text, label) in enumerate(zip(texts, labels)):
        if not text.strip() or re.fullmatch(r"[\d\s]+", text) or "Ġ" in text or "@@ " in text:
            raise ValueError(f"Empty or possibly undecoded BPE input at {split}:{i}")
        sid = f"{split}-{i:04d}-{digest(text)[:12]}"
        inputs.append(InferenceInput(sample_id=sid, full_text=text))
        gold.append(EvaluationGold(sample_id=sid, original_index=i, tables=parse_table_line(label)))
    return inputs, gold


def download(config):
    ds = config["dataset"]
    dest = Path(ds["raw_dir"])
    dest.mkdir(parents=True, exist_ok=True)
    revision = ds["revision"]
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Dataset revision must be a commit SHA")
    old = {x["filename"]: x for x in read_json(dest / "provenance.json")} if (dest / "provenance.json").exists() else {}
    records = []
    for name in ("test.text", "test.data", "valid.text", "valid.data"):
        url = f"https://huggingface.co/datasets/{ds['source']}/resolve/{revision}/rotowire/{name}"
        path = dest / name
        if path.exists():
            record = old.get(name)
            if not record or record["sha256"] != digest(path.read_bytes()) or record["revision"] != revision:
                raise ValueError(f"Unverified or modified data file: {path}")
        else:
            with urllib.request.urlopen(url, timeout=180) as response:
                body = response.read()
            path.write_bytes(body)
            record = dict(filename=name, url=url, revision=revision, sha256=digest(body), downloaded_at=utc_now())
        records.append(record)
        write_json(dest / "provenance.json", records + [v for k, v in old.items() if k not in {r['filename'] for r in records}])
    return records


def prepare(config):
    provenance = download(config)
    ds = config["dataset"]
    dest = Path(ds["prepared_dir"])
    test, tg = load_split(ds["raw_dir"], "test")
    val, vg = load_split(ds["raw_dir"], "validation")
    if len(test) != ds["expected_test_count"] or len(test) != 728:
        raise ValueError(f"Source verification required: expected 728 test articles, found {len(test)}")
    indices = random.Random(ds["sample_seed"]).sample(range(len(test)), ds["test_size"])
    hashes = {digest(test[i].full_text) for i in indices}
    eligible = [i for i, item in enumerate(val) if digest(item.full_text) not in hashes]
    vi = random.Random(ds["validation_seed"]).sample(eligible, ds["validation_size"])
    manifest = dict(dataset_revision=ds["revision"], source=ds["source"], n_test=len(test), n_validation=len(val),
        seed=ds["sample_seed"], validation_seed=ds["validation_seed"],
        samples=[dict(sample_id=test[i].sample_id, original_index=i, text_sha256=digest(test[i].full_text), gold_sha256=digest(tg[i].tables.model_dump())) for i in indices],
        validation_samples=[dict(sample_id=val[i].sample_id, original_index=i, text_sha256=digest(val[i].full_text), gold_sha256=digest(vg[i].tables.model_dump())) for i in vi],
        manual_review_ids=random.Random(2026).sample([test[i].sample_id for i in indices], min(20, len(indices))),
        overlap_check=dict(exact_text_excluded=len(val)-len(eligible), reliable_game_keys=False,
          limitation="Không có khóa trận ghép xác định; chỉ loại trùng văn bản. Validation chỉ kiểm tra kỹ thuật, không tối ưu theo nhãn."),
        files=provenance)
    path = dest / "sample_manifest.json"
    if path.exists() and read_json(path) != manifest:
        raise ValueError("Frozen manifest differs; use a new prepared_dir for a new dataset/protocol")
    write_json(path, manifest)
    for name, inp, gold, ids in (("test", test, tg, indices), ("validation", val, vg, vi)):
        write_jsonl(dest / f"{name}.inputs.jsonl", [inp[i].model_dump() for i in ids])
        write_jsonl(dest / f"{name}.gold.jsonl", [gold[i].model_dump() for i in ids])
    write_jsonl(dest / "snippets.jsonl", [dict(sample_id=test[i].sample_id, **select_snippet(test[i]).to_dict()) for i in indices])
    return manifest


def prepared(config, split="test"):
    base = Path(config["dataset"]["prepared_dir"])
    inputs = [InferenceInput.model_validate(r) for r in read_jsonl(base / f"{split}.inputs.jsonl")]
    gold = {r["sample_id"]: EvaluationGold.model_validate(r) for r in read_jsonl(base / f"{split}.gold.jsonl")}
    manifest = read_json(base / "sample_manifest.json")
    entries = manifest["samples" if split == "test" else "validation_samples"]
    if [r.sample_id for r in inputs] != [r["sample_id"] for r in entries] or set(gold) != {r.sample_id for r in inputs}:
        raise ValueError("Prepared IDs differ from frozen manifest")
    for item, record in zip(inputs, entries):
        if digest(item.full_text) != record["text_sha256"] or digest(gold[item.sample_id].tables.model_dump()) != record["gold_sha256"]:
            raise ValueError("Prepared content differs from manifest")
    return inputs, gold, manifest
