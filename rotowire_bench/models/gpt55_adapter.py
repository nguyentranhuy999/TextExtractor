from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from ..schemas import ProposedExtractionSchema, TableOutput
from ..utils import digest, dumps, utc_now
from .common import ModelError, RequestBudgetReached

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
PROMPTS = {k:(PROMPT_DIR/f"{v}.txt").read_text(encoding="utf-8") for k,v in {
    "known":"known_table", "schema":"short_schema", "direct":"direct_table"}.items()}


def build_request(config, mode, text, schema=None):
    if mode not in PROMPTS or (mode == "known") != (schema is not None):
        raise ValueError("Only known-schema mode may receive schema")
    payload = {"article_fragment" if mode == "schema" else "article": text}
    if schema is not None:
        payload["schema"] = schema.model_dump()
    contract = ProposedExtractionSchema if mode == "schema" else TableOutput
    return dict(model=config["model"], instructions=PROMPTS[mode], input=dumps(payload),
        reasoning={"effort":config["reasoning_effort"]},
        max_output_tokens=config["schema_max_output_tokens" if mode == "schema" else "table_max_output_tokens"],
        store=config["store"], text={"format":{"type":"json_schema", "name": "extraction_schema" if mode == "schema" else "tables", "strict":True, "schema":contract.model_json_schema()}})


def retry_after(headers, attempt, now=None):
    raw = headers.get("retry-after") if headers else None
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(raw)-(now or datetime.now(timezone.utc))).total_seconds())
            except (ValueError, TypeError):
                pass
    return float(2 ** (attempt-1))


class GPT55Adapter:
    def __init__(self, config, *, client=None, max_requests=None, already_used=0):
        self.config = config
        self.blocked_reason = None
        self.max_requests = max_requests
        self.requests_used = already_used
        if client is not None:
            self.client = client
        elif not os.environ.get("OPENAI_API_KEY"):
            self.client = None
            self.blocked_reason = "Missing OPENAI_API_KEY"
        else:
            from openai import OpenAI
            self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=config["base_url"], max_retries=0, timeout=config["timeout_seconds"])

    def request(self, payload, emit):
        if self.blocked_reason:
            raise ModelError("blocked", self.blocked_reason, attempted=False)
        for attempt in range(1, self.config["max_attempts"]+1):
            if self.max_requests is not None and self.requests_used >= self.max_requests:
                raise RequestBudgetReached()
            self.requests_used += 1
            started = time.perf_counter_ns()
            entry = dict(attempt=attempt, utc=utc_now(), request=payload, request_sha256=digest(payload), backend="openai_responses", simulated=False)
            emit("request_started", entry)
            try:
                response = self.client.responses.create(**payload)
            except Exception as exc:
                code = getattr(exc, "status_code", None)
                headers = getattr(getattr(exc, "response", None), "headers", {})
                timeout = "timeout" in type(exc).__name__.lower()
                temporary = code == 429 or code is not None and 500 <= code <= 599 or code is None and (timeout or "connection" in type(exc).__name__.lower())
                should_retry = temporary and attempt < self.config["max_attempts"]
                wait = retry_after(headers, attempt) if should_retry else 0
                # Never log exception repr/body, which can contain authentication data.
                entry.update(status="timeout" if timeout else "request_failed", error_type=type(exc).__name__, status_code=code,
                             duration_ms=(time.perf_counter_ns()-started)/1e6, retry_wait_ms=0.0, retry_wait_planned_ms=wait*1000)
                emit("attempt", entry)
                if code in (401,403,404):
                    self.blocked_reason = f"GPT authentication/model access failure (HTTP {code})"
                if not should_retry:
                    raise ModelError(entry["status"], f"OpenAI request failed: {type(exc).__name__}, HTTP {code}") from exc
                wait_start = time.perf_counter_ns()
                time.sleep(wait)
                entry["retry_wait_ms"] = (time.perf_counter_ns()-wait_start)/1e6
                emit("attempt", entry)
                continue
            entry.update(duration_ms=(time.perf_counter_ns()-started)/1e6, retry_wait_ms=0.0, status="received",
                         response_id=response.id, returned_model=response.model, request_id=getattr(response,"_request_id",None), raw=response.model_dump(mode="json"))
            emit("attempt", entry)
            if response.status != "completed":
                raise ModelError("incomplete", f"Response status: {response.status}")
            for output in response.output:
                for content in getattr(output,"content",[]):
                    if getattr(content,"type",None) == "refusal":
                        raise ModelError("refusal", "Model refused the request")
            # Parsing is deliberately timed in the pipeline's postprocess stage.
            return response.output_text
        raise AssertionError("Unreachable retry state")
