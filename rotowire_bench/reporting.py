from __future__ import annotations

import csv
import html
import io
import json
import statistics
from collections import Counter
from pathlib import Path
from .config import ARMS
from .evaluation import aggregate_counts, paired_bootstrap, quantile, score_output, scores
from .pipelines import SUCCESS
from .schemas import EvaluationGold, TableOutput
from .utils import atomic_write, digest, read_json, read_jsonl, write_json


def write_csv(path, rows, columns=None):
    buffer = io.StringIO()
    columns = columns or list(dict.fromkeys(k for r in rows for k in r))
    writer = csv.DictWriter(buffer,fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(path,buffer.getvalue())


def latency_stats(values, prefix):
    return {f"{prefix}_{name}":value for name,value in dict(mean_ms=statistics.mean(values) if values else None,
        median_ms=statistics.median(values) if values else None,p90_ms=quantile(values,.9),p95_ms=quantile(values,.95),
        throughput_docs_per_s=len(values)*1000/sum(values) if values and sum(values)>0 else None).items()}


def evaluate(run_dir):
    dest = Path(run_dir)
    lock = read_json(dest/"protocol.lock.json")
    gold = {g["sample_id"]:EvaluationGold.model_validate(g) for g in read_jsonl(dest/"evaluation_gold.jsonl")}
    ids = lock["sample_ids"]
    if set(ids) != set(gold):
        raise ValueError("Evaluation gold IDs differ from protocol")
    manifest_path = dest/"sample_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if lock.get("manifest_sha256") and digest(manifest) != lock["manifest_sha256"]:
            raise ValueError("Manifest differs from frozen protocol")
        entries = manifest["samples" if lock["split"] == "test" else "validation_samples"]
        expected = {e["sample_id"]:e for e in entries}
        for sid,value in gold.items():
            if sid not in expected or digest(value.tables.model_dump()) != expected[sid]["gold_sha256"]:
                raise ValueError("Gold was changed without a separate annotated-label analysis")
    results = {}
    for path in (dest/"results").glob("*.json"):
        result = read_json(path)
        if result.get("simulated"):
            raise ValueError("Mock results are forbidden in benchmark reports")
        if result["sample_id"] not in gold or result["arm"] not in ARMS:
            raise ValueError("Result outside protocol")
        if result.get("protocol_sha256") and result["protocol_sha256"] != digest(lock):
            raise ValueError("Result protocol hash differs from campaign")
        expected_mode = "local" if result["arm"] == ARMS[0] else lock["config"]["gpt"].get("execution_mode", "openai_responses")
        if result.get("execution_mode",expected_mode) != expected_mode:
            raise ValueError("Mixed execution modes are forbidden in a campaign")
        results[(result["sample_id"],result["arm"])] = result
    records, schema_errors, detailed, summaries = [], [], {}, []
    for arm in ARMS:
        details, attempted, successful, times_all, times_success = {}, [], [], [], []
        for sid in ids:
            r = results.get((sid,arm))
            status = r["status"] if r else "not_run"
            is_attempted = bool(r and r["attempted"])
            valid = bool(r and status in SUCCESS)
            output = TableOutput.model_validate(r["output"]) if valid else TableOutput(tables=[])
            score = score_output(output,gold[sid].tables)
            merge_path = dest/"events"/f"{sid}__{arm}"/"gliner_merge-0.json"
            if merge_path.exists():
                score["duplicates"] += read_json(merge_path).get("duplicates_merged",0)
            details[sid] = score
            if is_attempted:
                attempted.append(score)
            if valid:
                successful.append(score)
            latency = r["timings"].get("latency_e2e_ms") if r else None
            if is_attempted and latency is not None:
                times_all.append(latency)
                if valid:
                    times_success.append(latency)
            rec = dict(sample_id=sid,arm=arm,execution_mode="local" if arm == ARMS[0] else lock["config"]["gpt"].get("execution_mode","openai_responses"),status=status,attempted=is_attempted,latency_e2e_ms=latency,
                       **{f"fact_{k}":v for k,v in score["facts"].items()},field_f1=score["fields"]["f1"],entity_f1=score["entities"]["f1"],
                       exact=score["exact"],duplicates=score["duplicates"],conflicts=score["conflicts"])
            records.append(rec)
            for f in score["errors"].get("extra_field",[]):
                schema_errors.append(dict(sample_id=sid,arm=arm,error_type="extra_field",detail=json.dumps(f)))
            for f in sorted({(fact[0],fact[2]) for fact in score["errors"].get("missing_field",[])}):
                schema_errors.append(dict(sample_id=sid,arm=arm,error_type="missing_field",detail=json.dumps(f)))
            for e in r.get("errors",[]) if r else []:
                schema_errors.append(dict(sample_id=sid,arm=arm,error_type="output_or_execution",detail=e))
        detailed[arm] = details
        complete = len(attempted) == len(ids)
        selected_results = [r for (sid,a),r in results.items() if a == arm]
        fact = scores(**aggregate_counts(list(details.values()))) if complete else dict(precision=None,recall=None,f1=None)
        summary = dict(arm=arm,execution_mode="local" if arm == ARMS[0] else lock["config"]["gpt"].get("execution_mode","openai_responses"),n_expected=len(ids),n_completed=len(attempted),n_success=len(successful),n_failed=len(attempted)-len(successful),
            n_blocked=sum(r["status"]=="blocked" for r in selected_results),n_pending_external=sum(r["status"]=="pending_external" for r in selected_results),n_not_run=len(ids)-len(selected_results),
            gold_fact_count=sum(s["facts"]["gold_count"] for s in details.values()),fact_precision=fact["precision"],fact_recall=fact["recall"],fact_f1=fact["f1"],
            macro_f1=statistics.mean(s["facts"]["f1"] for s in details.values()) if complete else None,
            field_f1=scores(**aggregate_counts(list(details.values()),"fields"))["f1"] if complete else None,
            entity_f1=scores(**aggregate_counts(list(details.values()),"entities"))["f1"] if complete else None,
            exact_document_rate=sum(s["exact"] for s in details.values())/len(ids) if complete else None,
            valid_output_rate=len(successful)/len(attempted) if attempted else None,
            failure_rate=(len(attempted)-len(successful))/len(attempted) if attempted else None,
            duplicate_document_rate=sum(s["duplicates"]>0 for s in attempted)/len(attempted) if attempted else None,
            conflict_document_rate=sum(s["conflicts"]>0 for s in attempted)/len(attempted) if attempted else None,
            both_empty_count=sum(s["both_empty"] for s in attempted),n_latency_observed=len(times_all),
            n_attempts=sum(r.get("n_codex_attempts",r.get("n_api_attempts",0))+r.get("n_forward_passes",0) for r in selected_results),
            n_codex_attempts=sum(r.get("n_codex_attempts",0) for r in selected_results),
            n_forward_passes=sum(r.get("n_forward_passes",0) for r in selected_results),
            success_only_fact_f1=scores(**aggregate_counts(successful))["f1"] if successful else None,
            status="complete" if complete else "incomplete_primary_metrics_unavailable",
            **latency_stats(times_all,"all"),**latency_stats(times_success,"success"))
        summaries.append(summary)
    breakdown = []
    for arm in ARMS:
        for kind in ("players","teams"):
            samples = []
            for sid in ids:
                r = results.get((sid,arm))
                output = TableOutput.model_validate(r["output"]) if r and r["status"] in SUCCESS else TableOutput(tables=[])
                samples.append(score_output(output,gold[sid].tables,kind))
            complete = next(s for s in summaries if s["arm"]==arm)["n_completed"] == len(ids)
            breakdown.append(dict(arm=arm,table_type=kind,gold_fact_count=sum(s["facts"]["gold_count"] for s in samples),
                **({f"fact_{k}":v for k,v in scores(**aggregate_counts(samples)).items()} if complete else {"fact_precision":None,"fact_recall":None,"fact_f1":None}),
                field_f1=scores(**aggregate_counts(samples,"fields"))["f1"] if complete else None,
                entity_f1=scores(**aggregate_counts(samples,"entities"))["f1"] if complete else None))
    comparisons = []
    games = {sid:g.game_key for sid,g in gold.items()} if all(g.game_key for g in gold.values()) else None
    for a,b in ((ARMS[0],ARMS[1]),(ARMS[2],ARMS[3])):
        sa,sb = (next(s for s in summaries if s["arm"]==arm) for arm in (a,b))
        complete = sa["n_completed"] == len(ids) and sb["n_completed"] == len(ids)
        lat = lambda arm:{sid:r["timings"]["latency_e2e_ms"] for (sid,x),r in results.items() if x == arm and r["status"] in SUCCESS and r["timings"].get("latency_e2e_ms") is not None}
        comparisons.append(dict(left=a,right=b,quality_available=complete,**paired_bootstrap(detailed[a] if complete else {},detailed[b] if complete else {},lat(a),lat(b),
            seed=lock["config"]["evaluation"]["bootstrap_seed"],repetitions=lock["config"]["evaluation"]["bootstrap_repetitions"],game_keys=games)))
    write_csv(dest/"metrics_per_sample.csv",records)
    write_csv(dest/"summary.csv",summaries)
    write_csv(dest/"table_breakdown.csv",breakdown)
    write_csv(dest/"schema_errors.csv",schema_errors,["sample_id","arm","error_type","detail"])
    write_json(dest/"metrics.json",dict(summary=summaries,comparisons=comparisons,per_sample=detailed,table_breakdown=breakdown))
    return dict(run_dir=str(dest),n_expected=len(ids)*4,n_attempted=sum(s["n_completed"] for s in summaries),summary=summaries,comparisons=comparisons)


def format_number(value, digits=4):
    return "chưa có" if value is None else f"{value:.{digits}f}"


def wide_table(output):
    parts=[]
    for table in output.get("tables",[]):
        names=list(dict.fromkeys(table["field_names"]+[c["field_name"] for r in table["rows"] for c in r["cells"]]))
        parts.append("<h4>"+html.escape(table["table_name"])+"</h4><table><thead><tr><th>entity_name</th>"+"".join("<th>"+html.escape(n)+"</th>" for n in names)+"</tr></thead><tbody>")
        for row in table["rows"]:
            cells={}
            for c in row["cells"]:
                cells.setdefault(c["field_name"],[]).extend(c["raw_values"])
            parts.append("<tr><th>"+html.escape(row["entity_name"])+"</th>"+"".join("<td>"+html.escape(" | ".join(cells.get(n,[])))+"</td>" for n in names)+"</tr>")
        parts.append("</tbody></table>")
    return "".join(parts)


def export_wide_csv(dest,sid,arm,output):
    for ti,table in enumerate(output.get("tables",[])):
        fields=list(dict.fromkeys(table["field_names"]+[c["field_name"] for r in table["rows"] for c in r["cells"]]))
        rows=[]
        for row in table["rows"]:
            cells={}
            for c in row["cells"]:
                cells.setdefault(c["field_name"],[]).extend(c["raw_values"])
            rows.append({"entity_name":row["entity_name"],**{f:json.dumps(cells.get(f,[]),ensure_ascii=False) for f in fields}})
        write_csv(dest/"tables"/f"{sid}__{arm}__{ti}.csv",rows,["entity_name",*fields])


def report(run_dir):
    evaluation = evaluate(run_dir)
    dest=Path(run_dir)
    lock=read_json(dest/"protocol.lock.json")
    metrics=read_json(dest/"metrics.json")
    summaries=metrics["summary"]
    complete=evaluation["n_attempted"] == evaluation["n_expected"]
    lines=["# Khảo sát RotoWire: GLiNER2 và GPT 5.5", "",f"Run: `{dest.name}` · split: `{lock['split']}`.","",
           f"Trạng thái: **{'đủ lượt thử mô hình' if complete else 'CHƯA HOÀN TẤT'}** — {evaluation['n_attempted']}/{evaluation['n_expected']} công việc đã thực sự thử.",
           "Blocked, pending_external và công việc chưa chạy không được coi là đã thử. Chỉ công bố điểm chính của một nhánh khi đã thử đủ toàn bộ ID; ô trống CSV là null, không phải 0.","",
           "## Hai so sánh chính",""]
    for title,arms in (("A — cùng biết trước trường",ARMS[:2]),("B — đoạn ngắn so với đọc toàn bài",ARMS[2:])):
        lines += [f"### {title}","","| Phương pháp | Đã thử / dự kiến | Thành công | Fact micro F1 | Field F1 | Mean thành công (ms) | P95 thành công (ms) |","|---|---:|---:|---:|---:|---:|---:|"]
        for arm in arms:
            s=next(s for s in summaries if s["arm"]==arm)
            lines.append(f"| {arm} | {s['n_completed']} / {s['n_expected']} | {s['n_success']} | {format_number(s['fact_f1'])} | {format_number(s['field_f1'])} | {format_number(s['success_mean_ms'],2)} | {format_number(s['success_p95_ms'],2)} |")
        comp=next(c for c in metrics["comparisons"] if c["left"]==arms[0])
        lines += ["",f"Chênh lệch F1 (trái − phải): {format_number(comp['f1_difference'])}; CI95% {comp['f1_difference_ci95']}. Tỷ lệ tổng thời gian trái/phải: {format_number(comp['latency_ratio'])}, {comp['n_success_pairs']} cặp thành công; CI95% {comp['latency_ratio_ci95']}.",""]
    lines += ["## Diễn giải", ""]
    for i,comp in enumerate(metrics["comparisons"],1):
        lines.append(f"{i}. "+("Dữ liệu so sánh còn thiếu; chưa thể kết luận về chất lượng tương đối hoặc lợi thế thời gian." if not comp["quality_available"] else f"Chênh lệch micro F1 quan sát là {format_number(comp['f1_difference'])}; tỷ lệ thời gian trên các cặp thành công là {format_number(comp['latency_ratio'])}. Đây là kết quả của một lần chạy cấu hình đã khóa."))
    hybrid=[metrics["per_sample"][ARMS[2]][sid] for sid in lock["sample_ids"] if (dest/"results"/f"{sid}__{ARMS[2]}.json").exists() and read_json(dest/"results"/f"{sid}__{ARMS[2]}.json")["attempted"]]
    error_counts=Counter({k:sum(len(r["errors"].get(k,[])) for r in hybrid) for k in ("missing_field","missing_entity","missing_or_wrong_value","extra_or_wrong_fact")})
    lines.append("3. "+(f"Lỗi nhánh kết hợp: {dict(error_counts)}. Phân loại tự động theo trường → định danh → giá trị; không chứng minh quan hệ nhân quả. Phạm vi thời gian và nghi ngờ nhãn cần rà soát thủ công." if hybrid else "Nhánh kết hợp chưa có lượt thử; chưa thể phân tích nguyên nhân sai số."))
    lines.append("4. Chưa đặt ngưỡng chất lượng ứng dụng nên không tự kết luận GLiNER2 đáp ứng yêu cầu sản phẩm. Dùng điểm trường, định danh, dữ kiện và các ô lỗi trong samples.html để xác định trường hợp cần xử lý thêm.")
    campaign = read_json(dest/"campaign.json") if (dest/"campaign.json").exists() else None
    if campaign:
        sessions = campaign.get("sessions",[])
        lines += ["",f"Chiến dịch có {len(sessions)} phiên thực thi; tổng thời gian vòng chạy được ghi nhận là {sum(s['execution_ms'] for s in sessions):.2f} ms, chưa cộng tải/làm nóng. Lịch và thời điểm từng phiên nằm trong campaign.json.",
                  "Nếu resume những nhánh trước đây bị blocked ở một thời điểm khác, thứ tự Latin dự kiến không bảo đảm các mô hình đã thực sự chạy xen kẽ cùng thời điểm; cần diễn giải độ trễ với giới hạn này."]
    review_path = dest/"manual_review.json"
    if review_path.exists() and read_json(review_path).get("notes_file"):
        lines += ["", "Ghi chú đối chiếu 20 nhãn được chọn trước: [label_review.md](label_review.md). Đây là rà soát hỗ trợ bởi Codex, chưa có xác nhận độc lập của con người; không sửa nhãn gốc."]
    lines += ["", f"Chế độ GPT: `{lock['config']['gpt'].get('execution_mode','openai_responses')}`. CLI: `{lock['config']['gpt'].get('codex_cli_version','not_applicable')}`. Mô hình quan sát và kiểm tra ngữ cảnh nằm trong audit của từng attempt. Số lần gọi mô hình/lần thử nội bộ và phiên bản trọng số máy chủ có thể không được công bố."]
    if lock["config"]["gpt"].get("execution_mode") == "codex_ui_import":
        lines += ["So sánh thời gian CHƯA HOÀN TẤT: chế độ UI không có phép đo GPT/hybrid đáng tin cậy; thời gian để null. Bằng chứng ngữ cảnh/mô hình do người thao tác cung cấp, không tương đương kiểm tra rollout CLI."]
    lines += ["", "## Giao thức và giới hạn", "",
        "Nhóm A được biết tên bảng và cột của từng gold, không được biết số hàng, tên đối tượng hoặc giá trị. Nhóm B không nhận danh mục cột. Đoạn liên tục giữa bài theo min(80, N//10), nguyên văn; không suy ra tiết kiệm tiền hay token.",
        "Chuẩn hóa Unicode NFC, khoảng trắng, hoa thường; từ điển theo loại bảng; Decimal và số viết bằng chữ. Không quy đổi 0.5 thành 50%. Khớp định danh rút gọn chỉ khi duy nhất. Hai tập dữ kiện cùng rỗng: F1=1; một tập rỗng: F1=0. Lỗi đã thử là dự đoán rỗng và làm tăng FN. Các trường rỗng vẫn tính điểm trường.",
        "Độ trễ ứng dụng CPU sau tải/làm nóng; GPT gồm khởi động/điều phối Codex CLI, mạng và máy chủ từ xa. E2E gồm chuẩn bị, mọi lần gọi và retry wait, trích xuất và hậu xử lý. Không cộng E2E với các thành phần. Độ trễ thành công và toàn bộ nỗ lực lưu riêng trong summary.csv; lỗi nhanh không phải cải thiện tốc độ.",
        "Bootstrap ghép cặp 2.000 lần, seed 2026; micro F1 được tính lại từ tổng TP/FP/FN. Tỷ lệ thời gian là tỷ lệ tổng trên cùng ID thành công. Khoảng tin cậy chỉ phản ánh biến thiên dữ liệu của một lần chạy, không toàn bộ ngẫu nhiên mô hình.",
        "Chỉ 200 mẫu miền bóng rổ; một mức low GPT và một checkpoint GLiNER2. Không kiểm chứng nhiễm dữ liệu tiền huấn luyện; gold chuyển thể có thể sai; đoạn 10% không đại diện toàn bài. Không có khóa trận ghép xác định: chỉ kiểm tra trùng văn bản, validation chỉ kiểm tra kỹ thuật; chưa loại sạch trùng trận.",
        "Danh sách 20 ID rà soát được chọn trước trong sample_manifest.json. manual_review.json ghi trạng thái; báo cáo không tự coi việc kiểm tra nhãn là hoàn tất. Giữ nhãn gốc làm chính; sửa nhãn phải có changelog và chạy điểm phụ riêng cho cả bốn nhánh.",
        "", "## Nguồn và tái lập", "",
        "[Text-to-Table data](https://huggingface.co/datasets/xqwu/text-to-table) · [mã tác giả](https://github.com/shirley-wu/text_to_table) · [GLiNER2](https://github.com/fastino-ai/GLiNER2) · [GPT 5.5 trong Codex](https://learn.chatgpt.com/docs/models) · [Codex CLI](https://learn.chatgpt.com/docs/non-interactive-mode).",
        "SHA256 dữ liệu, commit checkpoint, cấu hình, mã nguồn và phiên bản thư viện nằm trong protocol.lock.json, sample_manifest.json và environment.json. preflight.json ghi khả năng tải mô hình và truy cập Codex qua ChatGPT. campaign.json liệt kê công việc còn lại."]
    atomic_write(dest/"report.md","\n\n".join(lines)+"\n")
    inputs=read_jsonl(dest/"inputs.jsonl")
    snippets={s["sample_id"]:s for s in read_jsonl(dest/"snippets.jsonl")}
    gold={g["sample_id"]:g["tables"] for g in read_jsonl(dest/"evaluation_gold.jsonl")}
    parts=['<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RotoWire — phân tích từng mẫu</title><style>body{font:16px system-ui;max-width:1440px;margin:auto;padding:24px;background:#f6f7fb;color:#18283d}details{background:white;margin:12px 0;padding:16px;border:1px solid #ccd4df;border-radius:8px}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere}table{border-collapse:collapse;display:block;overflow:auto}th,td{border:1px solid #ccd4df;padding:7px;vertical-align:top}th{background:#eaf0f7}mark{background:#ffdf85}.article{white-space:pre-wrap;line-height:1.6}</style><h1>RotoWire: phân tích từng mẫu</h1><p>Trang phân tích có gold. Các nội dung mô hình và văn bản đều được escape trước khi hiển thị.</p>']
    for item in inputs:
        sid=item["sample_id"];snippet=snippets[sid];text=item["full_text"]
        start,end=snippet["start_char"],snippet["end_char"]
        article=html.escape(text) if start is None else html.escape(text[:start])+"<mark>"+html.escape(text[start:end])+"</mark>"+html.escape(text[end:])
        parts += ["<details><summary>"+html.escape(sid)+"</summary><h3>Văn bản và đoạn trích</h3><p class='article'>"+article+"</p>","<h3>Gold</h3>",wide_table(gold[sid])]
        for arm in ARMS:
            path=dest/"results"/f"{sid}__{arm}.json"
            r=read_json(path) if path.exists() else {"status":"not_run","output":{"tables":[]},"schema":None}
            parts += ["<h3>"+arm+": "+html.escape(r["status"])+"</h3>","<details><summary>Schema dự đoán/được cho</summary><pre>"+html.escape(json.dumps(r.get("schema"),ensure_ascii=False,indent=2))+"</pre></details>",wide_table(r["output"]),"<details><summary>Lỗi từng dữ kiện và cấu trúc</summary><pre>"+html.escape(json.dumps(dict(scoring=metrics["per_sample"][arm][sid]["errors"],execution=r.get("errors",[])),ensure_ascii=False,indent=2))+"</pre></details>"]
            export_wide_csv(dest,sid,arm,r["output"])
        parts.append("</details>")
    parts.append("</html>")
    atomic_write(dest/"samples.html","".join(parts))
    plot_status=make_plots(dest,summaries,metrics,lock)
    write_json(dest/"report_status.json",dict(complete=complete,plots=plot_status,manual_review=read_json(dest/"manual_review.json").get("status") if (dest/"manual_review.json").exists() else "pending"))
    return dict(report=str(dest/"report.md"),html=str(dest/"samples.html"),plots=plot_status)


def make_plots(dest,summaries,metrics,lock):
    observed=[s for s in summaries if s["fact_f1"] is not None]
    if not observed:
        return "Không có nhánh đủ lượt thử để vẽ F1 chính"
    try:
        import os
        os.environ.setdefault("MPLCONFIGDIR",str(Path(".cache/matplotlib").resolve()))
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "Thiếu matplotlib; CSV/JSON đã xuất"
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout="constrained")
    names=[s["arm"] for s in observed]
    axes[0].bar(names,[s["fact_f1"] for s in observed],color="#3369a8");axes[0].set(ylabel="Fact micro F1",ylim=(0,1),title="Quality (completed arms only)")
    timed=[s for s in observed if s["success_median_ms"] is not None]
    axes[1].bar([s["arm"] for s in timed],[s["success_median_ms"] for s in timed],color="#008478");axes[1].set(ylabel="Successful document median latency (ms)",title="Application latency")
    for ax in axes:ax.tick_params(axis="x",rotation=20)
    fig.savefig(dest/"quality_latency.png",dpi=160);plt.close(fig)
    categories=["missing_field","missing_entity","missing_or_wrong_value","extra_or_wrong_fact"]
    fig,ax=plt.subplots(figsize=(12,5),layout="constrained")
    for i,s in enumerate(observed):
        counts=[sum(len(v["errors"].get(k,[])) for v in metrics["per_sample"][s["arm"]].values()) for k in categories]
        ax.bar([x+i*.8/len(observed) for x in range(len(categories))],counts,width=.8/len(observed),label=s["arm"])
    ax.set_xticks(range(len(categories)),categories);ax.set(ylabel="Number of facts",title="Automatic error categories (original labels)");ax.legend()
    fig.savefig(dest/"error_types.png",dpi=160);plt.close(fig)
    return ["quality_latency.png","error_types.png"]
