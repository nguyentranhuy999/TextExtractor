# Kết quả phần đã chạy

Bản bàn giao dùng duy nhất `outputs/rotowire-main-v2`, trên 200 ID đã khóa. Người dùng xác nhận chưa có khóa OpenAI và yêu cầu bàn giao phần chạy được. **Chưa hoàn tất thí nghiệm so sánh bốn cấu hình.**

| Hạng mục | Kết quả thực |
|---|---:|
| Công việc có trạng thái | 800 |
| GLiNER2 biết trước trường, đã thử | 200 |
| GLiNER2 có đầu ra hợp lệ | 198 |
| GLiNER2 lỗi giới hạn đầu vào | 2 |
| Lượt chạy mạng GLiNER2 trong nhánh test cuối | 1.322 |
| Công việc cần GPT chưa thực hiện | 600 |
| Yêu cầu OpenAI API đã gửi trong chiến dịch | 0 |
| Dữ kiện gold của 200 bài | 6.156 |

“Đầu ra hợp lệ” nói về việc xử lý/định dạng thành công, không khẳng định các dữ kiện đúng. Hai lỗi input_limit được giữ trong mẫu số; toàn bộ dữ kiện gold của chúng là FN. Sáu trăm công việc blocked không được tính là đã thử và không có thời gian giả 0 ms.

## Chất lượng GLiNER2 ở cấu hình đã khóa

| Chỉ số | Giá trị |
|---|---:|
| Fact micro precision | 0,021755 |
| Fact micro recall | 0,004711 |
| Fact micro F1 | 0,007745 |
| Macro fact F1 | 0,010657 |
| Entity F1 | 0,168161 |
| Field F1 | 0,990968 |
| Thời gian trung bình trên 198 bài xử lý thành công | 5.468,68 ms/bài |
| Median trên 198 bài xử lý thành công | 2.784,65 ms/bài |
| P95 trên 198 bài xử lý thành công | 14.964,93 ms/bài |
| Thời gian trung bình trên cả 200 nỗ lực | 5.414,63 ms/bài |

F1 trường cao vì nhóm A được biết trước tên bảng/cột; đây không phải bằng chứng mô hình tự khám phá đúng schema. F1 dữ kiện rất thấp cho thấy cấu hình này chưa tạo được bảng đủ tin cậy để sử dụng tự động. Quan sát đầu ra thấy các trường hợp tên đội xuất hiện trong bảng cầu thủ, định danh chưa giải quyết và số gắn sai thuộc tính. Không dùng điểm trường để che đi lỗi liên kết đối tượng–giá trị.

Trong 20 ID đã chọn trước, kiểm tra nhãn còn phát hiện nhiều trường hợp cần rà soát độc lập: số điểm cá nhân gán thành điểm hiệp của đội, số tổng hợp gán cho một người, hoặc số thuộc người khác. [LABEL_REVIEW.md](LABEL_REVIEW.md) ghi bằng chứng. Nhãn gốc vẫn được giữ nguyên; chưa có điểm “sửa nhãn” hay bù điểm cho một phương pháp.

## Hai câu hỏi so sánh còn thiếu dữ liệu

1. Chưa thể tính GLiNER2 giữ được bao nhiêu chất lượng hoặc nhanh/chậm hơn GPT khi cùng biết schema, vì A_GPT_KNOWN chưa được thử.
2. Chưa thể so sánh hệ thống GPT đoạn ngắn + GLiNER2 với GPT đọc toàn bài, hoặc phân biệt lỗi do thiếu schema với lỗi trích xuất của hệ thống kết hợp, vì hai nhánh B chưa được thử.

Chênh lệch F1, tỷ lệ thời gian và khoảng tin cậy so sánh hiện là null; không có cặp thành công giữa hai phương pháp. Chỉ có thể kết luận về kết quả quan sát của GLiNER2 ở cấu hình cụ thể này, không kết luận chung về GLiNER2 hoặc mọi LLM.

## Tệp bàn giao và tiếp tục

- Báo cáo tái tạo từ log: `outputs/rotowire-main-v2/report.md`.
- Xem từng bài, gold, schema, đầu ra và lỗi: `outputs/rotowire-main-v2/samples.html`.
- Số đo chi tiết: `summary.csv`, `metrics_per_sample.csv`, `table_breakdown.csv`, `metrics.json` trong cùng thư mục.
- Dấu vết thực thi: `protocol.lock.json`, `environment.json`, `results/`, `events/`, `campaign.json`.
- Cài đặt và chạy lại: [README.md](../README.md); phạm vi triển khai: [IMPLEMENTATION.md](IMPLEMENTATION.md).

Đã chạy 45 kiểm thử đạt, gồm GLiNER2 thật trên validation; kiểm thử mock không đi vào các số đo trên. Lượt v1 được lưu để truy nguyên sửa đổi kỹ thuật; mọi số đo trong tài liệu này dùng v2, không chọn mẫu/kết quả tốt nhất giữa các lượt.

Khi có OPENAI_API_KEY, chạy preflight và pilot thật; nếu giao thức không đổi, tiếp tục `run --run-id rotowire-main-v2 --resume`. Nếu cần sửa cấu hình/prompt/mã, tạo run_id mới. Việc các nhánh GPT được chạy vào thời điểm sau CPU phải được nêu như giới hạn của phép so sánh độ trễ.
