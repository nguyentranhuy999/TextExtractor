from copy import deepcopy
import pytest
from rotowire_bench.schemas import Cell, TableOutput, Row
from rotowire_bench.evaluation import score_output, normalized_value, resolve_entity, paired_bootstrap


def test_wrong_person_is_fp_and_fn(gold):
    pred=gold.tables.model_copy(deep=True)
    pred.tables[1].rows[0].cells[0].raw_values=["9"]
    pred.tables[1].rows[1].cells[0].raw_values=["24"]
    score=score_output(pred,gold.tables)
    assert (score["facts"]["tp"],score["facts"]["fp"],score["facts"]["fn"])==(2,2,2)


def test_order_does_not_matter(gold):
    pred=gold.tables.model_copy(deep=True)
    pred.tables.reverse()
    for table in pred.tables:
        table.rows.reverse();table.field_names.reverse()
        for row in table.rows:row.cells.reverse()
    assert score_output(pred,gold.tables)["exact"]


def test_synonym_missing_and_unknown(gold):
    pred=gold.tables.model_copy(deep=True)
    table=pred.tables[1]
    table.field_names=["pts","rebounds"]
    for row in table.rows:
        for cell in row.cells:cell.field_name={"Points":"pts","Total rebounds":"rebounds"}[cell.field_name]
    assert score_output(pred,gold.tables)["exact"]
    table.field_names.append("new stat")
    table.rows[0].cells.append(Cell(field_name="new stat",raw_values=["900"]))
    assert score_output(pred,gold.tables)["facts"]["fp"]==1
    table.rows[0].cells.pop(1)
    assert score_output(pred,gold.tables)["facts"]["fn"]==1


def test_null_zero_percent_count_decimal():
    assert normalized_value(None,"players","points") is None
    assert normalized_value("0","players","points")=="num:0"
    assert normalized_value("50%","players","field goals made")!="num:50"
    assert normalized_value("50 percent","players","field goal percentage")=="num:50"
    assert normalized_value("0.5","players","field goal percentage")=="num:0.5"
    assert normalized_value("twenty-four","players","points")=="num:24"
    assert normalized_value("one hundred and twenty three","teams","total points")=="num:123"
    assert normalized_value("fifty point five","teams","percentage of field goals")=="num:50.5"
    assert normalized_value("1,000.00","teams","total points")=="num:1000"


def test_duplicates_conflicts_do_not_hide_errors(gold):
    pred=gold.tables.model_copy(deep=True)
    pred.tables[1].rows[0].cells[0].raw_values=["24","24","25"]
    s=score_output(pred,gold.tables)
    assert s["facts"]["tp"]==4 and s["facts"]["fp"]==1
    assert s["duplicates"]==1 and s["conflicts"]==1


def test_unknown_empty_field_counts(gold):
    pred=gold.tables.model_copy(deep=True)
    pred.tables[0].field_names.append("new empty attribute")
    s=score_output(pred,gold.tables)
    assert s["facts"]["f1"]==1 and s["fields"]["fp"]==1 and not s["exact"]


def test_empty_and_failed(gold):
    empty=TableOutput(tables=[])
    assert score_output(empty,gold.tables)["facts"]["f1"]==0
    assert score_output(empty,empty)["facts"]["f1"]==1


def test_identity_ambiguity():
    names={"alice smith","bob smith"}
    assert resolve_entity("Smith",names)=="smith"
    assert resolve_entity("A. Smith",names)=="alice smith"
    assert resolve_entity("Smith",{"alice smith"})=="alice smith"


def test_paired_bootstrap_uses_micro_and_common_successes():
    left={"a":{"facts":{"tp":100,"fp":0,"fn":0}},"b":{"facts":{"tp":0,"fp":0,"fn":1}}}
    right={"a":{"facts":{"tp":0,"fp":0,"fn":100}},"b":{"facts":{"tp":1,"fp":0,"fn":0}}}
    r=paired_bootstrap(left,right,{"a":20,"b":999},{"a":10},repetitions=100)
    assert r["f1_difference"]==pytest.approx(200/201-2/102)
    assert r["n_success_pairs"]==1 and r["latency_ratio"]==2
    assert r["latency_ratio_ci95"]==[2,2]
    assert r==paired_bootstrap(left,right,{"a":20,"b":999},{"a":10},repetitions=100)


def test_cluster_bootstrap():
    a={"x":{"facts":{"tp":1,"fp":0,"fn":0}},"y":{"facts":{"tp":0,"fp":0,"fn":1}}}
    b={"x":{"facts":{"tp":0,"fp":0,"fn":1}},"y":{"facts":{"tp":1,"fp":0,"fn":0}}}
    r=paired_bootstrap(a,b,{}, {},game_keys={"x":"same_game","y":"same_game"},repetitions=50)
    assert r["f1_difference_ci95"]==[0,0]
    assert r["latency_ratio"] is None
