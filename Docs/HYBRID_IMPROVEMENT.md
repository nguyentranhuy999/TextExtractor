# Thử nghiệm cải tiến hybrid GPT 5.5 + GLiNER2

Ngày 14/09/2026. Phạm vi: phát triển trên 30 mẫu validation seed 43, không chạy lại 800 kết quả test. Bản kết quả cũ và thí nghiệm GLiNER2 biết trước trường được giữ riêng.

Thử nghiệm tiếp theo về vị trí đoạn trích đã hoàn tất: [SNIPPET_COMPARISON.md](SNIPPET_COMPARISON.md). Chia đầu–giữa–cuối trong cùng ngân sách làm F1 giảm trong lượt ghép cặp mới; giữ đoạn giữa. Các số hybrid v3 dưới đây vẫn là kết quả của lượt trước.

**Kết quả: bản mới chạy được 30/30 mẫu với schema hợp lệ, nhưng fact F1 còn 27,07%.** Sửa định dạng và cách mô tả chưa đủ để giải quyết cả thiếu trường lẫn lỗi gán dữ kiện của GLiNER2.

## Kết quả thực tế

| Chỉ số | Pilot v2, 3 mẫu | Pilot v3, 3 mẫu | Validation v3, 30 mẫu |
|---|---:|---:|---:|
| Schema hợp lệ | 3/3 | 3/3 | 30/30 |
| Schema có ít nhất một thuộc tính | 3/3 | 3/3 | 28/30 |
| Fact precision | 25,00% | 70,00% | 53,08% |
| Fact recall | 8,93% | 25,00% | 18,17% |
| Fact F1 | 13,16% | 36,84% | **27,07%** |
| Mean e2e, giây/bài | 10,544 | 10,006 | **10,753** |
| Tác vụ GPT đo / probe riêng | 3 / 1 | 3 / 1 | 30 / 1 |
| GLiNER2 forward passes | 4 | 3 | 47 |

Lượt 30 mẫu có **TP 155, FP 137, FN 698**, tổng **853 dữ kiện gold**. Median e2e 10,614 giây, p95 14,141 giây. Mean tạo schema qua Codex 9,748 giây; GLiNER2 0,992 giây; phần còn lại là chuẩn bị và hậu xử lý. Không có retry bên ngoài. Hai schema không có thuộc tính vẫn sinh hàng định danh nên trạng thái pipeline là `success`; không coi đây là hai schema hữu ích cho trích xuất giá trị.

Ba lượt dùng tổng cộng **39 phiên Codex mới**: 36 tác vụ theo mẫu và 3 probe riêng. Đã đối chiếu đủ 39 phiên: đúng GPT 5.5/low, ChatGPT, ngữ cảnh đã khóa, không công cụ, không dùng lại phiên. Đoạn gửi GPT khớp nguyên văn và đúng ngân sách. Mã pilot v3 và validation v3 giống nhau; 30 ID trùng thí nghiệm GLiNER2 validation trước. Băm 21 artifact của benchmark test cũ và 11 artifact của GLiNER2 validation cũ đều giữ nguyên.

## Phần độ chính xác còn mất ở đâu

Theo bộ chấm cố định, GPT đề xuất đúng **62/334 cặp bảng–trường** trong gold (recall trường **18,56%**), thiếu 272 cặp và có 24 cặp ngoài gold. Mỗi trường có thể chứa nhiều hàng, nên độ bao phủ dữ kiện khác độ bao phủ trường:

- **509/853 dữ kiện (59,67%)** thuộc cặp bảng–trường chưa được schema đề xuất khớp. GLiNER2 không thể xuất chúng qua các trường hiện có.
- **344/853 dữ kiện (40,33%)** thuộc trường đã được đề xuất. GLiNER2 lấy đúng **155/344 (45,06%)**, còn thiếu hoặc lấy sai 189 dữ kiện trong phần này.
- Ngoài ra có **137 dữ kiện dự đoán không khớp gold**, làm giảm precision.

Do đó, không nên quy toàn bộ F1 thấp cho đoạn trích hoặc cho riêng GLiNER2. Đoạn ngắn và cách đặt tên hạn chế bộ trường; GLiNER2 vẫn gặp lỗi đối tượng, giá trị và phạm vi ngay khi đã có trường. Nếu giả định trích xuất hoàn hảo, không FP và giữ nguyên schema đã sinh, trần F1 theo bộ chấm là 57,48% — đây là phép tính giới hạn, không phải kết quả mô hình đạt được.

![Phân rã bao phủ dữ kiện](../outputs/hybrid-validation-v3/coverage.png)

Kiểm tra định tính ba ví dụ sau bởi Codex, không phải đánh giá mù của người độc lập:

| Mẫu validation | Quan sát từ văn bản và kết quả |
|---|---|
| `0157-35ff0daddd8f` | GPT tạo bảng `player group` cho tổng của Gallinari và Mudiay. GLiNER2 vẫn tạo hàng mang tên từng người, thậm chí lấy điểm của Barton/Nurkic vào nhóm; chỉ dẫn phạm vi chưa sửa được hành vi gán bản ghi. |
| `0560-039d271e9e2e` | GLiNER2 lấy đúng 16 điểm của Belinelli, nhưng trường `Bench points` không khớp `Points` trong alias cố định. Đây là ví dụ mất điểm do phạm vi/tên trường, không phải con số bịa ra. Không sửa alias sau chạy. |
| `0442-e6144f60a0d3` | Có dòng 23 điểm không xác định được tên và có dòng Anthony bị gán 9 điểm từ thông tin rebound. Schema đã có points/rebounds/assists/steals nhưng vẫn sai liên kết người–thuộc tính–giá trị. |

Với ứng dụng đã biết bộ trường cần lấy, cấu hình GLiNER2 dùng schema cố định là bước thực tế hơn việc bắt GPT suy đoán schema từ một đoạn ngắn. Nếu mục tiêu vẫn là tự tìm trường, cần nghiên cứu riêng cách tăng độ bao phủ đoạn/schema và cách trích xuất quan hệ/phạm vi; tăng ngưỡng đơn thuần không lấy lại được trường thiếu. Các phương án đọc thêm đoạn hoặc dùng toàn bài sẽ thay điều kiện SPEC và chưa được chạy trong lần bàn giao này. Chưa có căn cứ để tuyên bố nhánh hybrid mới hơn GPT trực tiếp hoặc đã giải quyết xong lỗi phạm vi.

## Thay đổi đã triển khai

`rotowire_bench/prompts/short_schema.txt` tách rõ khóa định danh với thuộc tính, yêu cầu tên bảng là danh từ chỉ loại đối tượng và tên thuộc tính dễ đọc. Mô tả ngắn phải giữ đúng phạm vi: thống kê từng hiệp khác tổng cả trận; tổng của nhóm người khác số liệu của từng người. GPT chỉ đề xuất thuộc tính được đoạn trích hỗ trợ, không được điền danh mục cột thường gặp.

`ProposedExtractionSchema` áp dụng riêng cho schema GPT tạo. Nhãn thuộc tính cho phép chữ/số tiếng Anh, khoảng trắng và dấu gạch nối, nên khóa có dấu gạch dưới `entity_name` không thể xuất hiện trong danh sách thuộc tính. Ràng buộc này có trong cả JSON Schema gửi cho Codex lẫn kiểm tra Python. Kiểm tra trùng tên vẫn ở Python; JSON Schema không bảo đảm tính duy nhất theo một thuộc tính con. Khung schema biết trước của nhóm A giữ nguyên, bao gồm quyền dùng tên cột gốc có dấu câu.

JSON Schema `pattern` được tài liệu [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) hỗ trợ; cách dùng `--output-schema` được mô tả trong [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode). Đã kiểm tra hoạt động thực tế bằng các probe và pilot, không chỉ dựa vào tài liệu.

GLiNER2 dùng cấu hình đã chọn trước: tên có nghĩa, mô tả gọn, tách bảng, CPU float32/4 luồng, ngưỡng 0.5; checkpoint base-v1 đã ghim. Mỗi bảng vẫn đọc toàn bài. Không sửa trọng số, alias, gold, ngưỡng hay quy tắc ghép giá trị. GPT vẫn là `gpt-5.5`, low, qua Codex CLI/ChatGPT, mỗi tác vụ một phiên mới và không dùng công cụ. Đoạn giữa nguyên văn giữ nguyên ngân sách `min(80, N//10)` từ.

## Trình tự và tính tái lập

Pilot `outputs/hybrid-pilot-v2` chạy 3 mẫu và có 3 schema hợp lệ. Tuy nhiên, tên bảng như `Player Game Stats` không được từ điển chấm đã khóa nhận diện. Sau đó chỉ dẫn đặt tên bảng được làm rõ, và nhãn thuộc tính được phép bắt đầu bằng chữ số. Giữ nguyên toàn bộ kết quả pilot này; không sửa tên trong đầu ra đã chạy hoặc mở rộng alias để tăng điểm.

Pilot `outputs/hybrid-pilot-v3` kiểm tra lại cùng 3 ID bằng các phiên mới. Bản mã này được khóa để chạy `outputs/hybrid-validation-v3` trên đủ 30 mẫu. Ba mẫu pilot được suy luận mới khi xuất hiện trong lượt 30; không tái sử dụng dự đoán hoặc lấy câu trả lời tốt hơn. Pilot và validation được báo riêng.

Lệnh `hybrid-validation` chỉ chạy nhánh `B_HYBRID_SHORT`. Mỗi thư mục có `protocol.lock.json`, mã nguồn snapshot, manifest, đầu vào, đoạn trích, schema dự đoán, sự kiện Codex/GLiNER2, bảng kết quả và thời gian. `schema_coverage.json` chấm bộ trường GPT đề xuất ngay trước GLiNER2; trường đã được đề xuất vẫn được ghi nhận trong chỉ số phụ này nếu bước trích xuất gặp lỗi. Điểm dữ kiện cuối vẫn tính lỗi là dự đoán rỗng.

```bash
.venv/bin/python -m rotowire_bench hybrid-validation --out outputs/hybrid-pilot-new --limit 3
.venv/bin/python -m rotowire_bench hybrid-validation --out outputs/hybrid-validation-new --limit 30
.venv/bin/python -m rotowire_bench hybrid-validation --out outputs/hybrid-validation-v3 --report-only
```

Kiểm thử trước bản cuối: `RUN_GLINER_INTEGRATION=1 PYTHONHASHSEED=0 .venv/bin/python -m pytest -q` — **67 passed, 20.24 giây**, gồm GLiNER2 thật. Kiểm thử mới kiểm tra khóa dành riêng bị chặn ở JSON Schema, không gọi GLiNER2/sửa lại khi schema sai, giữ tên thống kê theo hiệp, tính trường thiếu, tính lỗi vào FN, resume không chạy lại mẫu đã hoàn thành và phát hiện kết quả bị sửa băm.

## Giới hạn khi diễn giải

Schema hợp lệ về cấu trúc không bảo đảm đúng nghĩa hoặc đủ trường. Không có baseline prompt cũ chạy ghép cặp trên đủ 30 mẫu trong thử nghiệm này, nên chưa thể tách tác động của từng thay đổi hay khẳng định mức tăng F1/thời gian so với 200 mẫu test cũ. Không so sánh trực tiếp điểm validation mới với GPT trên test cũ.

Các chỉ số thiếu trường tuân theo alias đã khóa: một tên chưa có ánh xạ có thể bị tính là trường khác dù người đọc thấy gần nghĩa. Phân tích bao phủ không tự phân biệt được mọi trường bị bỏ sót do đoạn ngắn với trường có nghĩa tương đương nhưng đặt tên khác. Thống kê theo hiệp và nhóm có thể đúng theo văn bản nhưng không thuộc các ô gold tương ứng; không được gán số đó sang cá nhân/cả trận để khớp nhãn.

Validation chỉ kiểm tra trùng văn bản, chưa loại sạch trùng trận với test. Đây là kết quả phát triển, không phải ước lượng test độc lập. Tên GPT là alias phía dịch vụ; không biết snapshot trọng số hoặc số lần suy luận nội bộ. Thời gian gồm khởi chạy Codex, mạng, GPT tạo schema, GLiNER2 và hậu xử lý; tải mô hình/làm nóng, probe và chấm điểm được tách riêng.

## Artifact bàn giao

- [Kết quả và log validation](../outputs/hybrid-validation-v3/): `metrics.json`, `metrics_per_sample.csv`, `schema_coverage.json`, `scores_per_sample.json`, `diagnostics.json`, `inference_audit.json` và `source_snapshot.zip`.
- [Gói mã và kết quả](../outputs/hybrid-validation-v3/delivery_package.zip), gồm hai pilot, validation cuối, cấu hình, kiểm thử và tài liệu.
- [Script kiểm tra sau chạy](../outputs/hybrid-analysis/analyze.py): `PYTHONPATH=. .venv/bin/python outputs/hybrid-analysis/analyze.py`. Chỉ đọc/chấm log, không gọi mô hình. Script xác minh băm nguồn hiện tại nên cần dùng đúng bản mã đã khóa.
