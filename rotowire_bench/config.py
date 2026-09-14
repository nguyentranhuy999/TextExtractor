from pathlib import Path
import yaml

ARMS = ["A_GLINER_KNOWN", "A_GPT_KNOWN", "B_HYBRID_SHORT", "B_GPT_DIRECT"]


def load_config(path):
    with Path(path).open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    checks = [
        (config["dataset"]["source"] == "xqwu/text-to-table", "Wrong dataset source"),
        (config["dataset"]["subset"] == "rotowire", "Only RotoWire supported"),
        (config["dataset"]["test_size"] == 200 and config["dataset"]["sample_seed"] == 42, "Main protocol requires 200 samples, seed 42"),
        (config["dataset"]["validation_size"] == 30 and config["dataset"]["validation_seed"] == 43, "Validation requires 30 samples, seed 43"),
        (config["arms"] == ARMS, "Main protocol requires all four arms in canonical order"),
        (config["gliner"]["model"] == "fastino/gliner2-base-v1", "Do not substitute GLiNER2"),
        (config["gliner"]["device"] == "cpu" and config["gliner"]["dtype"] == "float32", "This main protocol is CPU/float32; GPU requires a separately implemented protocol"),
        (config["gliner"]["batch_size"] == 1 and config["gpt"]["concurrency"] == 1, "Sequential benchmark only"),
        (config["gliner"]["cpu_threads"] >= 1 and config["gliner"]["overlap_tokens"] <= 64, "Invalid GLiNER limits"),
        (config["gliner"].get("schema_labels", "semantic") in ("semantic", "opaque"), "Invalid GLiNER schema labels"),
        (config["gliner"].get("schema_descriptions", "full") in ("full", "compact"), "Invalid GLiNER descriptions"),
        (config["gliner"].get("table_execution", "joint") in ("joint", "separate"), "Invalid GLiNER table execution"),
        (config["gpt"]["model"] == "gpt-5.5", "Do not substitute GPT 5.5"),
        (config["gpt"]["reasoning_effort"] == "low", "Main effort is low"),
        (config["gpt"]["execution_mode"] in ("codex_cli", "codex_ui_import"), "Unsupported Codex mode"),
        (config["gpt"]["auth_mode"] == "chatgpt" and config["gpt"]["fresh_session_per_task"] is True, "Fresh ChatGPT sessions required"),
        (config["gpt"]["tool_policy"] == "no_external_tools", "External tools forbidden"),
        (1 <= config["gpt"]["max_attempts"] <= 3, "At most three attempts"),
        (config["gpt"]["timeout_seconds"] > 0, "Timeout must be positive"),
        (config["snippet"] == dict(strategy="center_contiguous", count_unit="whitespace_words",ratio=.1,max_words=80), "Main snippet rule is fixed"),
        (config["run"]["repetitions"] == 1, "Main protocol runs once"),
    ]
    for ok, message in checks:
        if not ok:
            raise ValueError(message)
    return config
