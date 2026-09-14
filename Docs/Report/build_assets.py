"""Generate final-configuration report assets from saved outputs; no inference."""
from pathlib import Path
import csv, json, hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
FIG=HERE/'figures'; FIG.mkdir(exist_ok=True)
def read(path): return json.loads((ROOT/path).read_text())
def csvread(path): return list(csv.DictReader((ROOT/path).open()))
m=read('outputs/hybrid-test-v3/metrics.json')
d=read('outputs/hybrid-test-v3/diagnostics.json')
local=read('outputs/gliner-test-v1/metrics.json')
local_verification=read('outputs/gliner-test-v1/verification.json')
known=next(r for r in csvread('outputs/rotowire-codex-main-v1/summary.csv') if r['arm']=='A_GPT_KNOWN')
gpt=next(r for r in csvread('outputs/rotowire-codex-main-v1/summary.csv') if r['arm']=='B_GPT_DIRECT')
h=read('outputs/hybrid-test-v3/historical_comparison.json')['B_GPT_DIRECT']
t=read('outputs/hybrid-test-v3/table_breakdown.json')
assert m['complete'] and m['n_attempted']==200
assert local['complete'] and local['split']=='test' and local['arm']=='A_GLINER_KNOWN'
assert all(local[key]==200 for key in ('n_expected','n_attempted','n_completed','n_valid_outputs'))
assert local['n_gpt_calls']==0 and local['gold_fact_count']==m['gold_fact_count']
assert local_verification['complete'] and local_verification['all_ids_text_gold_matched']
assert local_verification['whole_text_covered_per_table'] and local_verification['saved_results_rescored']
for comparison_row, summary_row in ((read('outputs/gliner-test-v1/historical_comparison.json')['A_GPT_KNOWN'],known),(h,gpt)):
    for key in ('precision','recall','f1'):
        assert abs(comparison_row['facts'][key]-float(summary_row['fact_'+key]))<1e-12
pct=lambda v:f'{100*float(v):.2f}'.replace('.',',')+r'\%'
sec=lambda v:f'{float(v)/1000:.3f}'.replace('.',',')
def table(filename,spec,headers,rows):
    s=r'\begin{tabularx}{\linewidth}{'+spec+'}\n'+r'\toprule'+'\n'
    s+=' & '.join(r'\textbf{'+v+'}' for v in headers)+r' \\\midrule'+'\n'
    s+='\n'.join(' & '.join(row)+r' \\' for row in rows)+'\n'
    s+=r'\bottomrule'+'\n'+r'\end{tabularx}'+'\n'
    (HERE/'sections'/filename).write_text(s)
table('local_metrics.tex','@{}Yrr@{}',['Chỉ số','GLiNER2 local','GPT schema tham chiếu'],[
 ['Precision',pct(local['facts']['precision']),pct(known['fact_precision'])],
 ['Recall',pct(local['facts']['recall']),pct(known['fact_recall'])],
 ['Fact micro F1',r'\textbf{'+pct(local['facts']['f1'])+'}',r'\textbf{'+pct(known['fact_f1'])+'}'],
 ['TP / FP / FN',' / '.join(str(local['facts'][k]) for k in ('tp','fp','fn')),
  ' / '.join(str(read('outputs/gliner-test-v1/historical_comparison.json')['A_GPT_KNOWN']['facts'][k]) for k in ('tp','fp','fn'))],
 ['Đầu ra hợp lệ',str(local['n_valid_outputs'])+'/200',known['n_success']+'/200']])
table('hybrid_metrics.tex','@{}Yrr@{}',['Chỉ số','Hybrid','GPT trực tiếp'],[
 ['Precision',pct(m['facts']['precision']),pct(gpt['fact_precision'])],['Recall',pct(m['facts']['recall']),pct(gpt['fact_recall'])],
 ['Fact micro F1',r'\textbf{'+pct(m['facts']['f1'])+'}',r'\textbf{'+pct(gpt['fact_f1'])+'}'],
 ['TP / FP / FN',' / '.join(str(m['facts'][k]) for k in ('tp','fp','fn')),' / '.join(str(h['facts'][k]) for k in ('tp','fp','fn'))],['Đầu ra hợp lệ',str(m['n_valid_outputs'])+'/200',gpt['n_success']+'/200']])
table('latency_metrics.tex','@{}Yr@{}',['Chỉ số','Giây/bài'],[
 ['Mean e2e',sec(m['all_mean_ms'])],['Median e2e',sec(m['all_median_ms'])],['P95 e2e',sec(m['all_p95_ms'])],
 ['Mean bước GPT tạo schema',sec(d['mean_stage_ms']['schema_codex_ms'])],['Mean bước GLiNER2',sec(d['mean_stage_ms']['extract_ms'])]])
table('table_metrics.tex','@{}Yrrrrrrr@{}',['Bảng','Gold','TP','FP','FN','P (\\%)','R (\\%)','F1 (\\%)'],[
 [{'players':'Cầu thủ','teams':'Đội'}[k],str(v['gold_fact_count']),str(v['tp']),str(v['fp']),str(v['fn']),pct(v['precision']).replace(r'\%',''),pct(v['recall']).replace(r'\%',''),pct(v['f1']).replace(r'\%','')] for k,v in t.items()])
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
fig,axes=plt.subplots(1,2,figsize=(7.1,3.6),layout='constrained',sharey=True)
xs=list(range(3)); labels=['Precision','Recall','F1']
for ax,first,second,first_label,second_label,title in [
 (axes[0],local['facts'],known,'GLiNER2 local','GPT schema tham chiếu','Schema tham chiếu (oracle)'),
 (axes[1],m['facts'],gpt,'Hybrid','GPT trực tiếp','Tự xác định schema')]:
 a=[first[k]*100 for k in ('precision','recall','f1')]; b=[float(second['fact_'+k])*100 for k in ('precision','recall','f1')]
 for shift,vals,col,label in [(-.18,a,'#246e85',first_label),(.18,b,'#aeb8c5',second_label)]:
  bars=ax.bar([x+shift for x in xs],vals,width=.34,color=col,label=label)
  for bar,v in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,v+1,f'{v:.1f}',ha='center',fontsize=8)
 ax.set_xticks(xs,labels);ax.set_ylim(0,100);ax.set_title(title,fontsize=11);ax.legend(frameon=False,loc='upper right',fontsize=8);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
axes[0].set_ylabel('Điểm (%) trên cùng 200 mẫu test')
fig.savefig(FIG/'final_comparison.pdf');plt.close(fig)
fig,ax=plt.subplots(figsize=(7.1,3.25),layout='constrained')
vals=[d['gold_facts_without_declared_field'],d['unmatched_supported_gold_facts'],d['matched_gold_facts']]
labels=['Chưa có trường khớp','Có trường, chưa trích khớp','Trích xuất khớp đúng']
ax.barh(labels,vals,color=['#aeb8c5','#74a6b5','#246e85'])
for i,v in enumerate(vals):ax.text(v+55,i,f'{v} ({100*v/d["gold_facts"]:.2f}%)',va='center',fontsize=9)
ax.set_xlim(0,5000);ax.invert_yaxis();ax.set_xlabel('Số dữ kiện trong tổng 6156 dữ kiện gold');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
fig.savefig(FIG/'schema_coverage.pdf');plt.close(fig)
paths=['outputs/gliner-test-v1/metrics.json','outputs/gliner-test-v1/historical_comparison.json','outputs/gliner-test-v1/protocol.lock.json','outputs/gliner-test-v1/verification.json','outputs/gliner-validation-v1/selected_config.yaml','outputs/rotowire-codex-main-v1/summary.csv','outputs/hybrid-test-v3/metrics.json','outputs/hybrid-test-v3/historical_comparison.json','outputs/hybrid-test-v3/diagnostics.json','outputs/hybrid-test-v3/table_breakdown.json','data/prepared/sample_manifest.json']
paths+=['.venv/lib/python3.11/site-packages/gliner2/'+f for f in ['model.py','layers.py','processor.py','inference/engine.py']]
paths+=['.cache/gliner2-base-v1/8437ba583a733d87f56ae902f3b197934eedd58e/config.json']
(HERE/'sources_manifest.json').write_text(json.dumps({'report_revision':'2026-09-15-test200','scope':'Final configuration only; all four methods on identical 200 test IDs, comparisons separated by schema access','selected_rows':{'local':'separate on test','known_gpt':'A_GPT_KNOWN','direct':'B_GPT_DIRECT'},'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}},ensure_ascii=False,indent=2)+'\n')
print('Generated 4 final-result tables, 2 figures and source hashes; no model calls.')
