import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_EXPECTED_PATH = BASE_DIR / "Input" / "Target.csv"
DEFAULT_PREDICTED_PATH = BASE_DIR / "Output" / "Table.csv"
DEFAULT_REPORT_PATH = BASE_DIR / "Output" / "evaluation.json"
DEFAULT_IGNORE_COLUMNS = "row_number"


HEADER_ALIASES = {
    "ho ten": "student_name",
    "ho va ten": "student_name",
    "ten sinh vien": "student_name",
    "sinh vien": "student_name",
    "student name": "student_name",
    "name": "student_name",
    "ma sinh vien": "student_id",
    "ma sv": "student_id",
    "ma so sinh vien": "student_id",
    "ma dinh danh sinh vien": "student_id",
    "ma ho so": "student_id",
    "mssv": "student_id",
    "student id": "student_id",
    "id": "student_id",
    "ngay sinh": "date_of_birth",
    "dob": "date_of_birth",
    "date of birth": "date_of_birth",
    "lop": "class",
    "class": "class",
    "khoa": "cohort",
    "khoa hoc": "cohort",
    "cohort": "cohort",
    "diem thanh phan": "process_score",
    "diem mon hoc thanh phan": "process_score",
    "diem qua trinh": "process_score",
    "ket qua qua trinh": "process_score",
    "process score": "process_score",
    "component score": "process_score",
    "diem cuoi ky": "final_score",
    "diem mon hoc cuoi ky": "final_score",
    "diem thi cuoi ky": "final_score",
    "ket qua cuoi ky": "final_score",
    "final score": "final_score",
    "final exam score": "final_score",
    "tong diem": "total_score",
    "diem tong ket": "total_score",
    "diem chung cuoc": "total_score",
    "overall score": "total_score",
    "total score": "total_score",
    "stt": "row_number",
    "row number": "row_number",
    "so thu tu": "row_number",
    "no": "row_number",
    "number": "row_number",
}

KEY_PRIORITY = ["student_id", "id"]

VIETNAMESE_NUMBER_WORDS = {
    "khong": "0",
    "mot": "1",
    "hai": "2",
    "ba": "3",
    "bon": "4",
    "tu": "4",
    "nam": "5",
    "sau": "6",
    "bay": "7",
    "tam": "8",
    "chin": "9",
    "muoi": "10",
}


@dataclass
class Table:
    path: Path
    headers: list[str]
    rows: list[dict[str, str]]
    canonical_to_original: dict[str, str]


def strip_accents(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def loose_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = strip_accents(text)
    text = re.sub(r"[_/\-]+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return collapse_spaces(text)


def canonical_header(header: str) -> str:
    key = loose_key(header)
    return HEADER_ALIASES.get(key, key)


def normalize_cell(value: object) -> str:
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = collapse_spaces(text)
    text = strip_accents(text)

    if text in VIETNAMESE_NUMBER_WORDS:
        return VIETNAMESE_NUMBER_WORDS[text]

    numeric = text.replace(",", ".")
    if re.fullmatch(r"-?\d+(\.\d+)?", numeric):
        if "." in numeric:
            return numeric.rstrip("0").rstrip(".")
        return str(int(numeric))

    date = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if date:
        day, month, year = date.groups()
        if len(year) == 2:
            year = f"20{year}"
        return f"{int(day):02d}/{int(month):02d}/{year}"

    iso_date = re.fullmatch(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
    if iso_date:
        year, month, day = iso_date.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"

    return text


def header_score(row: list[str]) -> int:
    score = 0
    for cell in row:
        if not str(cell).strip():
            continue
        if canonical_header(cell) in {
            "row_number",
            "student_id",
            "student_name",
            "date_of_birth",
            "class",
            "process_score",
            "final_score",
            "total_score",
        }:
            score += 1
    return score


def find_header_row(rows: list[list[str]]) -> int:
    best_index = -1
    best_score = 0

    for row_index, row in enumerate(rows):
        score = header_score(row)
        if score > best_score:
            best_index = row_index
            best_score = score

    if best_index == -1 or best_score < 3:
        print("Could not detect a table header row in the CSV file.", file=sys.stderr)
        raise SystemExit(1)

    return best_index


def build_headers(rows: list[list[str]], header_index: int) -> tuple[list[str], int]:
    base_row = rows[header_index]
    next_row = rows[header_index + 1] if header_index + 1 < len(rows) else []
    max_width = max(len(base_row), len(next_row))
    base_row = base_row + [""] * (max_width - len(base_row))
    next_row = next_row + [""] * (max_width - len(next_row))

    has_key_column = any(canonical_header(cell) == "student_id" for cell in base_row)
    key_column_index = next(
        (index for index, cell in enumerate(base_row) if canonical_header(cell) == "student_id"),
        None,
    )
    next_row_has_key = (
        key_column_index is not None
        and key_column_index < len(next_row)
        and bool(next_row[key_column_index].strip())
    )
    use_continuation_row = has_key_column and not next_row_has_key and any(cell.strip() for cell in next_row)

    headers = []
    last_parent = ""
    for index, parent in enumerate(base_row):
        parent = parent.strip()
        child = next_row[index].strip() if use_continuation_row else ""

        if parent:
            last_parent = parent

        if parent and child and loose_key(parent) != loose_key(child):
            header = f"{parent} {child}"
        elif not parent and child and last_parent:
            header = f"{last_parent} {child}"
        else:
            header = parent or child or f"column_{index + 1}"

        headers.append(header)

    data_start = header_index + 2 if use_continuation_row else header_index + 1
    return headers, data_start


def should_keep_row(row: dict[str, str]) -> bool:
    if not any(str(value).strip() for value in row.values()):
        return False

    if "student_id" in row and not normalize_cell(row.get("student_id", "")):
        return False

    if "row_number" in row:
        row_number = normalize_cell(row.get("row_number", ""))
        if row_number and not re.fullmatch(r"\d+", row_number):
            return False

    return True


def read_csv_table(path: Path) -> Table:
    if not path.exists():
        print(f"CSV file not found: {path}", file=sys.stderr)
        raise SystemExit(1)

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        raw_rows = list(csv.reader(file))
        if not raw_rows:
            print(f"CSV file is empty: {path}", file=sys.stderr)
            raise SystemExit(1)

        header_index = find_header_row(raw_rows)
        headers, data_start = build_headers(raw_rows, header_index)
        canonical_to_original = {}
        for header in headers:
            canonical_to_original.setdefault(canonical_header(header), header)

        rows = []
        for raw_row in raw_rows[data_start:]:
            raw_row = raw_row + [""] * max(0, len(headers) - len(raw_row))
            row = {}
            for index, header in enumerate(headers):
                row[canonical_header(header)] = raw_row[index] if index < len(raw_row) else ""
            if should_keep_row(row):
                rows.append(row)

    return Table(
        path=path,
        headers=headers,
        rows=rows,
        canonical_to_original=canonical_to_original,
    )


def ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def is_unique_key(rows: list[dict[str, str]], column: str) -> bool:
    values = [normalize_cell(row.get(column, "")) for row in rows]
    return bool(values) and all(values) and len(values) == len(set(values))


def choose_key_column(
    expected: Table,
    predicted: Table,
    requested_key: str | None,
    common_columns: set[str],
) -> tuple[str | None, str]:
    if requested_key:
        key = canonical_header(requested_key)
        if key not in common_columns:
            print(f"Key column not found in both CSV files: {requested_key}", file=sys.stderr)
            raise SystemExit(1)
        return key, "manual"

    for key in KEY_PRIORITY:
        if key in common_columns and is_unique_key(expected.rows, key) and is_unique_key(predicted.rows, key):
            return key, "auto"

    candidates = [
        column
        for column in common_columns
        if is_unique_key(expected.rows, column) and is_unique_key(predicted.rows, column)
    ]
    if candidates:
        candidates.sort(key=lambda column: expected.canonical_to_original.get(column, column))
        return candidates[0], "auto"

    return None, "position"


def index_rows(rows: list[dict[str, str]], key_column: str) -> dict[str, tuple[int, dict[str, str]]]:
    index = {}
    for row_index, row in enumerate(rows):
        key = normalize_cell(row.get(key_column, ""))
        index[key] = (row_index, row)
    return index


def pair_rows(
    expected: Table,
    predicted: Table,
    key_column: str | None,
) -> tuple[list[tuple[str, int, int, dict[str, str], dict[str, str]]], list[str], list[str]]:
    if key_column:
        expected_index = index_rows(expected.rows, key_column)
        predicted_index = index_rows(predicted.rows, key_column)
        expected_keys = set(expected_index)
        predicted_keys = set(predicted_index)

        pairs = []
        for key in sorted(expected_keys & predicted_keys):
            expected_index_value, expected_row = expected_index[key]
            predicted_index_value, predicted_row = predicted_index[key]
            pairs.append((key, expected_index_value, predicted_index_value, expected_row, predicted_row))

        missing_rows = sorted(expected_keys - predicted_keys)
        extra_rows = sorted(predicted_keys - expected_keys)
        return pairs, missing_rows, extra_rows

    pair_count = min(len(expected.rows), len(predicted.rows))
    pairs = [
        (
            str(row_index + 1),
            row_index,
            row_index,
            expected.rows[row_index],
            predicted.rows[row_index],
        )
        for row_index in range(pair_count)
    ]
    missing_rows = [str(row_index + 1) for row_index in range(pair_count, len(expected.rows))]
    extra_rows = [str(row_index + 1) for row_index in range(pair_count, len(predicted.rows))]
    return pairs, missing_rows, extra_rows


def evaluate(expected: Table, predicted: Table, key_column: str | None, max_examples: int) -> dict:
    return evaluate_tables(expected, predicted, key_column, max_examples, set())


def evaluate_tables(
    expected: Table,
    predicted: Table,
    key_column: str | None,
    max_examples: int,
    ignored_columns: set[str],
) -> dict:
    expected_columns = set(expected.canonical_to_original) - ignored_columns
    predicted_columns = set(predicted.canonical_to_original) - ignored_columns
    common_columns = expected_columns & predicted_columns
    missing_columns = sorted(expected_columns - predicted_columns)
    extra_columns = sorted(predicted_columns - expected_columns)

    selected_key, key_mode = choose_key_column(expected, predicted, key_column, common_columns)
    row_pairs, missing_rows, extra_rows = pair_rows(expected, predicted, selected_key)

    matched_cells = 0
    compared_common_cells = 0
    matched_expected_cells = 0
    expected_cell_total = len(expected.rows) * len(expected_columns)
    row_exact_matches = 0
    column_stats = {
        column: {"matches": 0, "mismatches": 0}
        for column in sorted(expected_columns)
    }
    mismatch_examples = []

    for row_key, expected_index, predicted_index, expected_row, predicted_row in row_pairs:
        row_is_exact = True

        for column in expected_columns:
            expected_value = expected_row.get(column, "")
            predicted_value = predicted_row.get(column, "") if column in predicted_columns else ""
            values_match = (
                column in predicted_columns
                and normalize_cell(expected_value) == normalize_cell(predicted_value)
            )

            if values_match:
                matched_expected_cells += 1
                column_stats[column]["matches"] += 1
            else:
                row_is_exact = False
                column_stats[column]["mismatches"] += 1
                if len(mismatch_examples) < max_examples:
                    mismatch_examples.append(
                        {
                            "row": row_key,
                            "expected_row_number": expected_index + 1,
                            "predicted_row_number": predicted_index + 1,
                            "column": expected.canonical_to_original.get(column, column),
                            "expected": expected_value,
                            "predicted": predicted_value,
                        }
                    )

            if column in common_columns:
                compared_common_cells += 1
                if values_match:
                    matched_cells += 1

        if row_is_exact and not missing_columns:
            row_exact_matches += 1

    column_precision = ratio(len(common_columns), len(predicted_columns))
    column_recall = ratio(len(common_columns), len(expected_columns))
    column_f1 = f1_score(column_precision, column_recall)

    row_precision = ratio(len(row_pairs), len(predicted.rows))
    row_recall = ratio(len(row_pairs), len(expected.rows))
    row_f1 = f1_score(row_precision, row_recall)

    common_cell_accuracy = ratio(matched_cells, compared_common_cells)
    coverage_cell_accuracy = ratio(matched_expected_cells, expected_cell_total)
    exact_row_accuracy = ratio(row_exact_matches, len(expected.rows))
    overall_score = (0.2 * column_f1) + (0.2 * row_f1) + (0.6 * coverage_cell_accuracy)

    worst_columns = []
    for column, stats in column_stats.items():
        total = stats["matches"] + stats["mismatches"]
        if total == 0:
            continue
        accuracy = ratio(stats["matches"], total)
        worst_columns.append(
            {
                "column": expected.canonical_to_original.get(column, column),
                "accuracy": accuracy,
                "matches": stats["matches"],
                "mismatches": stats["mismatches"],
            }
        )
    worst_columns.sort(key=lambda item: (item["accuracy"], -item["mismatches"], item["column"]))

    return {
        "expected_path": str(expected.path),
        "predicted_path": str(predicted.path),
        "key_column": selected_key,
        "key_mode": key_mode,
        "columns": {
            "expected_count": len(expected_columns),
            "predicted_count": len(predicted_columns),
            "matched_count": len(common_columns),
            "missing": [expected.canonical_to_original.get(column, column) for column in missing_columns],
            "extra": [predicted.canonical_to_original.get(column, column) for column in extra_columns],
            "precision": column_precision,
            "recall": column_recall,
            "f1": column_f1,
        },
        "rows": {
            "expected_count": len(expected.rows),
            "predicted_count": len(predicted.rows),
            "matched_count": len(row_pairs),
            "missing_count": len(missing_rows),
            "extra_count": len(extra_rows),
            "missing_keys": missing_rows[:max_examples],
            "extra_keys": extra_rows[:max_examples],
            "precision": row_precision,
            "recall": row_recall,
            "f1": row_f1,
            "exact_row_accuracy": exact_row_accuracy,
        },
        "cells": {
            "matched_common_cells": matched_cells,
            "compared_common_cells": compared_common_cells,
            "matched_expected_cells": matched_expected_cells,
            "expected_cell_total": expected_cell_total,
            "common_cell_accuracy": common_cell_accuracy,
            "coverage_cell_accuracy": coverage_cell_accuracy,
        },
        "overall_score": overall_score,
        "ignored_columns": sorted(ignored_columns),
        "worst_columns": worst_columns[:max_examples],
        "mismatch_examples": mismatch_examples,
    }


def print_report(report: dict) -> None:
    print("Evaluation result")
    print(f"Expected : {report['expected_path']}")
    print(f"Predicted: {report['predicted_path']}")

    key_column = report["key_column"] or "row position"
    print(f"Row match: {key_column} ({report['key_mode']})")
    if report["ignored_columns"]:
        print(f"Ignored columns: {', '.join(report['ignored_columns'])}")
    print()

    columns = report["columns"]
    rows = report["rows"]
    cells = report["cells"]

    print(f"Overall score              : {format_percent(report['overall_score'])}")
    print(f"Column F1                  : {format_percent(columns['f1'])}")
    print(f"Row F1                     : {format_percent(rows['f1'])}")
    print(f"Cell accuracy, common cols : {format_percent(cells['common_cell_accuracy'])}")
    print(f"Cell accuracy, coverage    : {format_percent(cells['coverage_cell_accuracy'])}")
    print(f"Exact row accuracy         : {format_percent(rows['exact_row_accuracy'])}")
    print()

    print(
        "Columns: "
        f"{columns['matched_count']}/{columns['expected_count']} expected columns matched "
        f"({columns['predicted_count']} predicted)"
    )
    print(
        "Rows   : "
        f"{rows['matched_count']}/{rows['expected_count']} expected rows matched "
        f"({rows['predicted_count']} predicted)"
    )
    print()

    if columns["missing"]:
        print("Missing columns:")
        for column in columns["missing"]:
            print(f"- {column}")
        print()

    if columns["extra"]:
        print("Extra columns:")
        for column in columns["extra"]:
            print(f"- {column}")
        print()

    if rows["missing_keys"]:
        print("Missing rows:")
        for row_key in rows["missing_keys"]:
            print(f"- {row_key}")
        print()

    if rows["extra_keys"]:
        print("Extra rows:")
        for row_key in rows["extra_keys"]:
            print(f"- {row_key}")
        print()

    if report["worst_columns"]:
        print("Lowest-accuracy columns:")
        for item in report["worst_columns"]:
            print(
                f"- {item['column']}: {format_percent(item['accuracy'])} "
                f"({item['matches']} match, {item['mismatches']} mismatch)"
            )
        print()

    if report["mismatch_examples"]:
        print("Mismatch examples:")
        for item in report["mismatch_examples"]:
            print(
                f"- Row {item['row']}, column {item['column']}: "
                f"expected {item['expected']!r}, got {item['predicted']!r}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate how well a generated CSV table matches a reference CSV table."
    )
    parser.add_argument(
        "--expected",
        default=str(DEFAULT_EXPECTED_PATH),
        help="Reference CSV path. Default: Code/Input/Target.csv",
    )
    parser.add_argument(
        "--predicted",
        default=str(DEFAULT_PREDICTED_PATH),
        help="Generated CSV path. Default: Code/Output/Table.csv",
    )
    parser.add_argument(
        "--key-column",
        default=None,
        help="Column used to match rows. If omitted, the script auto-detects a unique key.",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT_PATH),
        help="JSON report path. Default: Code/Output/evaluation.json",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Print results only and do not write a JSON report.",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=10,
        help="Maximum number of rows, columns, and mismatch examples to print.",
    )
    parser.add_argument(
        "--ignore-columns",
        default=DEFAULT_IGNORE_COLUMNS,
        help=(
            "Comma-separated columns to ignore during evaluation. "
            "Default: row_number. Use an empty string to compare all columns."
        ),
    )
    return parser.parse_args()


def parse_ignored_columns(raw_value: str) -> set[str]:
    if not raw_value.strip():
        return set()
    return {
        canonical_header(column)
        for column in raw_value.split(",")
        if column.strip()
    }


def main() -> None:
    args = parse_args()
    expected_path = Path(args.expected).expanduser().resolve()
    predicted_path = Path(args.predicted).expanduser().resolve()

    expected = read_csv_table(expected_path)
    predicted = read_csv_table(predicted_path)
    ignored_columns = parse_ignored_columns(args.ignore_columns)
    report = evaluate_tables(expected, predicted, args.key_column, args.max_examples, ignored_columns)
    print_report(report)

    if not args.no_report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print()
        print(f"Saved JSON report: {report_path}")


if __name__ == "__main__":
    main()
