import json
import re

import pytest

from rotowire_bench.hybrid_validation import schema_coverage, run_validation, report_validation
from rotowire_bench.models.codex_gpt55_adapter import build_request
from rotowire_bench.pipelines import execute
from rotowire_bench.schemas import ProposedExtractionSchema, SchemaField, known_schema, TableOutput
from rotowire_bench.utils import digest, read_json, write_json


def test_decoder_excludes_reserved_key_without_restricting_known_fields(config, gold):
    contract = build_request(config["gpt"], "schema", "untrusted fragment")["output_schema"]
    field = contract["$defs"]["ProposedSchemaField"]["properties"]["name"]
    assert re.fullmatch(field["pattern"], "First quarter points")
    assert re.fullmatch(field["pattern"], "3-point attempts")
    for value in ("entity_name", "ENTITY_NAME", " entity_name ", "[SEP]"):
        assert not re.fullmatch(field["pattern"], value)
    parsed = ProposedExtractionSchema.model_validate(known_schema(gold).model_dump())
    assert parsed.tables[1].fields[0].name == "Points"
    # The known-schema contract still accepts arbitrary source headers.
    assert SchemaField(name="Rate (%)", description="", value_type="number", unit=None)


def test_invalid_schema_is_not_repaired_or_sent_to_gliner(config, item):
    class GPT:
        blocked_reason = None
        calls = 0
        def request(self, request, emit):
            self.calls += 1
            return json.dumps(dict(tables=[dict(table_name="player", entity_type="player",
                identity_field="entity_name", fields=[dict(name="entity_name", description="name",
                value_type="string", unit=None)])]))
    class GL:
        def extract(self, *args):
            raise AssertionError("Invalid schema must never reach extraction")
    gpt = GPT()
    r = execute(item, "B_HYBRID_SHORT", config, GL(), gpt, lambda *args: None)
    assert r["status"] == "invalid_output" and r["output"] == {"tables": []}
    assert gpt.calls == 1


def test_duplicate_names_rejected_and_scope_preserved(gold):
    data = known_schema(gold).model_dump()
    data["tables"][1]["fields"][1]["name"] = " points "
    with pytest.raises(ValueError):
        ProposedExtractionSchema.model_validate(data)
    data["tables"][1]["fields"][1]["name"] = "First quarter points"
    parsed = ProposedExtractionSchema.model_validate(data)
    assert parsed.tables[1].fields[1].name == "First quarter points"
    coverage = schema_coverage(parsed.model_dump(), gold.tables)
    assert coverage["fn"] == 1 and coverage["fp"] == 1
    assert coverage["gold_facts_with_declared_field"] == 3


def test_runner_freezes_and_report_counts_failed_schema(tmp_path, monkeypatch, config, item, gold):
    import rotowire_bench.hybrid_validation as module
    inputs = [item.model_copy(update={"sample_id": f"synthetic-{i}"}) for i in range(30)]
    golds = {i.sample_id: gold.model_copy(update={"sample_id": i.sample_id}) for i in inputs}
    manifest = {"validation_samples": [dict(sample_id=i.sample_id,
        text_sha256=digest(i.full_text), gold_sha256=digest(gold.tables.model_dump())) for i in inputs]}
    monkeypatch.setattr(module, "prepared", lambda *args: (inputs, golds, manifest))
    class GPT:
        blocked_reason = None
    monkeypatch.setattr(module, "preflight", lambda *args, **kwargs: ({"gpt": {"status": "ready"}}, object(), GPT()))
    calls = []
    def fake_execute(received, arm, config, model, gpt, emit):
        calls.append(received.sample_id)
        assert arm == "B_HYBRID_SHORT" and not hasattr(received, "gold")
        # All are failures, which must still count all their gold facts as FN.
        return dict(sample_id=received.sample_id, arm=arm, attempted=True, simulated=False,
            status="invalid_output", text_sha256=digest(received.full_text), schema=None,
            output={"tables": []}, n_codex_attempts=1, n_forward_passes=0,
            timings={"latency_e2e_ms": 10.0})
    monkeypatch.setattr(module, "execute", fake_execute)
    out = tmp_path / "pilot"
    report = run_validation(config, out, limit=3)
    assert report["complete"] and report["n_schema_valid"] == 0
    assert report["facts"] == dict(tp=0, fp=0, fn=12, precision=0.0, recall=0.0, f1=0.0)
    run_validation(config, out, limit=3, resume=True)
    assert len(calls) == 3
    sample = out / "results" / "synthetic-0.json"
    record = read_json(sample)
    record["protocol_sha256"] = "tampered"
    write_json(sample, record)
    with pytest.raises(ValueError, match="Invalid hybrid result"):
        report_validation(out)
