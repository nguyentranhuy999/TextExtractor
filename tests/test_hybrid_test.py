import pytest

from rotowire_bench.hybrid_validation import run_test, run_validation, report_hybrid
from rotowire_bench.utils import digest, read_json, write_json


def setup_fake_test(monkeypatch, item, gold, count=200):
    import rotowire_bench.hybrid_validation as module
    inputs = [item.model_copy(update={"sample_id": f"synthetic-test-{i}"}) for i in range(count)]
    golds = {i.sample_id: gold.model_copy(update={"sample_id": i.sample_id}) for i in inputs}
    manifest = {"samples": [dict(sample_id=i.sample_id, text_sha256=digest(i.full_text),
        gold_sha256=digest(gold.tables.model_dump())) for i in inputs]}
    def prepare(config, split):
        assert split == "test"
        return inputs, golds, manifest
    monkeypatch.setattr(module, "prepared", prepare)
    setups, calls = [], []
    class GPT:
        blocked_reason = None
    def preflight(*args, **kwargs):
        setups.append(1)
        return {"gpt": {"status": "ready"}}, object(), GPT()
    monkeypatch.setattr(module, "preflight", preflight)
    def execute(item, arm, config, model, gpt, emit, **kwargs):
        assert arm == "B_HYBRID_SHORT" and not kwargs
        assert not hasattr(item, "gold")
        calls.append(item.sample_id)
        return dict(sample_id=item.sample_id, arm=arm, attempted=True, simulated=False,
            status="invalid_output", text_sha256=digest(item.full_text), schema=None,
            output={"tables": []}, n_codex_attempts=1, n_forward_passes=0,
            timings={"latency_e2e_ms": 10.0})
    monkeypatch.setattr(module, "execute", execute)
    return inputs, calls, setups


def test_only_200_hybrid_tasks_resume_without_new_probe_when_complete(tmp_path, monkeypatch, config, item, gold):
    inputs,calls,setups = setup_fake_test(monkeypatch,item,gold)
    out = tmp_path/"hybrid-test"
    partial = run_test(config,out,max_tasks=2)
    assert partial["split"] == "test" and partial["n_expected"] == 200
    assert partial["n_attempted"] == 2 and not partial["complete"]
    assert len(read_json(out/"campaign.json")["remaining"]) == 198
    result = run_test(config,out,resume=True)
    assert result["complete"] and result["n_attempted"] == 200
    assert len(calls) == len(set(calls)) == 200
    assert result["facts"]["fn"] == 800  # failures remain in the denominator
    assert result["gold_fact_count"] == 800
    assert result["n_valid_outputs"] == 0
    assert read_json(out/"campaign.json")["remaining"] == []
    run_test(config,out,resume=True)
    assert len(calls)==200 and len(setups)==2
    path=out/"results"/f"{inputs[0].sample_id}.json"
    r=read_json(path); r["arm"]="B_GPT_DIRECT"; write_json(path,r)
    with pytest.raises(ValueError,match="Invalid hybrid result"):
        report_hybrid(out)


def test_refuses_missing_test_ids_before_model_setup(tmp_path, monkeypatch, config, item, gold):
    _,calls,setups=setup_fake_test(monkeypatch,item,gold,count=199)
    with pytest.raises(ValueError,match="200"):
        run_test(config,tmp_path/"short")
    assert not calls and not setups


def test_interrupted_request_is_not_reissued(tmp_path, monkeypatch, config, item, gold):
    _,calls,setups=setup_fake_test(monkeypatch,item,gold)
    out=tmp_path/"interrupted"
    run_test(config,out,max_tasks=1)
    next_sid=read_json(out/"schedule.json")[1]
    write_json(out/"events"/next_sid/"request_started-interrupted.json",{"attempt":1})
    with pytest.raises(ValueError,match="Interrupted task"):
        run_test(config,out,resume=True)
    assert len(calls)==len(setups)==1


def test_validation_runner_refuses_a_paired_child(tmp_path, monkeypatch, config, item, gold):
    import rotowire_bench.hybrid_validation as module
    inputs=[item.model_copy(update={"sample_id":f"synthetic-{i}"}) for i in range(30)]
    monkeypatch.setattr(module,"prepared",lambda *args:(inputs,{},{}))
    out=tmp_path/"paired-child";out.mkdir()
    write_json(out/"protocol.lock.json",{"parent_protocol_sha256":"parent"})
    with pytest.raises(ValueError,match="parent directory"):
        run_validation(config,out,resume=True)
