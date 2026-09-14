"""Offline UI task exchange. The exported folder must never be model context."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .models.common import ModelError
from .models.codex_gpt55_adapter import build_request
from .schemas import ProposedExtractionSchema, known_schema, sanitize_output
from .snippets import select_snippet
from .utils import atomic_write, digest, read_json, utc_now, write_json, write_jsonl


class ExternalAdapter:
    def __init__(self, answers_dir=None):
        self.blocked_reason = None
        self.requests_used = 0
        self.max_requests = None
        self.last_audit = None
        self.answers = {}
        if answers_dir and Path(answers_dir).exists():
            self.answers = {(a["sample_id"],a["arm"]):a for p in Path(answers_dir).glob("*.json") for a in [read_json(p)]}

    def set_task(self, sample_id, arm):
        self.task = (sample_id,arm)

    def request(self, payload, emit):
        self.last_audit = None
        answer = self.answers.get(getattr(self,"task",None))
        if answer is None:
            raise ModelError("pending_external", "No imported answer for this task", attempted=False)
        if answer["request_sha256"] != digest(payload):
            raise ModelError("blocked", "Imported request differs from current payload", attempted=False)
        self.last_audit = answer["evidence"]
        entry = dict(attempt=1,request=payload,request_sha256=digest(payload),backend="codex_ui_import",
                     raw_final=answer["raw_final"],status="received",retry_wait_ms=0,
                     duration_ms=None,timing_unavailable_reason="UI measurement unavailable",
                     internal_model_calls=None,internal_retries=None,simulated=False,evidence=answer["evidence"])
        emit("attempt",entry)
        if answer["evidence"].get("tools_used"):
            raise ModelError("protocol_violation", "UI evidence reports forbidden tools")
        return answer["raw_final"]


def export_tasks(config, out, *, split="test", limit=None):
    from .data import prepared
    from .runner import environment, protocol, schedule
    dest = Path(out)
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("Export destination must be new or empty")
    dest.mkdir(parents=True,exist_ok=True)
    ui_config = copy.deepcopy(config)
    ui_config["gpt"]["execution_mode"] = "codex_ui_import"
    ui_config["run"]["output_root"] = str(dest.resolve().parent)
    inputs,gold,manifest = prepared(ui_config,split)
    if limit is not None:
        if split != "validation" or not 1 <= limit <= len(inputs):
            raise ValueError("Only validation export accepts a limit")
        inputs = inputs[:limit]
    ids = [i.sample_id for i in inputs]
    env = environment(ui_config)
    lock = protocol(ui_config,manifest,split,ids,env)
    write_json(dest/"protocol.lock.json",lock)
    write_json(dest/"environment.json",env)
    write_json(dest/"sample_manifest.json",manifest)
    write_jsonl(dest/"inputs.jsonl",[i.model_dump() for i in inputs])
    write_jsonl(dest/"evaluation_gold.jsonl",[gold[s].model_dump() for s in ids])
    write_jsonl(dest/"snippets.jsonl",[dict(sample_id=i.sample_id,**select_snippet(i).to_dict()) for i in inputs])
    write_json(dest/"schedule.json",schedule(ids,config["run"]["order_seed"]))
    write_json(dest/"manual_review.json",dict(ids=[s for s in manifest["manual_review_ids"] if s in ids],status="pending"))
    tasks = []
    for item in inputs:
        for arm,mode in (("A_GPT_KNOWN","known"),("B_HYBRID_SHORT","schema"),("B_GPT_DIRECT","direct")):
            snippet = select_snippet(item)
            if mode == "schema" and snippet.status != "success":
                continue
            payload = build_request(ui_config["gpt"],mode,snippet.text if mode == "schema" else item.full_text,
                                    known_schema(gold[item.sample_id]) if mode == "known" else None)
            task_id = item.sample_id+"__"+arm+"__"+digest(payload)[:16]
            task = dict(task_id=task_id,sample_id=item.sample_id,arm=arm,input_hash=payload["input_hash"],
                        prompt_hash=payload["prompt_hash"],request_sha256=digest(payload),request=payload)
            write_json(dest/"tasks"/(task_id+".json"),task)
            atomic_write(dest/"prompts"/(task_id+".txt"),payload["stdin"]+"\n\nOUTPUT_JSON_SCHEMA:\n"+json.dumps(payload["output_schema"]))
            tasks.append(task)
    write_json(dest/"task_manifest.json",dict(execution_mode="codex_ui_import",protocol_sha256=digest(lock),
                                             tasks=[{k:v for k,v in t.items() if k != "request"} for t in tasks]))
    write_json(dest/"campaign.json",dict(run_id=dest.name,split=split,n_expected=len(ids)*4,n_attempted=0,n_blocked=0,
        complete=False,sessions=[],remaining=[dict(sample_id=s,arm=a) for s,a in schedule(ids)]))
    atomic_write(dest/"UI_INSTRUCTIONS.md", """# Nhập kết quả Codex UI

Mỗi tệp trong `prompts/` là một tác vụ. Mở phiên Codex GPT 5.5 mới, chọn low,
chỉ gửi nội dung một tệp; không gắn thư mục xuất, dữ liệu toàn bài cho tác vụ schema,
SPEC, gold, lịch sử triển khai hoặc kết quả khác. Không dùng công cụ/skills/browse.
Khung JSON được đính kèm về mặt kỹ thuật; đây là chế độ riêng với CLI.

Lưu mỗi câu trả lời thành một tệp JSON trong thư mục answers riêng, theo envelope:
`task_id`, `sample_id`, `arm`, `input_hash`, `prompt_hash` (chép nguyên từ task manifest),
`raw_final` (chuỗi trả lời nguyên bản, không sửa), và `evidence` gồm:
`observed_model: "gpt-5.5"`, `reasoning_effort: "low"`, `auth_mode: "chatgpt"`,
`fresh_session: true`, `context_isolated: true`, `tools_used: false`,
`source` (mô tả bằng chứng thực tế từ giao diện), `session_id` (ID phiên mới riêng).
Nếu không xác minh được bằng chứng, giữ tác vụ chờ; không suy đoán giá trị.

Chạy `python -m rotowire_bench import-results --run-dir THU_MUC_NAY --from-dir ANSWERS`.
Thời gian GPT/hybrid luôn null vì UI không cung cấp phép đo đáng tin cậy.
Không trộn phép đo này với CLI. GLiNER2 sẽ chạy cục bộ khi nhập; các câu trả lời
chưa có vẫn ở trạng thái pending_external. Không gửi bí mật đăng nhập.
""")
    return dict(run_dir=str(dest),n_tasks=len(tasks),execution_mode="codex_ui_import",model_requests=0)


def validate_answer(answer, task):
    for key in ("task_id","sample_id","arm","input_hash","prompt_hash"):
        if answer.get(key) != task[key]:
            raise ValueError("Answer identity/hash mismatch: " + key)
    if not isinstance(answer.get("raw_final"),str):
        raise ValueError("raw_final must preserve the unmodified answer as a string")
    evidence = answer.get("evidence",{})
    expected = dict(observed_model="gpt-5.5",reasoning_effort="low",auth_mode="chatgpt",fresh_session=True,context_isolated=True)
    if any(evidence.get(k) != v for k,v in expected.items()) or not evidence.get("source") or not evidence.get("session_id") or not isinstance(evidence.get("tools_used"),bool):
        raise ValueError("Missing model/auth/context evidence; keep task pending")
    # Invalid model JSON is retained and later scored as a failed attempt, not repaired.
    try:
        if task["arm"] == "B_HYBRID_SHORT":
            ProposedExtractionSchema.model_validate_json(answer["raw_final"])
        else:
            sanitize_output(json.loads(answer["raw_final"]))
        validation = "valid"
    except (ValueError,TypeError,KeyError):
        validation = "invalid_output"
    return dict(**answer,request_sha256=task["request_sha256"],raw_sha256=digest(answer["raw_final"]),
                validation=validation,imported_at=utc_now(),execution_mode="codex_ui_import")


def import_results(run_dir, from_dir, *, local_files_only=False):
    from .runner import campaign_mutex, run, source_hashes
    dest = Path(run_dir).resolve()
    lock = read_json(dest/"protocol.lock.json")
    if lock["config"]["gpt"]["execution_mode"] != "codex_ui_import":
        raise ValueError("UI answers cannot be mixed into a CLI campaign")
    if lock["source_sha256"] != source_hashes():
        raise ValueError("Code changed after task export; create a new export")
    manifest = read_json(dest/"task_manifest.json")
    if manifest["protocol_sha256"] != digest(lock):
        raise ValueError("Task manifest differs from frozen protocol")
    tasks = {t["task_id"]:t for t in manifest["tasks"]}
    with campaign_mutex(dest/".runner.lock"):
        prior = [read_json(p) for p in (dest/"external_answers").glob("*.json")]
        seen = {a["task_id"] for a in prior}
        sessions = {a["evidence"]["session_id"] for a in prior}
        incoming = []
        for path in sorted(Path(from_dir).glob("*.json")):
            answer = read_json(path)
            tid = answer.get("task_id")
            if tid not in tasks or tid in seen:
                raise ValueError("Unknown or duplicate task: " + str(tid))
            result = validate_answer(answer,tasks[tid])
            if result["evidence"]["session_id"] in sessions:
                raise ValueError("A Codex UI session was reused")
            sessions.add(result["evidence"]["session_id"])
            incoming.append(result); seen.add(tid)
        for result in incoming:
            write_json(dest/"external_answers"/(result["task_id"]+".json"),result)
        write_json(dest/"import_status.json",dict(n_imported=len(seen),missing_task_ids=sorted(set(tasks)-seen)))
    return run(lock["config"],run_id=dest.name,resume=True,split=lock["split"],
               limit=len(lock["sample_ids"]) if lock["split"] == "validation" else None,local_files_only=local_files_only)
