import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "Input" / "Document.txt"
DEFAULT_OUTPUT_PATH = BASE_DIR / "Output" / "Table.csv"
DEFAULT_MODEL = "~openai/gpt-latest"
DEFAULT_MAX_TOKENS = 12000
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def require_openrouter_client():
    try:
        from openai import OpenAI
    except ImportError:
        print(
            "Missing package: openai\n"
            "Install it with: python3 -m pip install openai",
            file=sys.stderr,
        )
        raise SystemExit(1)

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(
            "Missing OPENROUTER_API_KEY.\n"
            "Add it to Code/.env, for example:\n"
            "OPENROUTER_API_KEY=your_openrouter_api_key_here",
            file=sys.stderr,
        )
        raise SystemExit(1)

    default_headers = {}
    if os.getenv("OPENROUTER_HTTP_REFERER"):
        default_headers["HTTP-Referer"] = os.getenv("OPENROUTER_HTTP_REFERER")
    if os.getenv("OPENROUTER_APP_TITLE"):
        default_headers["X-OpenRouter-Title"] = os.getenv("OPENROUTER_APP_TITLE")

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
        default_headers=default_headers or None,
    )


def getenv_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        value = int(raw_value)
    except ValueError:
        print(f"{name} must be an integer. Current value: {raw_value}", file=sys.stderr)
        raise SystemExit(1)

    if value <= 0:
        print(f"{name} must be greater than 0. Current value: {value}", file=sys.stderr)
        raise SystemExit(1)

    return value


def extract_json(text: str) -> dict:
    cleaned = text.strip()

    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def normalize_table(payload: dict) -> tuple[list[str], list[list[str]]]:
    columns = payload.get("columns")
    rows = payload.get("rows")

    if not isinstance(columns, list) or not columns:
        raise ValueError("Model response must contain a non-empty 'columns' list.")
    if not isinstance(rows, list):
        raise ValueError("Model response must contain a 'rows' list.")

    columns = [str(column).strip() for column in columns]
    normalized_rows = []

    for row in rows:
        if isinstance(row, dict):
            normalized_rows.append([clean_cell(row.get(column, "")) for column in columns])
        elif isinstance(row, list):
            padded = row[: len(columns)] + [""] * max(0, len(columns) - len(row))
            normalized_rows.append([clean_cell(value) for value in padded])
        else:
            raise ValueError("Each row must be an object or a list.")

    return columns, normalized_rows


def clean_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def build_prompt(document: str) -> str:
    return f"""
Extract the important structured data from the document below and convert it into one clean table.

Rules:
- Return JSON only. Do not include Markdown.
- Use this exact JSON shape: {{"columns": ["column name"], "rows": [{{"column name": "value"}}]}}
- Choose concise, human-readable column names.
- Preserve numbers, dates, names, units, and identifiers exactly when possible.
- If the document has multiple related records, create one row per record.
- If the document has only one entity or summary, create one row with the most useful fields.
- Leave unknown cells as empty strings.

Document:
{document}
""".strip()


def call_llm(client, model: str, document: str, max_tokens: int) -> dict:
    prompt = build_prompt(document)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You convert unstructured text into accurate CSV-ready JSON tables.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=max_tokens,
        )
    except Exception as error:
        error_text = str(error)
        if "Error code: 402" in error_text or "requires more credits" in error_text:
            print(
                "OpenRouter rejected the request because the key does not have enough credits "
                "for this model and token limit.",
                file=sys.stderr,
            )
            print(
                "Try one of these: add credits/increase the key limit, use a cheaper model, "
                "or lower OPENROUTER_MAX_TOKENS in Code/.env.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        raise

    content = response.choices[0].message.content
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))

    return extract_json(content or "")


def write_csv(output_path: Path, columns: list[str], rows: list[list[str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Code/Input/Document.txt into Code/Output/Table.csv using OpenRouter."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT_PATH), help="Path to Document.txt")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to Table.csv")
    parser.add_argument(
        "--model",
        default=os.getenv("OPENROUTER_MODEL") or os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        help="OpenRouter model slug. Can also be set with OPENROUTER_MODEL in Code/.env",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=getenv_int("OPENROUTER_MAX_TOKENS", DEFAULT_MAX_TOKENS),
        help="Maximum number of output tokens to request from OpenRouter.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    load_dotenv(BASE_DIR.parent / ".env")

    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        print("Create Code/Input/Document.txt and run again.", file=sys.stderr)
        raise SystemExit(1)

    document = input_path.read_text(encoding="utf-8").strip()
    if not document:
        print(f"Input file is empty: {input_path}", file=sys.stderr)
        raise SystemExit(1)

    client = require_openrouter_client()
    payload = call_llm(client, args.model, document, args.max_tokens)
    columns, rows = normalize_table(payload)
    write_csv(output_path, columns, rows)

    print(f"Saved table with {len(rows)} row(s) and {len(columns)} column(s): {output_path}")


if __name__ == "__main__":
    main()
