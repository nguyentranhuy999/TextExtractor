from __future__ import annotations

import json
import time
from .evaluation import sets
from .models.common import ModelError
from .models.codex_gpt55_adapter import build_request
from .schemas import ProposedExtractionSchema, TableOutput, sanitize_output, schema_from_output
from .snippets import select_snippet
from .utils import digest

SUCCESS = {"success", "empty_prediction"}


def execute(item, arm, config, gliner, gpt, emit, *, known_schema_factory=None, snippet_selector=None):
    """Input has no gold. A's schema factory is the sole explicit privilege."""
    start = time.perf_counter_ns()
    clock = lambda:(time.perf_counter_ns()-start)/1e6
    timings = {key:0.0 for key in ("prepare_ms", "schema_codex_ms", "extract_ms", "postprocess_ms", "retry_wait_ms")}
    schema, output, errors, attempts = None, TableOutput(tables=[]), [], {}
    attempted = False
    forward_passes = 0
    status = "success"
    stage, boundary = "prepare_ms", clock()

    def switch(next_stage):
        nonlocal stage, boundary
        now = clock()
        timings[stage] += now-boundary
        stage, boundary = next_stage, now

    def event(kind, data):
        nonlocal attempted, forward_passes
        if kind in ("request_started", "attempt", "gliner_request", "gliner_chunk"):
            attempted = True
        if kind == "attempt":
            attempts[(data["request_sha256"],data["attempt"])] = data
        if kind == "gliner_chunk":
            forward_passes += 1
        emit(kind, data)

    try:
        if hasattr(gpt, "set_task"):
            gpt.set_task(item.sample_id, arm)
        if arm in ("A_GLINER_KNOWN", "B_HYBRID_SHORT") and gliner is None:
            raise ModelError("blocked", "GLiNER2 unavailable; see preflight.json", attempted=False)
        if arm != "A_GLINER_KNOWN" and gpt.blocked_reason:
            raise ModelError("blocked", gpt.blocked_reason, attempted=False)
        if arm.startswith("A_"):
            if known_schema_factory is None:
                raise ValueError("Known arm requires a schema factory")
            schema = known_schema_factory()
        if arm == "B_HYBRID_SHORT":
            snippet = (snippet_selector or select_snippet)(item)
            event("snippet",snippet.to_dict())
            if snippet.status != "success":
                raise ModelError("insufficient_fragment", "Article has fewer than ten whitespace words")
            request = build_request(config["gpt"],"schema",snippet.text)
            switch("schema_codex_ms")
            raw = gpt.request(request,event)
            switch("postprocess_ms")
            schema = ProposedExtractionSchema.model_validate_json(raw)
            event("predicted_schema",schema.model_dump())
        if arm in ("A_GLINER_KNOWN", "B_HYBRID_SHORT"):
            event("schema",schema.model_dump())
            switch("extract_ms")
            attempted = True
            output = gliner.extract(item,schema,event)
            switch("postprocess_ms")
        else:
            mode = "known" if arm == "A_GPT_KNOWN" else "direct"
            switch("prepare_ms")
            request = build_request(config["gpt"],mode,item.full_text,schema)
            switch("extract_ms")
            raw = gpt.request(request,event)
            switch("postprocess_ms")
            output, errors = sanitize_output(json.loads(raw))
            if arm == "B_GPT_DIRECT":
                # Field names may repeat in a technically readable output. Do not drop its facts.
                schema = schema_from_output(output)
                event("predicted_schema",schema.model_dump())
        normalized = sets(output)
        normalized = {k:sorted(v) if isinstance(v,set) else v for k,v in normalized.items()}
        if not output.tables or not any(t.rows for t in output.tables):
            status = "empty_prediction"
    except ModelError as exc:
        status = "request_failed" if exc.status == "blocked" and attempted else exc.status
        attempted = attempted or exc.attempted
        errors.append(str(exc))
        normalized = None
    except (ValueError, TypeError, KeyError) as exc:
        status = "invalid_output"
        errors.append(f"{type(exc).__name__}: {exc}")
        normalized = None
    except Exception as exc:
        status = "request_failed"
        errors.append(f"Local adapter failure: {type(exc).__name__}: {exc}")
        normalized = None
    switch("postprocess_ms")
    # Stage API/extraction timers included waits. Subtract once; e2e remains untouched.
    wait_schema = sum(a.get("retry_wait_ms",0) for a in attempts.values() if a["request"].get("mode") == "schema")
    wait_extract = sum(a.get("retry_wait_ms",0) for a in attempts.values()) - wait_schema
    timings["schema_codex_ms"] = max(0.0,timings["schema_codex_ms"]-wait_schema)
    timings["extract_ms"] = max(0.0,timings["extract_ms"]-wait_extract)
    timings["retry_wait_ms"] = wait_schema+wait_extract
    # Codex stage time is process launch through exit; rollout auditing and local
    # adapter overhead remain in e2e and are charged to postprocessing.
    if config["gpt"]["execution_mode"] == "codex_cli" and attempts and all(a.get("duration_ms") is not None for a in attempts.values()):
        codex_stage = "schema_codex_ms" if arm == "B_HYBRID_SHORT" else "extract_ms"
        measured = sum(a["duration_ms"] for a in attempts.values())
        timings["postprocess_ms"] += max(0,timings[codex_stage]-measured)
        timings[codex_stage] = measured
    timings["latency_e2e_ms"] = clock() if status not in ("blocked", "pending_external") else None
    if status in ("blocked", "pending_external"):
        timings = {k:None for k in timings}
    execution_mode = "local" if arm == "A_GLINER_KNOWN" else config["gpt"]["execution_mode"]
    timing_unavailable_reason = None
    if execution_mode == "codex_ui_import":
        timings = {k:None for k in timings}
        timing_unavailable_reason = "UI response latency cannot be measured reliably; copy/paste time excluded"
    if status not in SUCCESS:
        output = TableOutput(tables=[])
    return dict(sample_id=item.sample_id,arm=arm,status=status,attempted=attempted and status not in ("blocked", "pending_external"),simulated=False,
        execution_mode=execution_mode,timing_unavailable_reason=timing_unavailable_reason,
        codex_audit=getattr(gpt,"last_audit",None) if attempts else None,
        text_sha256=digest(item.full_text),schema_sha256=digest(schema.model_dump()) if schema is not None else None,
        schema=schema.model_dump() if schema is not None else None,output=output.model_dump(),normalized=normalized,
        timings=timings,errors=errors,n_codex_attempts=len(attempts),n_forward_passes=forward_passes)
