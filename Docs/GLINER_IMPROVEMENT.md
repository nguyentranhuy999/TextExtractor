# Cải thiện adapter GLiNER2 và kết quả validation

Đã sửa adapter, chạy **120/120 công việc trên cùng 30 mẫu validation**, chọn
cấu hình và cập nhật `configs/main.yaml`. Không gọi GPT, không huấn luyện lại,
không thay checkpoint/ngưỡng và không sửa bộ chấm hoặc gold. Không chạy lại 200
test trong lượt này; kết quả benchmark cũ được giữ nguyên.

## Kết quả đối chiếu

| Cấu hình | Precision | Recall | Fact micro F1 | Mean hợp lệ (giây/bài) | Tổng forward |
|---|---:|---:|---:|---:|---:|
| Adapter cũ: t0/f0, mô tả đầy đủ, gộp bảng | 0,012270 | 0,002345 | 0,003937 | 1,863 | 114 |
| Tên có nghĩa, giữ mô tả | 0,389930 | 0,390387 | 0,390158 | 2,097 | 129 |
| Tên có nghĩa, mô tả ngắn | 0,476421 | 0,461899 | 0,469048 | 1,490 | 74 |
| Tên có nghĩa, mô tả ngắn, tách bảng | **0,533241** | 0,451348 | **0,488889** | 1,733 | 85 |

Mỗi cấu hình có đủ 30 lượt hợp lệ. Baseline gồm 29 `success` và một
`empty_prediction`; ba cấu hình mới đều 30 `success`. Điểm tính trên đủ 853 dữ
kiện gold của 30 bài, gồm dự đoán rỗng. Baseline có 2 TP, 161 FP, 851 FN; cấu
hình được chọn có 385 TP, 337 FP, 468 FN. Ba kết quả baseline trùng pilot cũ
được kiểm tra lại: đầu ra và số forward giống hệt, không dùng lại thời gian cũ.

Thay tên schema là bước tạo mức cải thiện lớn nhất trong đối chiếu này.
Rút gọn mô tả tiếp tục tăng F1 và giảm số đoạn. Tách bảng tăng precision, nhưng
recall thấp hơn một chút và chậm hơn chế độ compact gộp bảng. Không có một cấu
hình tốt nhất ở mọi thước đo.

Quy tắc chọn đã ghi trước khi chạy: F1 cao nhất, hòa điểm chọn mean toàn lượt
thấp hơn. Vì vậy chọn **separate**. Chênh lệch F1 so với baseline là +0,484952,
CI95% bootstrap ghép cặp [0,436929; 0,539628]. So với compact, chênh lệch chỉ
+0,019841, CI95% [−0,019802; 0,062760] chứa 0: chưa có bằng chứng chắc rằng tách
bảng luôn hơn gộp bảng. Tỷ lệ thời gian separate/legacy 0,929943 có CI95%
[0,789379; 1,115819], không đủ để kết luận lợi thế tốc độ chắc chắn.

CI dùng 2.000 lần lấy mẫu lại tài liệu, seed 2026, không điều chỉnh việc chọn
cấu hình trên cùng tập. Đây là kết quả validation dùng lựa chọn, không được
so trực tiếp với điểm GPT trên 200 test hoặc coi là ước lượng test mới.

![So sánh trên cùng 30 validation](../outputs/gliner-validation-v1/validation_comparison.png)

## Các thay đổi đã áp dụng

- `schemas.py`: giữ tên có nghĩa cho cấu trúc và thuộc tính. Làm sạch ký hiệu
  encoder/parser, xử lý tên va chạm có hậu tố và ánh xạ về tên gốc; không mất
  trường. Chế độ opaque giữ nguyên để đối chiếu lịch sử.
- Mô tả compact giữ mô tả được cung cấp, kiểu và đơn vị, giảm phần nhắc lại.
  Không tự thêm cột hoặc cung cấp giá trị/định danh gold cho mô hình.
- `gliner2_adapter.py`: hỗ trợ joint/separate. Khi separate, mỗi bảng nhận toàn
  văn riêng, được chia theo giới hạn thực tế. Chuẩn bị các nhóm trước khi chạy;
  không gọi một phần rồi coi tài liệu là thành công khi nhóm khác vượt giới hạn.
  Số thứ tự chunk liên tục, không ghi đè sự kiện giữa bảng; tổng thời gian tính
  đầy đủ mọi lượt. Giữ giá trị xung đột, không dùng gold để chọn giá trị.
- Lệnh `gliner-validation`: đóng băng bốn biến thể và 30 ID, luân phiên thứ tự,
  dùng một model đã tải/làm nóng, ghi raw output/checkpoint và tổng hợp riêng.
  Không tạo GPT client; không nhận split test. Snapshot lưu nguồn trước chạy.
- Kiểm thử mới bắt lỗi sai người, nhầm points/rebounds/assists, giá trị không có
  trong bài, va chạm tên sau làm sạch, mất toàn văn hoặc ghi đè chunk khi tách bảng.

Checkpoint vẫn `fastino/gliner2-base-v1` revision
`8437ba583a733d87f56ae902f3b197934eedd58e`, CPU float32, 4 luồng, threshold 0.5,
seed 0. Tập validation seed 43 và bộ chấm chính được giữ nguyên.

## Kiểm thử và điểm yếu còn lại

**63/63 kiểm thử đạt**, gồm kiểm thử GLiNER2 thật kiểm tra chính xác từng ô ở các
ví dụ đơn giản và kiểm tra tích hợp toàn văn validation. Các kiểm thử logic
không thay dữ liệu thật của lượt đối chiếu.

Bốn ví dụ tự tạo bổ sung, không dùng chọn cấu hình và không nằm trong 30 bài,
cho thấy các hạn chế sau vẫn tồn tại:

| Tình huống | Quan sát ở cấu hình được chọn |
|---|---|
| 18 điểm trận trước, 24 điểm tối nay | Giữ cả 18 và 24 trong Points |
| 8 điểm hiệp đầu, 24 điểm cả trận | Trả Points=8 và nhầm rebounds=24 |
| Tên ở câu trước, “He” ở câu sau | Lấy đúng 24 points và seven rebounds |
| Hai người cùng ghi tổng 40 điểm | Gán 40 điểm cho từng người |

Các thử thách này là chẩn đoán, không phải kiểm thử đã đạt về năng lực tổng
quát. Mô hình vẫn cần xử lý thêm phạm vi thời gian, số liệu tổng nhóm và liên
kết thực thể. Chưa fine-tune hoặc thêm luật theo các ví dụ này. Recall mới
45,13% vẫn cho thấy nhiều dữ kiện bị bỏ sót theo gold; chưa đủ để tuyên bố tạo
bảng đầy đủ tự động. Alias/đơn vị và lỗi nhãn trong bộ dữ liệu vẫn là hạn chế.

Validation chưa loại sạch trùng trận do thiếu khóa ghép xác định; chỉ kiểm tra
trùng văn bản. Cần khóa cấu hình đã chọn rồi thực hiện lượt test mới trước khi
đưa ra so sánh mới với GPT. Giữ nguyên run cũ để truy nguyên.

## Tệp và cách chạy

- [Báo cáo tự sinh](../outputs/gliner-validation-v1/report.md)
- [Chỉ số CSV](../outputs/gliner-validation-v1/summary.csv)
- [Cấu hình được chọn](../outputs/gliner-validation-v1/selected_config.yaml)
- [Các thử thách ngữ cảnh](../outputs/gliner-diagnosis/context_challenges.json)
- [Nhật ký 63 kiểm thử](../outputs/gliner-diagnosis/final-regression-tests.log)
- [Kiểm tra bàn giao](../outputs/gliner-validation-v1/delivery_manifest.json)

```bash
# Tái tạo đối chiếu vào một thư mục mới, chỉ dùng GLiNER2 cục bộ.
.venv/bin/python -m rotowire_bench gliner-validation --config configs/gliner-validation.yaml --out outputs/gliner-validation-v2
# Tính lại từ log; không gọi mô hình.
.venv/bin/python -m rotowire_bench gliner-validation --out outputs/gliner-validation-v1 --report-only
```

Do `.gitignore` hiện loại source/config/output khỏi theo dõi, bản bàn giao có
snapshot nguồn và gói triển khai riêng; không dùng Git commit đơn lẻ làm phiên
bản của thay đổi này. Không chỉnh `.gitignore` hoặc tự commit/push.
