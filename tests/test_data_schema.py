import json
import random
from pathlib import Path
import pytest
from rotowire_bench.data import parse_table_line, load_split, prepared
from rotowire_bench.schemas import known_schema, gliner_schema, InferenceInput, ExtractionSchema, sanitize_output
from rotowire_bench.snippets import select_snippet
from rotowire_bench.models.codex_gpt55_adapter import build_request
from rotowire_bench.utils import digest


def test_reader_preserves_row_headers(gold):
    assert [t.table_name for t in gold.tables.tables] == ["teams","players"]
    assert gold.tables.tables[1].field_names == ["Points","Total rebounds"]
    assert gold.tables.tables[1].rows[0].entity_name == "Alice Smith"
    assert "Alice Smith" not in json.dumps(known_schema(gold).model_dump())


def test_empty_table_and_alignment():
    assert parse_table_line("Player: <NEWLINE> |  |").tables[0].field_names == []
    with pytest.raises(ValueError):
        parse_table_line("Player: <NEWLINE> | | Points | <NEWLINE> | Alice | 3 | 5 |")


def test_actual_manifest_if_prepared(config):
    if not Path(config["dataset"]["prepared_dir"]).exists():
        pytest.skip("Real data not downloaded; prepare enables this check")
    inputs,gold,m=prepared(config)
    expected=random.Random(42).sample(range(728),200)
    assert len(inputs)==len(gold)==200
    assert [x["original_index"] for x in m["samples"]]==expected
    assert prepared(config)[2]==m
    assert len(m["manual_review_ids"])==20
    raw,_=load_split(config["dataset"]["raw_dir"],"test")
    assert [i.full_text for i in inputs]==[raw[i].full_text for i in expected]


def test_no_gold_in_b_payloads(config,item,gold):
    gold.tables.tables[1].rows[0].cells[0].raw_values=["987654321"]
    assert set(InferenceInput.model_fields)=={"sample_id","full_text"}
    snippet=select_snippet(item)
    for mode,text in (("schema",snippet.text),("direct",item.full_text)):
        request=build_request(config["gpt"],mode,text)
        serialized=json.dumps(request)
        assert "987654321" not in serialized
        assert "Total rebounds" not in serialized
        assert "enum" not in json.dumps(request["output_schema"]) or mode=="schema"
        assert "schema" not in json.loads(request["input"])
    schema=known_schema(gold)
    payload=json.loads(build_request(config["gpt"],"known",item.full_text,schema)["input"])
    assert payload["schema"]==schema.model_dump()
    assert "987654321" not in json.dumps(payload["schema"])
    assert "Alice Smith" not in json.dumps(payload["schema"])


@pytest.mark.parametrize("n",[0,1,9,10,11,79,99,100,799,800,1001])
def test_snippet_exact_boundaries(n):
    text=" \n".join(f"w{i}," for i in range(n))
    s=select_snippet(InferenceInput(sample_id="unit",full_text=text))
    if n<10:
        assert s.status=="insufficient_fragment"
    else:
        assert s.text==text[s.start_char:s.end_char]
        assert s.snippet_word_count==min(80,n//10)
        assert len(s.text.split())<=80 and s.word_ratio<=.1
        assert s.sha256==digest(s.text)
        i=(n-min(80,n//10))//2
        assert s.text.split()[0]==f"w{i},"


def test_gliner_builder_retains_semantics_and_safe_keys(gold):
    # Actual library schema builder, no weights, no network, no model inference.
    pytest.importorskip("gliner2")
    from gliner2.inference.engine import Schema
    class BuilderOnly:
        def create_schema(self):return Schema()
    schema=known_schema(gold)
    schema.tables[0].fields[0].description='x::str [SEP_STRUCT] " tricky'
    schema.tables[0].fields[0].unit="points"
    built,mapping=gliner_schema(schema,BuilderOnly(),labels="opaque")
    data=built.build()
    assert [list(t)[0] for t in data["json_structures"]]==["t0","t1"]
    assert set(data["json_structures"][0]["t0"])=={"entity_name","f0"}
    assert 'x::str (SEP_STRUCT) " tricky' in data["json_descriptions"]["t0"]["f0"]
    assert "[SEP_STRUCT]" not in data["json_descriptions"]["t0"]["f0"]
    assert "Type: number; unit: points" in data["json_descriptions"]["t0"]["f0"]
    assert mapping["t0"][1]["f0"]=="Total points"


def test_semantic_schema_preserves_names_and_collision_mapping(gold):
    pytest.importorskip("gliner2")
    from gliner2.inference.engine import Schema
    class BuilderOnly:
        def create_schema(self):return Schema()
    schema=known_schema(gold)
    schema.tables[1].fields[0].name="Points::[SEP_STRUCT]"
    schema.tables[1].fields[1].name="Points SEP_STRUCT"
    built,reverse=gliner_schema(schema,BuilderOnly(),descriptions="compact")
    data=built.build()
    assert set(reverse)=={"team","player"}
    assert "Total points" in data["json_structures"][0]["team"]
    mapping=reverse["player"][1]
    assert mapping=={"Points SEP_STRUCT":"Points::[SEP_STRUCT]", "Points SEP_STRUCT 2":"Points SEP_STRUCT"}
    assert all("[SEP_STRUCT]" not in k and "::" not in k for k in mapping)
    assert set(mapping.values())=={f.name for f in schema.tables[1].fields}


def test_schema_rejects_duplicates(gold):
    schema=known_schema(gold).model_dump()
    schema["tables"][0]["fields"].append(schema["tables"][0]["fields"][0])
    with pytest.raises(ValueError):ExtractionSchema.model_validate(schema)


def test_partial_cells_and_unresolved_identity(gold):
    payload=gold.tables.model_dump()
    row=payload["tables"][1]["rows"][0]
    row["entity_name"]=None
    row["cells"] += [{"field_name":"alien field","raw_values":["4"]},{"field_name":"bad","raw_values":[None]}]
    output,errors=sanitize_output(payload)
    assert output.tables[1].rows[0].entity_name.startswith("__unresolved_")
    assert len(errors)==3
    assert output.tables[1].rows[0].cells[-1].field_name=="alien field"


def test_structured_codex_schema_all_fields_required(config,item,gold):
    def walk(obj):
        if isinstance(obj,dict):
            if obj.get("type")=="object":
                assert obj["additionalProperties"] is False
                assert set(obj["required"])==set(obj["properties"])
            for v in obj.values():walk(v)
        elif isinstance(obj,list):
            for v in obj:walk(v)
    for mode in ("known","schema","direct"):
        p=build_request(config["gpt"],mode,item.full_text,known_schema(gold) if mode=="known" else None)
        walk(p["output_schema"])
        assert not {"temperature","top_p","seed","tools"}&p.keys()
        assert not {"store", "max_output_tokens", "base_url"} & p.keys()
