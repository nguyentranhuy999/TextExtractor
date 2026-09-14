"""Synthetic mocked CLI transport tests; never performance measurements."""
import copy
import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from rotowire_bench.models.codex_gpt55_adapter import CodexGPT55Adapter, audit_rollout, build_request, child_environment, terminate_group
from rotowire_bench.models.common import ModelError
from rotowire_bench.external_tasks import validate_answer, ExternalAdapter, export_tasks, import_results
from rotowire_bench.pipelines import execute
from rotowire_bench.utils import digest, read_json, write_json


def mock_records(payload,cwd,version,model="gpt-5.5",extra=None):
    r = [dict(type="session_meta",payload=dict(source="exec",cli_version=version,base_instructions={"text":"mock fixed instructions"})),
         dict(type="turn_context",payload=dict(model=model,effort="low",cwd=cwd)),
         dict(type="world_state",payload={"state":{}}),
         dict(type="response_item",payload=dict(type="message",role="developer",content=[{"text":"mock permissions"}])),
         dict(type="response_item",payload=dict(type="message",role="user",content=[{"text":"<environment_context>mock</environment_context>"}])),
         dict(type="response_item",payload=dict(type="message",role="user",content=[{"text":payload["stdin"]}]))]
    return r + (extra or [])


@pytest.fixture
def transport(config,monkeypatch):
    import rotowire_bench.models.codex_gpt55_adapter as module
    cfg=copy.deepcopy(config["gpt"]);cfg.pop("context_sha256",None)
    adapter=CodexGPT55Adapter(cfg);adapter.executable="mock-codex";adapter.cli_version=cfg["codex_cli_version"]
    pending=[]; launches=[]; records={}
    class MockProcess:
        def __init__(self,cmd,**kwargs):
            self.cmd,self.kwargs=cmd,kwargs;self.returncode=0
            launches.append(self)
        def communicate(self,stdin=None,timeout=None):
            self.stdin=stdin
            behavior=pending.pop(0) if pending else {}
            cwd=self.cmd[self.cmd.index("-C")+1]
            payload={"stdin":stdin}
            sid=str(uuid.uuid4())
            records[sid]=mock_records(payload,cwd,adapter.cli_version,model=behavior.get("model","gpt-5.5"))
            if behavior.get("history"):
                records[sid].append(dict(type="response_item",payload=dict(type="message",role="user",content=[{"text":"mock previous task GOLD"}])))
            self.returncode=behavior.get("exit_code",0)
            events=[dict(type="thread.started",thread_id=sid),dict(type="turn.started")]
            if behavior.get("error"):
                events.append(dict(type="error",message=behavior["error"]))
            if behavior.get("tool"):
                events.append(dict(type="item.completed",item={"type":"command_execution","command":"cat forbidden"}))
            if not self.returncode:
                events.append(dict(type="turn.completed"))
                Path(self.cmd[self.cmd.index("-o")+1]).write_text(behavior.get("final",'{"tables":[]}'))
            return "\n".join(json.dumps(e) for e in events),""
    monkeypatch.setattr(module.subprocess,"Popen",MockProcess)
    monkeypatch.setattr(adapter,"_records",lambda sid:records.get(sid,[]))
    return adapter,pending,launches


def test_mock_cli_fresh_sessions_and_allowed_files(transport,config,item):
    adapter,pending,launches=transport
    payload=build_request(config["gpt"],"schema","only fragment")
    events=[]
    for _ in range(2):
        assert adapter.request(payload,lambda k,v:events.append((k,copy.deepcopy(v))))=='{"tables":[]}'
    attempts=[v for k,v in events if k=="attempt"]
    assert attempts[0]["session_id"]!=attempts[1]["session_id"]
    assert len({p.kwargs["cwd"] for p in launches})==2
    for p in launches:
        assert "resume" not in p.cmd and "fork" not in p.cmd and p.cmd[-1]=="-"
        assert "--ignore-user-config" in p.cmd and "--ignore-rules" not in p.cmd
        assert p.kwargs["start_new_session"] and p.stdin==payload["stdin"]
        assert item.full_text not in p.stdin and "article_fragment" in p.stdin
    assert all(a["audit"]["status"]=="verified" and a["internal_model_calls"] is None for a in attempts)


@pytest.mark.parametrize("behavior",[{"model":"gpt-other"},{"history":True},{"tool":True}])
def test_mock_protocol_violation_no_retry(transport,config,behavior):
    adapter,pending,launches=transport;pending.append(behavior)
    with pytest.raises(ModelError) as error:
        adapter.request(build_request(config["gpt"],"direct","synthetic source"),lambda *args:None)
    assert error.value.status=="protocol_violation" and len(launches)==1


def test_mock_retry_and_budget_preserve_failure(transport,config,item):
    adapter,pending,launches=transport
    pending.extend([{"exit_code":1,"error":"rate limit exceeded; retry-after: 0"},{}])
    events=[]
    adapter.request(build_request(config["gpt"],"direct",item.full_text),lambda k,v:events.append((k,copy.deepcopy(v))))
    assert len(launches)==2 and adapter.requests_used==2
    assert len({v["session_id"] for k,v in events if k=="attempt"})==2
    adapter.max_requests=3
    pending.append({"exit_code":1,"error":"rate limit exceeded; retry-after: 0"})
    result=execute(item,"B_GPT_DIRECT",config,None,adapter,lambda *args:None)
    assert result["attempted"] and result["status"]=="request_failed" and result["n_codex_attempts"]==1


def test_mock_quota_blocks_remaining_branch(transport,config,item):
    adapter,pending,launches=transport
    pending.append({"exit_code":1,"error":"You've hit your usage limit"})
    result=execute(item,"B_GPT_DIRECT",config,None,adapter,lambda *args:None)
    later=execute(item,"B_GPT_DIRECT",config,None,adapter,lambda *args:None)
    assert result["attempted"] and not later["attempted"] and later["status"]=="blocked"
    assert len(launches)==1 and later["codex_audit"] is None


def test_mock_login_checks_chatgpt_without_reading_secret(config,monkeypatch):
    import rotowire_bench.models.codex_gpt55_adapter as module
    monkeypatch.setattr(module.shutil,"which",lambda _:"mock-codex")
    def run(cmd,**kwargs):
        return SimpleNamespace(returncode=0,stdout="codex-cli "+config["gpt"]["codex_cli_version"] if "--version" in cmd else "Logged in using an API key",stderr="")
    monkeypatch.setattr(module.subprocess,"run",run)
    adapter=CodexGPT55Adapter(config["gpt"])
    assert adapter.inspect()["status"]=="blocked"
    monkeypatch.setenv("OPENAI_API_KEY","mock-secret");monkeypatch.setenv("CODEX_THREAD_ID","mock-parent")
    monkeypatch.setenv("CODEX_PERMISSION_PROFILE","mock-mandatory")
    env=child_environment()
    assert "OPENAI_API_KEY" not in env and "CODEX_THREAD_ID" not in env and env["CODEX_PERMISSION_PROFILE"]=="mock-mandatory"


def test_mock_timeout_terminates_process_group(monkeypatch):
    import rotowire_bench.models.codex_gpt55_adapter as module
    kills=[]
    monkeypatch.setattr(module.os,"killpg",lambda pid,sig:kills.append((pid,sig)))
    class Process:
        pid=456
        calls=0
        def communicate(self,timeout=None):
            self.calls+=1
            if self.calls==1:raise subprocess.TimeoutExpired("mock",5)
            return "partial events","mock stderr"
    assert terminate_group(Process())==("partial events","mock stderr")
    assert len(kills)==2 and all(pid==456 for pid,_ in kills)


def test_mock_context_drift_rejected(config):
    p=build_request(config["gpt"],"schema","mock fragment")
    r=mock_records(p,"/tmp/mock","mock-version")
    first=audit_rollout(r,[],p,"/tmp/mock","mock-version")
    r[3]["payload"]["content"][0]["text"]+=" new data"
    changed=audit_rollout(r,[],p,"/tmp/mock","mock-version",first["context_sha256"])
    assert changed["status"]=="protocol_violation"


def answer_fixture(task,raw='{"tables":[]}'):
    return dict(**{k:task[k] for k in ("task_id","sample_id","arm","input_hash","prompt_hash")},raw_final=raw,
                evidence=dict(observed_model="gpt-5.5",reasoning_effort="low",auth_mode="chatgpt",fresh_session=True,
                              context_isolated=True,tools_used=False,source="mock UI fixture, not performance",session_id="mock-new-session"))


def test_mock_ui_hash_raw_and_missing_time(config,item,tmp_path):
    payload=build_request(config["gpt"],"direct",item.full_text)
    task=dict(task_id="mock-task",sample_id=item.sample_id,arm="B_GPT_DIRECT",input_hash=payload["input_hash"],prompt_hash=payload["prompt_hash"],request_sha256=digest(payload))
    answer=answer_fixture(task, ' {"tables":[]} \n')
    result=validate_answer(answer,task)
    assert result["raw_final"]==answer["raw_final"]
    wrong=copy.deepcopy(answer);wrong["input_hash"]="wrong"
    with pytest.raises(ValueError,match="mismatch"):validate_answer(wrong,task)
    broken=answer_fixture(task,'{"tables":[')
    assert validate_answer(broken,task)["validation"]=="invalid_output"
    write_json(tmp_path/"answer.json",result)
    adapter=ExternalAdapter(tmp_path);config["gpt"]["execution_mode"]="codex_ui_import"
    scored=execute(item,"B_GPT_DIRECT",config,None,adapter,lambda *args:None)
    assert scored["attempted"] and scored["status"]=="empty_prediction"
    assert all(v is None for v in scored["timings"].values()) and scored["timing_unavailable_reason"]
    missing=execute(item,"A_GPT_KNOWN",config,None,ExternalAdapter(),lambda *args:None,known_schema_factory=lambda:None)
    assert not missing["attempted"]


def test_mock_ui_export_import_duplicate_and_mode(config,tmp_path,monkeypatch,item,gold):
    import rotowire_bench.data as data
    import rotowire_bench.runner as runner
    monkeypatch.setattr(data,"prepared",lambda *args:([item],{item.sample_id:gold},{"manual_review_ids":[]}))
    out=tmp_path/"ui"
    exported=export_tasks(config,out)
    assert exported["n_tasks"]==3 and exported["model_requests"]==0
    tasks=read_json(out/"task_manifest.json")["tasks"]
    hybrid=next(t for t in tasks if t["arm"]=="B_HYBRID_SHORT")
    payload=read_json(out/"tasks"/(hybrid["task_id"]+".json"))["request"]
    assert item.full_text not in payload["stdin"] and "schema" not in json.loads(payload["input"])
    answers=tmp_path/"answers";answers.mkdir()
    write_json(answers/"a.json",answer_fixture(tasks[0]))
    monkeypatch.setattr(runner,"run",lambda *args,**kwargs:{"mock":True})
    assert import_results(out,answers)=={"mock":True}
    assert len(read_json(out/"import_status.json")["missing_task_ids"])==2
    with pytest.raises(ValueError,match="duplicate"):import_results(out,answers)
    lock=read_json(out/"protocol.lock.json");lock["config"]["gpt"]["execution_mode"]="codex_cli";write_json(out/"protocol.lock.json",lock)
    with pytest.raises(ValueError,match="mixed"):import_results(out,answers)
