# GLiNER2 local: cấu hình cuối trên 200 mẫu test

Hoàn tất 200/200 mẫu RotoWire test, cùng ID, văn bản và gold với GPT và hybrid đã lưu. Không gọi GPT trong lượt chạy này.

Cấu hình được giữ nguyên từ `outputs/gliner-validation-v1/selected_config.yaml`: semantic / compact / separate, CPU float32, 4 luồng, batch 1, threshold 0.5. Checkpoint và bộ chấm không đổi; không chọn lại cấu hình theo test.

| Chỉ số | GLiNER2 local | GPT biết schema (đã lưu) |
|---|---:|---:|
| Precision | 48.11% | 72.16% |
| Recall | 41.44% | 65.51% |
| Fact micro F1 | 44.53% | 68.68% |

TP/FP/FN local: 2551/2751/3605; gold: 6156.
Đầu ra hợp lệ: 200/200; số forward: 636.
Mean/median/P95 local: 3.620/2.592/9.165 giây/bài. Không tính tải trọng số, làm nóng, chấm điểm hoặc dựng báo cáo.

Các phương pháp được đo ở các thời điểm khác nhau, không suy ra tỷ số tăng tốc có kiểm soát. Local và GPT biết schema nhận cùng tên bảng/trường, không nhận tên hàng hoặc giá trị gold. Hybrid và GPT trực tiếp tự xác định schema; không quy chênh lệch giữa hai điều kiện chỉ cho năng lực mô hình.

Đây là cùng tập test đã quan sát trước trong dự án, chưa phải tập xác nhận hoàn toàn mới. Chỉ kiểm chứng RotoWire tiếng Anh; chưa đo token/chi phí hoặc chất lượng đa miền.

Bằng chứng: `protocol.lock.json`, `model_setup.json`, `results/`, `events/`, `metrics_per_sample.csv`, `historical_comparison.json`, `verification.json`. Báo cáo cập nhật: `Docs/Report/main.pdf`.

Để chạy một chiến dịch mới từ thư mục gốc (thư mục đích phải chưa tồn tại):
```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONHASHSEED=0 .venv/bin/python Code/run_gliner_test.py
```
Để kiểm tra lại đầu ra đã lưu, không suy luận:
```bash
.venv/bin/python Code/audit_gliner_test.py
```
