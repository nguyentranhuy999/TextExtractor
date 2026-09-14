# Chạy lại 200 mẫu test — hybrid GPT 5.5 + GLiNER2

**Đã hoàn tất 200/200 mẫu test**, run `outputs/hybrid-test-v3`. Chỉ chạy `B_HYBRID_SHORT`; không chạy lại GPT trực tiếp. Fact F1 của hybrid mới là **25,46%**, precision **46,03%**, recall **17,59%**.

## Kết quả cuối

| Chỉ số | Hybrid mới | GPT trực tiếp, lượt cũ |
|---|---:|---:|
| Số mẫu test | 200 | 200 |
| TP / FP / FN | 1083 / 1270 / 5073 | 664 / 7501 / 5492 |
| Precision | 46,03% | 8,13% |
| Recall | 17,59% | 10,79% |
| Fact F1 | **25,46%** | **9,27%** |

GPT trực tiếp được lấy nguyên kết quả `B_GPT_DIRECT` của `rotowire-codex-main-v1`, gồm cả mẫu timeout. Đây là đối chiếu theo cùng bộ chấm và 200 ID, với baseline lịch sử. Chênh F1 hybrid mới trừ GPT trực tiếp cũ: **+16.18 điểm phần trăm**, CI95 **[+11.89; +20.18]**, bootstrap ghép cặp theo tài liệu 2000 lần, seed 2026. CI không đo toàn bộ biến thiên qua các lần gọi GPT hoặc việc alias mô hình thay đổi phía dịch vụ. Không diễn giải kết quả này như kết luận năng lực tổng quát của hai mô hình.

Hybrid có **200/200 schema hợp lệ**, **187/200 schema có thuộc tính**, **200/200 đầu ra hợp lệ**. Trạng thái: `{"empty_prediction": 4, "success": 196}`. Macro fact F1: 20,72%; F1 định danh: 69,71%; tỷ lệ tài liệu đúng toàn bộ: 0,00%.

Thời gian hybrid: mean **12,020 giây/bài**, median **11,552**, p95 **18,126**; mean trên đầu ra hợp lệ **12,020 giây/bài**. Mean bước GPT tạo schema **10,696 giây**; GLiNER2 **1,310 giây**. Tổng GLiNER2 forward: **339**. Tải mô hình/làm nóng, probe và chấm điểm không nằm trong các số đo này. Không tính tỷ số tốc độ với GPT trực tiếp cũ vì hai lượt không chạy xen kẽ cùng thời điểm.

## Những dữ kiện còn thiếu

Theo cặp bảng–trường của bộ chấm cố định, schema GPT bao phủ **2395/6156 dữ kiện gold (38,91%)**. Có **3761 dữ kiện** thuộc trường chưa được đề xuất khớp. Trong phần có trường, **1083 dữ kiện** được trích xuất đúng và **1312 dữ kiện** chưa khớp.

Độ bao phủ này bao gồm ảnh hưởng của việc thiếu trường và tên bảng/trường chưa khớp alias; không đồng nghĩa mọi trường bị thiếu đều vắng trong đoạn trích. Không sửa alias sau chạy. Phần sai còn lại không chỉ do schema: GLiNER2 vẫn có thể bỏ sót hoặc gán nhầm đối tượng, giá trị và phạm vi. Phân rã này là mô tả kết quả, không phải đề xuất chỉnh theo test.

![Chất lượng hybrid và baseline lịch sử](../outputs/hybrid-test-v3/quality.png)

## Kiểm chứng và artifact

Đã xác minh **200 lượt thử Codex theo mẫu**, **1 probe/lượt thử thiết lập**, **201 phiên mới riêng** và **201 audit hợp lệ**. Mọi yêu cầu theo mẫu chỉ là tạo schema từ đoạn giữa. ID/gold/đoạn trích và tám thành phần suy luận khớp bản đã khóa; chunk GLiNER2 phủ toàn bài. Kết quả lịch sử được kiểm tra băm, không sửa/đo lại.

Kiểm thử trước test: **84 passed, 23.12 giây**, gồm GLiNER2 thật. Xem `test_validation.json` và `inference_audit.json`.

- [Kết quả JSON](../outputs/hybrid-test-v3/metrics.json), [CSV từng mẫu](../outputs/hybrid-test-v3/metrics_per_sample.csv), [cầu thủ/đội](../outputs/hybrid-test-v3/table_breakdown.json).
- [Xem đủ 200 mẫu trong HTML](../outputs/hybrid-test-v3/samples.html): toàn bài, đoạn trích, schema, dự đoán, gold và lỗi theo bộ chấm. Gold chỉ dùng trong phân tích sau chạy.
- [Đối chiếu baseline lịch sử](../outputs/hybrid-test-v3/historical_comparison.json), [phân tích thiếu dữ kiện](../outputs/hybrid-test-v3/diagnostics.json).
- [Gói nguồn, cấu hình và kết quả](../outputs/hybrid-test-v3/delivery_package.zip). `source_snapshot.zip` bảo toàn bản nguồn suy luận.

20 ID rà soát được chọn trước trong manifest đã được xuất vào `predetermined_review_cases.json`; tệp này không được coi là đánh giá mù hay xác nhận đã hoàn tất rà soát độc lập của con người.

## Cấu hình khóa trước test

- Cùng 200 ID seed 42 và cùng gold/manifest của `rotowire-codex-main-v1`. Đầu vào tiếng Anh nguyên bản.
- GPT 5.5 low qua Codex CLI 0.154.0-alpha.6.2, tài khoản ChatGPT, phiên mới mỗi tác vụ, không công cụ. Giữ nguyên prompt/JSON Schema của hybrid v3 đã kiểm tra trên validation.
- GPT nhận một đoạn giữa nguyên văn, đúng `B=min(80,N//10)` từ whitespace. Không dùng biến thể đầu–giữa–cuối và không đọc toàn bài để tạo schema.
- GLiNER2 `fastino/gliner2-base-v1`, revision `8437ba583a733d87f56ae902f3b197934eedd58e`, CPU float32, 4 luồng, batch 1, ngưỡng 0.5. Tên trường có nghĩa, mô tả gọn, tách bảng; mỗi bảng đọc toàn bài bằng các chunk có biên kiểm tra được.
- Không đổi trọng số, ngưỡng, alias, gold hoặc quy tắc chuẩn hóa theo điểm test. Lỗi được giữ lại, không thay mẫu và không gọi GPT sửa đầu ra để lấy câu trả lời tốt hơn.

Đã đối chiếu trước chạy: 200 ID, manifest và đoạn giữa giống lượt test cũ; tám thành phần suy luận gồm prompt, schema, bộ chọn đoạn, pipeline, hai adapter, scorer và alias khớp bản đã kiểm tra trên validation. Chỉ mở rộng bộ điều phối/báo cáo để chạy riêng 200 mẫu hybrid.

## Cách đo và đối chiếu

Mỗi mẫu được đo từ lấy đoạn đến kết quả cuối, bao gồm GPT tạo schema, tất cả GLiNER2 forward, hậu xử lý và thời gian chờ thử lại nếu có. Tải mô hình/làm nóng và probe ngoài dữ liệu đánh giá được ghi riêng. Chạy tuần tự, thứ tự tài liệu xáo bằng seed 44; không gọi GPT trực tiếp xen kẽ vì người dùng yêu cầu dùng kết quả trước đó.

Precision/recall/F1 dữ kiện dùng đủ 200 mẫu khi chiến dịch hoàn tất, gồm lỗi như dự đoán rỗng. Báo thêm macro F1, schema hợp lệ, độ bao phủ trường/dữ kiện bằng schema, F1 định danh, thống kê cầu thủ/đội và thời gian toàn lượt/hợp lệ. Các kết quả tạm khi chưa đủ 200 mẫu không được gọi là điểm test cuối.

Nếu đối chiếu GPT trực tiếp cũ, dùng đúng đầu ra đã lưu trên cùng ID và bộ chấm gốc, gồm cả mẫu timeout cũ. Đây là **baseline lịch sử**. Điểm chất lượng có thể đối chiếu theo bộ chấm cố định; thời gian hai lượt được đo ở thời điểm khác nhau, nên không diễn giải tỷ lệ thời gian như một phép so sánh xen kẽ cùng điều kiện dịch vụ. Không sửa đầu ra GPT cũ hoặc chuyển sang nhánh biết trước trường để làm baseline.

Tập validation đã dùng phát triển và chưa loại sạch trùng trận. Mô hình GPT là alias dịch vụ, không biết snapshot trọng số hoặc số lần suy luận nội bộ. Các giới hạn này tiếp tục áp dụng khi diễn giải lượt test mới.

## Chạy lại và kiểm tra

```bash
.venv/bin/python -m rotowire_bench hybrid-test --out outputs/hybrid-test-new
.venv/bin/python -m rotowire_bench hybrid-test --out outputs/hybrid-test-new --resume
.venv/bin/python -m rotowire_bench hybrid-test --out outputs/hybrid-test-v3 --report-only
```

`--max-tasks N` dừng sau tối đa N mẫu mới trong phiên điều phối; không chọn lại hay rút gọn tập 200. Resume giữ các kết quả đã thử, kể cả lỗi. Nếu đã có sự kiện bắt đầu một tác vụ nhưng thiếu checkpoint, chương trình từ chối gửi lại âm thầm. Cấu hình/mã thay đổi cần thư mục run mới. Resume một lượt hoàn tất và report-only không gọi mô hình; resume còn việc dùng probe riêng, không ghi đè log probe cũ.

Kiểm thử trước khi khóa: **84 passed, 23.12 giây**, bằng `RUN_GLINER_INTEGRATION=1 PYTHONHASHSEED=0 .venv/bin/python -m pytest -q`, gồm GLiNER2 thật. Kiểm thử mới xác nhận chỉ gọi nhánh hybrid, giữ đủ 200 ID, đếm lỗi vào FN, checkpoint/resume không đo lại mẫu đã xong, không phát probe khi đã hoàn tất, từ chối thiếu ID và không gửi lại tác vụ bị gián đoạn. Bộ chạy validation cũng từ chối resume nhầm một thư mục con của thí nghiệm ghép cặp.
