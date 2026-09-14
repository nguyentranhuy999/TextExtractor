import json
from pathlib import Path
from rotowire_bench.reporting import report
from rotowire_bench.config import ARMS
from rotowire_bench.schemas import InferenceInput
from rotowire_bench.snippets import select_snippet
from rotowire_bench.utils import write_json,write_jsonl


def test_report_escapes_untrusted_html_and_does_not_invent_metrics(tmp_path,config,gold):
    item=InferenceInput(sample_id=gold.sample_id,full_text='<script>alert("x")</script> short')
    write_json(tmp_path/"protocol.lock.json",dict(sample_ids=[item.sample_id],config=config,split="validation"))
    write_jsonl(tmp_path/"inputs.jsonl",[item.model_dump()])
    write_jsonl(tmp_path/"evaluation_gold.jsonl",[gold.model_dump()])
    write_jsonl(tmp_path/"snippets.jsonl",[dict(sample_id=item.sample_id,**select_snippet(item).to_dict())])
    for arm in ARMS:
        write_json(tmp_path/"results"/f"{item.sample_id}__{arm}.json",dict(sample_id=item.sample_id,arm=arm,status="blocked",attempted=False,simulated=False,output={"tables":[]},timings={"latency_e2e_ms":None},errors=["No credentials"],n_api_attempts=0))
    result=report(tmp_path)
    page=Path(result["html"]).read_text()
    assert '<script>alert(' not in page
    assert '&lt;script&gt;alert' in page
    metrics=json.loads((tmp_path/"metrics.json").read_text())
    assert all(s["fact_f1"] is None and s["all_mean_ms"] is None for s in metrics["summary"])
    assert "CHƯA HOÀN TẤT" in (tmp_path/"report.md").read_text()


def test_evaluation_rejects_changed_gold(tmp_path,config,gold,item):
    import pytest
    from rotowire_bench.utils import digest
    from rotowire_bench.reporting import evaluate
    manifest={"samples":[{"sample_id":item.sample_id,"gold_sha256":digest(gold.tables.model_dump())}]}
    write_json(tmp_path/"sample_manifest.json",manifest)
    write_json(tmp_path/"protocol.lock.json",dict(sample_ids=[item.sample_id],config=config,split="test",manifest_sha256=digest(manifest)))
    altered=gold.model_copy(deep=True)
    altered.tables.tables[0].rows[0].cells[0].raw_values=["999"]
    write_jsonl(tmp_path/"evaluation_gold.jsonl",[altered.model_dump()])
    with pytest.raises(ValueError,match="Gold was changed"):evaluate(tmp_path)
