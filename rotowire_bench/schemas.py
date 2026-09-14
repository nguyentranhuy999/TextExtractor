from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InferenceInput(Contract):
    sample_id: str
    full_text: str


class SchemaField(Contract):
    name: str = Field(min_length=1)
    description: str
    value_type: Literal["number", "string", "percentage"]
    unit: str | None


class SchemaTable(Contract):
    table_name: str = Field(min_length=1)
    entity_type: str
    identity_field: Literal["entity_name"]
    fields: list[SchemaField]

    @model_validator(mode="after")
    def unique_fields(self):
        names = [f.name.casefold().strip() for f in self.fields]
        if len(set(names)) != len(names) or "entity_name" in names:
            raise ValueError("Duplicate or reserved field name")
        return self


class ExtractionSchema(Contract):
    tables: list[SchemaTable]

    @model_validator(mode="after")
    def unique_tables(self):
        names = [t.table_name.casefold().strip() for t in self.tables]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate table name")
        return self


class ProposedSchemaField(SchemaField):
    # Human-readable labels also make the reserved underscore key impossible in
    # the constrained decoder. Keep the generic/known schema contract unchanged.
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9 -]*$",
        description="Unique readable English attribute label using letters, digits, spaces or hyphens; never an identity/name attribute.")
    description: str = Field(description="Brief meaning, entity scope and time scope supported by the fragment; no observed names or values.")


class ProposedSchemaTable(SchemaTable):
    table_name: str = Field(min_length=1, description="Short singular noun for the entity kind, matching entity_type; no report titles or statistics/assessment suffixes.")
    identity_field: Literal["entity_name"] = Field(description="The sole record identity key; it is automatically added by the extractor and must not appear in fields.")
    fields: list[ProposedSchemaField] = Field(description="Non-identity attributes only, with unique names; merge synonyms only when entity and time scopes match.")


class ProposedExtractionSchema(ExtractionSchema):
    """Stricter generation contract for the short-fragment hybrid only."""
    tables: list[ProposedSchemaTable]


class Cell(Contract):
    field_name: str
    raw_values: list[str]


class Row(Contract):
    entity_name: str
    cells: list[Cell]


class Table(Contract):
    table_name: str
    entity_type: str
    field_names: list[str]
    rows: list[Row]


class TableOutput(Contract):
    tables: list[Table]


class EvaluationGold(Contract):
    sample_id: str
    original_index: int
    tables: TableOutput
    game_key: str | None = None


def known_schema(gold: EvaluationGold) -> ExtractionSchema:
    """The only inference-bound function allowed to inspect gold (headers only)."""
    return ExtractionSchema(tables=[SchemaTable(
        table_name=t.table_name, entity_type=t.entity_type, identity_field="entity_name",
        fields=[SchemaField(name=n, description=f"{n}; reported game.",
                            value_type="percentage" if "percentage" in n.casefold() else "number",
                            unit="percent" if "percentage" in n.casefold() else None)
                for n in t.field_names]) for t in gold.tables.tables])


def schema_from_output(output: TableOutput) -> ExtractionSchema:
    groups = {}
    for table in output.tables:
        key = table.table_name.casefold().strip()
        entry = groups.setdefault(key, dict(table_name=table.table_name, entity_type=table.entity_type, fields={}))
        for name in table.field_names:
            if name.strip() and name.casefold().strip() != "entity_name":
                entry["fields"].setdefault(name.casefold().strip(), SchemaField(name=name, description=name, value_type="string", unit=None))
    return ExtractionSchema(tables=[SchemaTable(table_name=g["table_name"],entity_type=g["entity_type"],identity_field="entity_name",fields=list(g["fields"].values())) for g in groups.values()])


def sanitize_output(payload: dict) -> tuple[TableOutput, list[str]]:
    """Only cell-local damage is salvageable; broken document structure fails."""
    if not isinstance(payload, dict) or not isinstance(payload.get("tables"), list):
        raise ValueError("Invalid document: tables must be a list")
    errors, tables = [], []
    for ti, raw in enumerate(payload["tables"]):
        if not isinstance(raw, dict):
            raise ValueError("Invalid table")
        shell = {**raw, "rows": []}
        table = Table.model_validate(shell)
        if not isinstance(raw.get("rows"), list):
            raise ValueError("Invalid rows")
        for ri, r in enumerate(raw["rows"]):
            if not isinstance(r, dict) or not isinstance(r.get("cells"), list):
                errors.append(f"table[{ti}].row[{ri}]: invalid row")
                continue
            entity = r.get("entity_name")
            if not isinstance(entity, str) or not entity.strip():
                entity = f"__unresolved_{ti}_{ri}"
                errors.append(f"table[{ti}].row[{ri}]: missing identity")
            cells = []
            for ci, c in enumerate(r["cells"]):
                try:
                    cell = Cell.model_validate(c)
                except ValueError:
                    errors.append(f"table[{ti}].row[{ri}].cell[{ci}]: invalid cell")
                    continue
                if cell.field_name not in table.field_names:
                    errors.append(f"table[{ti}].row[{ri}].cell[{ci}]: undeclared field {cell.field_name}")
                cells.append(cell)
            table.rows.append(Row(entity_name=entity, cells=cells))
        tables.append(table)
    return TableOutput(tables=tables), errors


def gliner_schema(schema: ExtractionSchema, model, *, labels="semantic", descriptions="full"):
    """Builder API uses descriptions as data, never as :: parsing syntax."""
    builder = model.create_schema()
    reverse = {}
    if labels not in ("semantic", "opaque") or descriptions not in ("full", "compact"):
        raise ValueError("Unknown GLiNER schema representation")
    def description(text):
        # Prevent free-form schema text from injecting encoder separator tokens.
        import re
        return re.sub(r"\[([A-Z_]+)\]", r"(\1)", text)
    def semantic_key(text, used):
        # Keep readable labels; remove encoder/parser syntax without replacing
        # the label's meaning by an opaque positional identifier.
        import re
        key = " ".join(re.sub(r"[^\w\s-]", " ", text).split()) or "attribute"
        base, suffix = key, 2
        while key.casefold() in used:
            key = f"{base} {suffix}"
            suffix += 1
        used.add(key.casefold())
        return key
    table_keys = set()
    for ti, table in enumerate(schema.tables):
        name = {"players": "player", "teams": "team"}.get(table.table_name, table.table_name)
        key = f"t{ti}" if labels == "opaque" else semantic_key(name, table_keys)
        record = builder.structure(key)
        identity = f"Name of {table.entity_type} ({table.table_name}). Reported game, explicit facts only; no other games, season averages, predictions or derived values."
        if descriptions == "compact":
            identity = f"{table.entity_type} name; current game, explicit facts only; exclude season averages, predictions and derived values."
        record.field("entity_name", dtype="str", description=description(identity))
        mapping = {}
        field_keys = {"entity_name"}
        for fi, field in enumerate(table.fields):
            safe = f"f{fi}" if labels == "opaque" else semantic_key(field.name, field_keys)
            meaning = field.description if field.description.startswith(field.name) else f"{field.name}. {field.description}"
            unit = f"; unit: {field.unit}" if field.unit is not None else ""
            text = f"{table.table_name}: {meaning} Type: {field.value_type}{unit}."
            if descriptions == "compact":
                # The field label already carries its name. Retain the supplied
                # description, value type and unit; never invent missing fields.
                text = f"{field.description} ({field.value_type}{unit})"
            record.field(safe, dtype="list", description=description(text))
            mapping[safe] = field.name
        reverse[key] = (table, mapping)
    return builder, reverse
