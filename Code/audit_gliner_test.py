"""Re-score saved local and GPT test outputs, compare, and verify provenance."""
from pathlib import Path
import sys
import collections
import csv
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rotowire_bench.data import prepared
from rotowire_bench.config import load_config
from rotowire_bench.evaluation import score_output, aggregate_counts, scores, paired_bootstrap
from rotowire_bench.schemas import TableOutput, known_schema
from rotowire_bench.utils import read_json, read_jsonl, digest, write_json

dest = ROOT / 'outputs/gliner-test-v1'
config = load_config(dest / 'selected_config.yaml')
inputs, gold, manifest = prepared(config, 'test')
items = {x.sample_id: x for x in inputs}
rows = [read_json(p) for p in sorted((dest / 'results').glob('*.json'))]
assert len(rows) == 200 and {r['sample_id'] for r in rows} == set(items)
lock = read_json(dest / 'protocol.lock.json')
details = {}
for row in rows:
    sid = row['sample_id']
    assert row['arm'] == 'A_GLINER_KNOWN' and row['attempted'] and not row['simulated']
    assert row['n_codex_attempts'] == 0 and row['execution_mode'] == 'local'
    assert row['protocol_sha256'] == digest(lock)
    assert row['text_sha256'] == digest(items[sid].full_text)
    assert row['schema'] == known_schema(gold[sid]).model_dump()
    request = read_json(dest / 'events' / sid / 'gliner_request-0.json')
    assert request['table_execution'] == 'separate'
    groups = collections.defaultdict(list)
    for chunk in request['chunks']:
        assert chunk['text'] == items[sid].full_text[chunk['start_char']:chunk['end_char']]
        groups[chunk['group_index']].append(chunk)
    assert len(groups) == len(row['schema']['tables'])
    for chunks in groups.values():
        covered = 0
        for c in chunks:
            assert c['start_char'] <= covered and c['end_char'] > covered
            covered = c['end_char']
        assert covered == len(items[sid].full_text)
    assert len(list((dest / 'events' / sid).glob('gliner_chunk-*.json'))) == row['n_forward_passes']
    details[sid] = score_output(TableOutput.model_validate(row['output']), gold[sid].tables)
counts = aggregate_counts(list(details.values()))
metrics = read_json(dest / 'metrics.json')
assert metrics['facts'] == dict(**counts, **scores(**counts))
historical = ROOT / 'outputs/rotowire-codex-main-v1'
comparisons = {}
for arm in ('A_GPT_KNOWN', 'B_GPT_DIRECT'):
    prior = [read_json(p) for p in (historical / 'results').glob(f'*__{arm}.json')]
    assert len(prior) == 200 and {r['sample_id'] for r in prior} == set(items)
    scored = {}
    for row in prior:
        sid = row['sample_id']
        assert row['text_sha256'] == digest(items[sid].full_text)
        if arm == 'A_GPT_KNOWN':
            assert row['schema'] == known_schema(gold[sid]).model_dump()
        scored[sid] = score_output(TableOutput.model_validate(row['output']), gold[sid].tables)
    c = aggregate_counts(list(scored.values()))
    original = next(r for r in csv.DictReader((historical / 'summary.csv').open()) if r['arm']==arm)
    assert all(abs(scores(**c)[k]-float(original['fact_'+k])) < 1e-12 for k in ('precision','recall','f1'))
    ci = paired_bootstrap(details, scored, {}, {}, seed=2026, repetitions=2000)
    comparisons[arm] = dict(facts=dict(**c, **scores(**c)), n_quality_pairs=ci['n_quality'],
                           local_minus_historical_f1=ci['f1_difference'], f1_difference_ci95=ci['f1_difference_ci95'],
                           schema_access_matched=arm=='A_GPT_KNOWN', new_gpt_calls=0,
                           latency_comparison=None, reason='Different campaign times; no measured speedup claim')
write_json(dest / 'historical_comparison.json', comparisons)
prior_hashes = read_json(dest / 'prior_files_sha256.json')
assert all(digest((ROOT / p).read_bytes()) == h for p,h in prior_hashes.items())
write_json(dest / 'verification.json', dict(complete=True, n_samples=200, all_ids_text_gold_matched=True,
           whole_text_covered_per_table=True, saved_results_rescored=True, schema_headers_only=True,
           n_gpt_calls=0, prior_files_unchanged=len(prior_hashes), no_test_tuning=True,
           aliases_and_extraction_code_unchanged=True))
print(metrics)
print(comparisons)
