import json
from pathlib import Path

import pytest

from rotowire_bench.models.codex_gpt55_adapter import build_request
from rotowire_bench.schemas import InferenceInput, known_schema
from rotowire_bench.snippets import select_experiment_snippet, select_snippet
from rotowire_bench.snippet_comparison import STRATEGIES, coverage_bootstrap, run_comparison, report_comparison, schedule
from rotowire_bench.utils import digest, read_json, write_json


@pytest.mark.parametrize("n", [0, 9, 10, 20, 30, 100, 110, 799, 800, 1001])
def test_distributed_exact_budget_verbatim_and_nonoverlap(n):
    text = "\t \n".join(f"w{i}," for i in range(n))
    item = InferenceInput(sample_id="synthetic", full_text=text)
    s = select_experiment_snippet(item, strategy="head_middle_tail")
    b = min(80, n//10)
    assert s.start_char is None and s.end_char is None
    if b == 0:
        assert s.status == "insufficient_fragment" and not s.segments
        return
    assert len(s.text.split()) == s.snippet_word_count == b
    assert s.word_ratio <= .1 and s.sha256 == digest(s.text)
    assert s.text == "\n\n".join(p["text"] for p in s.segments)
    for p in s.segments:
        assert p["text"] == text[p["start_char"]:p["end_char"]]
        assert len(p["text"].split()) == p["word_count"]
    assert all(a["end_char"] < z["start_char"] for a, z in zip(s.segments, s.segments[1:]))
    if b >= 3:
        assert len(s.segments) == 3
        assert s.segments[0]["text"].split()[0] == "w0,"
        assert s.segments[-1]["text"].split()[-1] == f"w{n-1},"
        assert max(p["word_count"] for p in s.segments)-min(p["word_count"] for p in s.segments) <= 1
    else:
        assert s.text == select_snippet(item).text


def test_center_unchanged_and_request_only_contains_allowed_text(config):
    item = InferenceInput(sample_id="synthetic", full_text=" ".join(f"word{i}" for i in range(120)))
    a = select_experiment_snippet(item, strategy=STRATEGIES[0])
    b = select_experiment_snippet(item, strategy=STRATEGIES[1])
    assert a == select_snippet(item)
    requests = [build_request(config["gpt"], "schema", s.text) for s in (a, b)]
    assert requests[0]["output_schema"] == requests[1]["output_schema"]
    assert requests[0]["stdin"].split("SOURCE_DATA_JSON:")[0] == requests[1]["stdin"].split("SOURCE_DATA_JSON:")[0]
    for r, s in zip(requests, (a,b)):
        assert json.loads(r["input"]) == {"article_fragment": s.text}
        assert "word25" not in r["stdin"]
    with pytest.raises(ValueError):
        select_experiment_snippet(item, strategy="unsupported")


def test_paired_order_and_bootstrap():
    jobs = schedule([str(i) for i in range(30)])
    assert len(set(jobs)) == 60
    assert sum(jobs[i][1] == STRATEGIES[0] for i in range(0,60,2)) == 15
    assert all(jobs[i][0] == jobs[i+1][0] for i in range(0,60,2))
    a = {str(i): dict(gold_fact_count=10, gold_facts_with_declared_field=8) for i in range(4)}
    b = {str(i): dict(gold_fact_count=10, gold_facts_with_declared_field=3) for i in range(4)}
    result = coverage_bootstrap(a,b)
    assert result["difference"] == pytest.approx(.5)
    assert result["ci95"] == pytest.approx([.5,.5])


def test_paired_runner_resume_freezes_and_does_not_reuse_predictions(tmp_path, monkeypatch, config, item, gold):
    import rotowire_bench.snippet_comparison as module
    inputs = [InferenceInput(sample_id=f"synthetic-{i}", full_text=item.full_text*10) for i in range(30)]
    golds = {i.sample_id: gold.model_copy(update={"sample_id": i.sample_id}) for i in inputs}
    manifest = {"validation_samples": [dict(sample_id=i.sample_id, text_sha256=digest(i.full_text),
        gold_sha256=digest(gold.tables.model_dump())) for i in inputs]}
    monkeypatch.setattr(module, "prepared", lambda *args: (inputs, golds, manifest))
    setup_calls, requests = [], []
    class GPT:
        blocked_reason = None
        last_audit = {"status": "verified"}
        def request(self, payload, emit):
            requests.append(payload)
            emit("attempt", dict(request=payload, request_sha256=digest(payload), attempt=1, duration_ms=.001))
            return known_schema(gold).model_dump_json()
    class GL:
        def extract(self, received, schema, emit):
            assert received.full_text == item.full_text*10
            assert not hasattr(received, "gold")
            return gold.tables
    def setup(*args, **kwargs):
        setup_calls.append(1)
        return {"gpt": {"status": "ready"}}, GL(), GPT()
    monkeypatch.setattr(module, "preflight", setup)
    out = tmp_path / "paired"
    r = run_comparison(config, out, max_pairs=3)
    assert not r["complete"] and r["n_attempted"] == 6 and len(requests) == 6
    r = run_comparison(config, out, resume=True)
    assert r["complete"] and r["n_attempted"] == len(requests) == 60
    assert r["comparison"]["n_quality"] == r["comparison"]["n_success_pairs"] == 30
    run_comparison(config, out, resume=True)
    assert len(setup_calls) == 2 and len(requests) == 60
    path = out / STRATEGIES[1] / "protocol.lock.json"
    lock = read_json(path); lock["config"]["gliner"]["threshold"] = .9
    write_json(path, lock)
    with pytest.raises(ValueError, match="Child protocol"):
        report_comparison(out)
