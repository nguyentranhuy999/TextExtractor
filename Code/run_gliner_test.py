"""Run the frozen local GLiNER2 configuration on the existing 200 test IDs.

From the repository root: HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
PYTHONHASHSEED=0 .venv/bin/python Code/run_gliner_test.py
No GPT client is constructed. Existing campaigns are never overwritten.
"""
from pathlib import Path
import collections
import random
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rotowire_bench.config import load_config
from rotowire_bench.data import prepared
from rotowire_bench.evaluation import aggregate_counts, score_output, scores
from rotowire_bench.gliner_validation import NoGPT
from rotowire_bench.pipelines import execute, SUCCESS
from rotowire_bench.reporting import latency_stats, write_csv
from rotowire_bench.runner import campaign_mutex, environment, source_hashes
from rotowire_bench.schemas import TableOutput, known_schema
from rotowire_bench.utils import digest, read_json, read_jsonl, write_json, write_jsonl, utc_now


def main():
    config_path = ROOT / 'outputs/gliner-validation-v1/selected_config.yaml'
    config = load_config(config_path)
    assert {k: config['gliner'][k] for k in ('schema_labels', 'schema_descriptions', 'table_execution')} == dict(schema_labels='semantic', schema_descriptions='compact', table_execution='separate')
    inputs, gold, manifest = prepared(config, 'test')
    ids = [x.sample_id for x in inputs]
    assert len(ids) == len(set(ids)) == 200
    historical = read_jsonl(ROOT / 'outputs/rotowire-codex-main-v1/inputs.jsonl')
    hybrid = read_jsonl(ROOT / 'outputs/hybrid-test-v3/inputs.jsonl')
    expected_texts = {x.sample_id: digest(x.full_text) for x in inputs}
    for previous in (historical, hybrid):
        assert {x['sample_id']: digest(x['full_text']) for x in previous} == expected_texts
    for previous_dir in ('rotowire-codex-main-v1', 'hybrid-test-v3'):
        previous_gold = read_jsonl(ROOT / 'outputs' / previous_dir / 'evaluation_gold.jsonl')
        assert {x['sample_id']: digest(x['tables']) for x in previous_gold} == {sid: digest(gold[sid].tables.model_dump()) for sid in ids}
    dest = ROOT / 'outputs/gliner-test-v1'
    dest.mkdir(exist_ok=False)
    with campaign_mutex(dest / '.runner.lock'):
        env = environment(config)
        lock = dict(kind='gliner_local_test_only', split='test', sample_ids=ids,
                    config=config, executed_arms=['A_GLINER_KNOWN'], source_sha256=source_hashes(),
                    runner_sha256=digest(Path(__file__).read_bytes()),
                    selected_config_sha256=digest(config_path.read_bytes()),
                    manifest_sha256=digest(manifest), environment=env,
                    selection='Frozen separate configuration previously selected on 30 validation samples; no test tuning',
                    comparison='Same text and gold as historical GPT and final hybrid; different campaign times')
        write_json(dest / 'protocol.lock.json', lock)
        write_json(dest / 'environment.json', env)
        write_json(dest / 'sample_manifest.json', manifest)
        write_jsonl(dest / 'inputs.jsonl', [x.model_dump() for x in inputs])
        write_jsonl(dest / 'evaluation_gold.jsonl', [gold[sid].model_dump() for sid in ids])
        (dest / 'selected_config.yaml').write_bytes(config_path.read_bytes())
        with zipfile.ZipFile(dest / 'source_snapshot.zip', 'w', zipfile.ZIP_DEFLATED) as z:
            for name in lock['source_sha256']:
                z.write(ROOT / 'rotowire_bench' / name, 'rotowire_bench/' + name)
            z.write(__file__, 'Code/run_gliner_test.py')
        order = list(ids)
        random.Random(config['run']['order_seed']).shuffle(order)
        write_json(dest / 'schedule.json', order)
        from rotowire_bench.models.gliner2_adapter import GLiNER2Adapter
        model = GLiNER2Adapter(config['gliner'], local_files_only=True)
        write_json(dest / 'model_setup.json', model.metadata)
        items = {x.sample_id: x for x in inputs}
        started = time.perf_counter_ns()
        rows, details, per_sample = [], {}, []
        for index, sid in enumerate(order, 1):
            event_dir = dest / 'events' / sid
            def emit(kind, value):
                suffix = value['index'] if kind == 'gliner_chunk' else 0
                write_json(event_dir / f'{kind}-{suffix}.json', value)
            row = execute(items[sid], 'A_GLINER_KNOWN', config, model, NoGPT(), emit,
                          known_schema_factory=lambda: known_schema(gold[sid]))
            row.update(protocol_sha256=digest(lock), run_id=dest.name)
            assert row['n_codex_attempts'] == 0 and not row['simulated']
            write_json(dest / 'results' / f'{sid}.json', row)
            rows.append(row)
            pred = TableOutput.model_validate(row['output'])
            detail = score_output(pred, gold[sid].tables)
            details[sid] = detail
            per_sample.append(dict(sample_id=sid, status=row['status'], n_forward_passes=row['n_forward_passes'],
                                   latency_e2e_ms=row['timings']['latency_e2e_ms'], **detail['facts']))
            print(f'{index}/200 {sid}: {row["status"]}; {row["n_forward_passes"]} forwards', flush=True)
        counts = aggregate_counts(list(details.values()))
        result = dict(complete=len(rows)==200 and all(r['attempted'] for r in rows), split='test',
                      variant='separate', arm='A_GLINER_KNOWN', n_expected=200, n_attempted=sum(r['attempted'] for r in rows),
                      n_completed=len(rows), n_valid_outputs=sum(r['status'] in SUCCESS for r in rows),
                      statuses=dict(collections.Counter(r['status'] for r in rows)), n_gpt_calls=0,
                      n_forward_passes=sum(r['n_forward_passes'] for r in rows),
                      gold_fact_count=sum(v['facts']['gold_count'] for v in details.values()),
                      facts=dict(**counts, **scores(**counts)),
                      macro_fact_f1=sum(v['facts']['f1'] for v in details.values())/200,
                      entities=scores(**aggregate_counts(list(details.values()), 'entities')),
                      exact_document_rate=sum(v['exact'] for v in details.values())/200,
                      **latency_stats([r['timings']['latency_e2e_ms'] for r in rows if r['timings']['latency_e2e_ms'] is not None], 'all'))
        assert result['complete'] and result['gold_fact_count'] == 6156
        assert source_hashes() == lock['source_sha256']
        write_json(dest / 'metrics.json', result)
        write_json(dest / 'scores_per_sample.json', details)
        write_csv(dest / 'metrics_per_sample.csv', per_sample)
        write_csv(dest / 'summary.csv', [{**{k:v for k,v in result.items() if not isinstance(v, dict)}, **result['facts']}])
        breakdown = {}
        for kind in ('players', 'teams'):
            ds = [score_output(TableOutput.model_validate(r['output']), gold[r['sample_id']].tables, kind) for r in rows]
            c = aggregate_counts(ds)
            breakdown[kind] = dict(**c, **scores(**c), gold_fact_count=sum(v['facts']['gold_count'] for v in ds))
        write_json(dest / 'table_breakdown.json', breakdown)
        write_json(dest / 'campaign.json', dict(complete=True, n_expected=200, n_attempted=200, n_gpt_calls=0,
                   finished_at=utc_now(), execution_ms=(time.perf_counter_ns()-started)/1e6))
        print(result, flush=True)


if __name__ == '__main__':
    main()
