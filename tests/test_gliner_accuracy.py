"""Real model regression checks: correct cells, not merely parseable rows."""
import os
import pytest
from rotowire_bench.schemas import ExtractionSchema, SchemaTable, SchemaField, InferenceInput
from rotowire_bench.evaluation import normalized_value


@pytest.fixture(scope="module", params=["semantic_reference", "selected_default"])
def real_adapter(request):
    if os.getenv("RUN_GLINER_INTEGRATION") != "1":
        pytest.skip("Opt in to real local checkpoint")
    from rotowire_bench.config import load_config
    from rotowire_bench.models.gliner2_adapter import GLiNER2Adapter
    config=load_config("configs/main.yaml")["gliner"]
    if request.param == "semantic_reference":
        config.update(schema_labels="semantic",schema_descriptions="full",table_execution="joint")
    return GLiNER2Adapter(config,local_files_only=True)


@pytest.mark.integration
@pytest.mark.parametrize("text,expected",[
    ("LeBron James scored 28 points and had 8 rebounds and 6 assists. Anthony Davis scored 24 points and had 12 rebounds and 3 assists.",
     {"LeBron James":(28,8,6),"Anthony Davis":(24,12,3)}),
    ("The Celtics defeated the Hornets 106-98. Isaiah Thomas had 28 points and seven assists. Jonas Jerebko had 16 points and 10 rebounds.",
     {"Isaiah Thomas":(28,None,7),"Jonas Jerebko":(16,10,None)}),
])
def test_real_semantic_schema_correct_player_and_stat(real_adapter,text,expected):
    names=["Points","Total rebounds","Assists"]
    schema=ExtractionSchema(tables=[SchemaTable(table_name="players",entity_type="player",identity_field="entity_name",
        fields=[SchemaField(name=n,description=f"{n}; reported game.",value_type="number",unit=None) for n in names])])
    output=real_adapter.extract(InferenceInput(sample_id="synthetic-regression",full_text=text),schema,lambda *_:None)
    observed={row.entity_name:{cell.field_name:{normalized_value(v,"players",cell.field_name) for v in cell.raw_values}
                              for cell in row.cells} for row in output.tables[0].rows}
    wanted={person:{field:{f"num:{value}"} for field,value in zip(names,values) if value is not None}
            for person,values in expected.items()}
    assert observed==wanted  # Catches swapped people, swapped stats and invented cells.


@pytest.mark.parametrize("reject_player",[False,True])
def test_separate_tables_cover_full_text_and_do_not_overwrite_events(gold,item,reject_player):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from gliner2.inference.engine import Schema
    from rotowire_bench.models.gliner2_adapter import GLiNER2Adapter
    from rotowire_bench.models.common import ModelError
    from rotowire_bench.schemas import known_schema
    calls=[]
    def prepare(text,built):
        names=[next(iter(t)) for t in built["json_structures"]]
        return SimpleNamespace(num_schemas=len(names),input_ids=[0]*(1001 if reject_player and "player" in names else 10))
    def extract(text,builder,**kwargs):
        tables=builder.build()["json_structures"]
        assert len(tables)==1
        name,fields=next(iter(tables[0].items()))
        calls.append((text,name))
        return {name:[{f:(name+" name" if f=="entity_name" else "7") for f in fields}]}
    adapter=GLiNER2Adapter.__new__(GLiNER2Adapter)
    adapter.config=dict(table_execution="separate",schema_labels="semantic",schema_descriptions="compact",overlap_tokens=64,threshold=.5)
    adapter.model=SimpleNamespace(create_schema=Schema,extract=extract,
        processor=SimpleNamespace(transform_and_format=prepare,_tokenize_text=str.split))
    adapter.tokenizer=SimpleNamespace(tokenize=lambda word:[word])
    adapter.max_length=1000
    adapter.max_records=19
    adapter.saturation_counts=[]
    adapter.torch=SimpleNamespace(inference_mode=nullcontext)
    adapter.sync=lambda:None
    events=[]
    if reject_player:
        with pytest.raises(ModelError,match="Schema consumes input budget"):
            adapter.extract(item,known_schema(gold),lambda k,v:events.append((k,v)))
        assert calls==[]  # Never label a partially extracted document as successful.
    else:
        out=adapter.extract(item,known_schema(gold),lambda k,v:events.append((k,v)))
        assert calls==[(item.full_text,"team"),(item.full_text,"player")]
        chunks=[v for k,v in events if k=="gliner_chunk"]
        assert [c["index"] for c in chunks]==[0,1]
        assert [t.table_name for t in out.tables]==["teams","players"]
        assert [t.rows[0].entity_name for t in out.tables]==["team name","player name"]
        assert len([1 for k,v in events if k=="gliner_request"])==1
