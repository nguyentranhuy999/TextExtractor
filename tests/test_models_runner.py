import json
import time
from types import SimpleNamespace
from pathlib import Path
import pytest
from rotowire_bench.models.codex_gpt55_adapter import build_request
from rotowire_bench.models.gpt55_adapter import GPT55Adapter, retry_after  # legacy transport unit fixtures only
from rotowire_bench.models.gliner2_adapter import split_text, merge_chunks
from rotowire_bench.models.common import ModelError
from rotowire_bench.schemas import known_schema, TableOutput
from rotowire_bench.pipelines import execute
from rotowire_bench.runner import schedule, run, protocol, environment
from rotowire_bench.utils import write_json, write_jsonl, read_json


class MockResponse:
    id="mock-response"; model="gpt-5.5-2026-04-23"; status="completed"; output=[]
    def __init__(self,output_text):self.output_text=output_text
    def model_dump(self,mode=None):return dict(id=self.id,model=self.model,status=self.status,output_text=self.output_text,simulated=True)


class MockClient:
    def __init__(self,responses):self.responses=self;self.pending=list(responses);self.calls=[]
    def create(self,**kwargs):
        self.calls.append(kwargs)
        r=self.pending.pop(0)
        if isinstance(r,Exception):raise r
        return r


def test_mock_retry_records_all_attempts(config,item,monkeypatch):
    import rotowire_bench.models.gpt55_adapter as module
    class Mock429(Exception):
        status_code=429
        response=SimpleNamespace(headers={"retry-after":"0.001"})
    client=MockClient([Mock429(),MockResponse('{"tables":[]}')])
    adapter=GPT55Adapter(config["gpt"],client=client)
    events=[]
    adapter.request(build_request(config["gpt"],"direct",item.full_text),lambda k,v:events.append((k,dict(v))))
    attempts={e[1]["attempt"]:e[1] for e in events if e[0]=="attempt"}
    assert len(client.calls)==len(attempts)==2
    assert attempts[1]["retry_wait_ms"]>0
    assert attempts[1]["status_code"]==429
    assert retry_after({"retry-after":"Wed, 21 Oct 2015 07:28:00 GMT"},1)==0


def test_mock_auth_stops_branch(config,item):
    class Mock403(Exception):status_code=403
    client=MockClient([Mock403()]);adapter=GPT55Adapter(config["gpt"],client=client)
    payload=build_request(config["gpt"],"direct",item.full_text)
    with pytest.raises(ModelError):adapter.request(payload,lambda *args:None)
    with pytest.raises(ModelError) as error:adapter.request(payload,lambda *args:None)
    assert error.value.status=="blocked" and len(client.calls)==1


def test_mock_retry_after_zero_still_retries(config,item):
    class Mock429(Exception):
        status_code=429
        response=SimpleNamespace(headers={"retry-after":"0"})
    client=MockClient([Mock429(),MockResponse('{"tables":[]}')])
    adapter=GPT55Adapter(config["gpt"],client=client)
    adapter.request(build_request(config["gpt"],"direct",item.full_text),lambda *args:None)
    assert len(client.calls)==2


def test_mock_hybrid_timing_and_isolation(config,item,gold):
    schema=known_schema(gold)
    client=MockClient([MockResponse(schema.model_dump_json())])
    adapter=GPT55Adapter(config["gpt"],client=client)
    class MockGLiNER:
        def extract(self,received,schema,emit):
            assert not hasattr(received,"gold")
            time.sleep(.004)
            return gold.tables
    events=[]
    result=execute(item,"B_HYBRID_SHORT",config,MockGLiNER(),adapter,lambda k,v:events.append((k,v)))
    assert result["status"]=="success"
    t=result["timings"]
    assert t["extract_ms"]>=4 and t["schema_codex_ms"]>0
    assert t["latency_e2e_ms"]>=sum(t[k] for k in t if k!="latency_e2e_ms")-.1
    sent=json.loads(client.calls[0]["input"])
    assert set(sent)=={"article_fragment"} and len(sent["article_fragment"].split())<=len(item.full_text.split())//10


def test_mock_invalid_json_no_repair(config,item):
    client=MockClient([MockResponse('{"tables":[')])
    result=execute(item,"B_GPT_DIRECT",config,None,GPT55Adapter(config["gpt"],client=client),lambda *args:None)
    assert result["status"]=="invalid_output" and result["output"]=={"tables":[]} and len(client.calls)==1


def test_chunker_covers_every_character_and_overlap():
    text="One two three four. Five six seven eight. Nine ten eleven twelve. "*4
    chunks=split_text(text,lambda s:len(s.split())<=9,lambda s:len(s.split()),overlap_tokens=2)
    covered=set()
    for c in chunks:
        assert c["text"]==text[c["start_char"]:c["end_char"]]
        assert len(c["text"].split())<=9 and c["overlap_tokens"]<=2
        covered.update(range(c["start_char"],c["end_char"]))
    assert covered==set(range(len(text)))
    with pytest.raises(ModelError):split_text(text,lambda s:False,len)


def test_merge_keeps_conflicts(gold):
    s=known_schema(gold).tables[1]
    output,meta=merge_chunks([{"t0":[{"entity_name":"Alice Smith","f0":["24"]}]},{"t0":[{"entity_name":"alice smith","f0":["24","25"]}]}],{"t0":(s,{"f0":"Points"})})
    assert output.tables[0].rows[0].cells[0].raw_values==["24","25"]
    assert meta["duplicates_merged"]==1 and len(meta["conflicts"])==1


def test_latin_square():
    jobs=schedule(["a","b","c","d"])
    from rotowire_bench.config import ARMS
    assert len(set(jobs))==16
    assert {jobs[i*4][1] for i in range(4)}==set(ARMS)
    assert schedule(["a","b","c","d"])==jobs


def test_protocol_captures_changes(config):
    env=environment(config)
    a=protocol(config,{},"test",["x"],env)
    import copy
    changed=copy.deepcopy(config);changed["gliner"]["threshold"]=.6
    assert a!=protocol(changed,{},"test",["x"],env)


def test_mock_resume_preserves_latency_and_rejects_config_change(config,tmp_path,monkeypatch,item,gold):
    import rotowire_bench.runner as runner
    config["run"]["output_root"]=str(tmp_path)
    manifest={"manual_review_ids":[],"samples":[]}
    monkeypatch.setattr(runner,"prepared",lambda *args:([item],{item.sample_id:gold},manifest))
    calls=[]
    class MockGLiNER:
        load_ms=1;warmup_ms=1
        def extract(self,i,s,emit):
            calls.append(i.sample_id)
            time.sleep(.002)
            return gold.tables
    def mock_preflight(*args,**kwargs):
        return {},MockGLiNER(),SimpleNamespace(blocked_reason="mock unavailable",requests_used=0)
    monkeypatch.setattr(runner,"preflight",mock_preflight)
    first=run(config,run_id="mock-unit")
    result_path=tmp_path/"mock-unit"/"results"/f"{item.sample_id}__A_GLINER_KNOWN.json"
    before=result_path.read_bytes()
    second=run(config,run_id="mock-unit",resume=True)
    assert calls==[item.sample_id] and result_path.read_bytes()==before
    assert second["n_attempted"]==1 and second["n_blocked"]==3
    third=run(config,resume=True)
    assert third["run_id"]=="mock-unit" and calls==[item.sample_id]
    config["gliner"]["threshold"]=.6
    with pytest.raises(ValueError,match="changed"):run(config,run_id="mock-unit",resume=True)


def test_blocked_is_not_attempted_or_zero_latency(config,item):
    gpt=SimpleNamespace(blocked_reason="no key")
    r=execute(item,"B_GPT_DIRECT",config,None,gpt,lambda *args:None)
    assert not r["attempted"] and r["timings"]["latency_e2e_ms"] is None


def test_request_budget_after_retry_keeps_actual_attempt(config,item):
    class Mock429(Exception):
        status_code=429
        response=SimpleNamespace(headers={"retry-after":"0"})
    client=MockClient([Mock429()])
    gpt=GPT55Adapter(config["gpt"],client=client,max_requests=1)
    r=execute(item,"B_GPT_DIRECT",config,None,gpt,lambda *args:None)
    assert r["attempted"] and r["status"]=="request_failed" and r["n_codex_attempts"]==1


def test_report_failure_denominator_and_mock_rejection(tmp_path,gold,item,config):
    from rotowire_bench.reporting import evaluate
    from rotowire_bench.config import ARMS
    write_json(tmp_path/"protocol.lock.json",dict(sample_ids=[item.sample_id],config=config))
    write_jsonl(tmp_path/"evaluation_gold.jsonl",[gold.model_dump()])
    for arm in ARMS:
        write_json(tmp_path/"results"/f"{arm}.json",dict(sample_id=item.sample_id,arm=arm,status="invalid_output",attempted=True,simulated=False,output={"tables":[]},timings={"latency_e2e_ms":10},errors=[],n_codex_attempts=1))
    output=evaluate(tmp_path)
    assert all(s["n_expected"]==1 and s["fact_f1"]==0 and s["n_failed"]==1 for s in output["summary"])
    path=tmp_path/"results"/f"{ARMS[0]}.json";r=read_json(path);r["simulated"]=True;write_json(path,r)
    with pytest.raises(ValueError,match="Mock"):evaluate(tmp_path)


@pytest.mark.integration
def test_real_gliner_validation(config):
    import os
    if os.getenv("RUN_GLINER_INTEGRATION")!="1":pytest.skip("Opt in: RUN_GLINER_INTEGRATION=1")
    from rotowire_bench.models.gliner2_adapter import GLiNER2Adapter
    from rotowire_bench.data import prepared
    inputs,gold,_=prepared(config,"validation")
    adapter=GLiNER2Adapter(config["gliner"],local_files_only=True)
    events=[]
    output=adapter.extract(inputs[0],known_schema(gold[inputs[0].sample_id]),lambda k,v:events.append((k,v)))
    assert isinstance(output,TableOutput)
    assert any(len(table.rows) >= 2 for table in output.tables), "Real validation probe must exercise multiple records"
    request=next(v for k,v in events if k=="gliner_request")
    chunks=request["chunks"]
    assert chunks[0]["start_char"]==0 and chunks[-1]["end_char"]==len(inputs[0].full_text)
    assert len([1 for k,v in events if k=="gliner_chunk"])==len(chunks)
    assert adapter.max_records==19
