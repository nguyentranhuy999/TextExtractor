# Kết quả SPEC 1.2 — GLiNER2 cục bộ và GPT 5.5 trong Codex

> Hybrid đã có lượt validation riêng sau sửa prompt/schema: [HYBRID_IMPROVEMENT.md](HYBRID_IMPROVEMENT.md), 30/30 schema hợp lệ, fact F1 27,07%. Không thay số đo test lịch sử dưới đây bằng số đo validation.

> Đã hoàn tất lượt cải thiện trên 30 validation: xem [GLINER_IMPROVEMENT.md](GLINER_IMPROVEMENT.md). Điểm 200 test dưới đây vẫn thuộc adapter cũ.


> **Cập nhật chẩn đoán sau benchmark:** phép thử ba ví dụ ngoài tập test phát hiện
> biểu diễn schema `t0/f0` trong adapter làm trích xuất kém hơn rõ so với tên có
> nghĩa khi giữ nguyên mô tả. Số đo dưới đây vẫn là kết quả thật của pipeline đã
> khóa, nhưng chưa đủ để kết luận về năng lực GLiNER2 hoặc mức thua kém của mô hình.
> Xem [bằng chứng và giới hạn phép thử](../outputs/gliner-diagnosis/README.md).

**Đã hoàn tất 800/800 công việc thực sự được thử**, bốn nhánh trên cùng 200 ID
test RotoWire. Run duy nhất: `rotowire-codex-main-v1`. Không có blocked/pending,
không thay mô hình, không trộn kết quả SPEC 1.1 và không sửa cấu hình theo test.

Chạy từ 06:42:02 đến 09:46:09 ngày 14/09/2026 (UTC+07), khoảng 3 giờ 04 phút
theo lịch. Đồng hồ đơn điệu của vòng chạy ghi 10.921,228 giây, chưa cộng tải
GLiNER2 7,092 giây và làm nóng 0,349 giây. Một lần máy ngủ ảnh hưởng chênh lệch
giữa hai loại thời gian; xem phần giới hạn bên dưới.

## A — cùng biết trước trường

| Phương pháp | Hợp lệ / đã thử | Fact micro F1 | Precision | Recall | Mean hợp lệ (giây) | P95 hợp lệ (giây) |
|---|---:|---:|---:|---:|---:|---:|
| GLiNER2 | 198 / 200 | 0,007745 | 0,021755 | 0,004711 | 3,268 | 10,729 |
| GPT 5.5 trong Codex | 200 / 200 | 0,686760 | 0,721596 | 0,655133 | 17,393 | 26,636 |

GLiNER2 đạt khoảng **1,13% mức F1 của GPT** theo bộ chấm đã khóa. Chênh lệch
F1 GLiNER2 − GPT là −0,679016; CI95% [−0,719384; −0,633550]. Trên 198 ID hợp
lệ ở cả hai nhánh, tỷ lệ tổng thời gian GLiNER2/GPT là **0,188741**, CI95%
[0,140648; 0,245608], tương đương thời gian thấp hơn khoảng 81,1% trên tập cặp
này. Lỗi giới hạn đầu vào của GLiNER2: 2/200; GPT: 0/200.

GLiNER2 có 29 TP, 1.304 FP và 6.127 FN; GPT có 4.033 TP, 1.556 FP và 2.123 FN.
Field F1 của nhóm A gần 1 chủ yếu vì được cung cấp tiêu đề gold, không chứng
minh lấy đúng giá trị. Exact-document rate lần lượt 0% và 1,5%.

## B — GPT đọc đoạn ngắn rồi GLiNER2, so với GPT đọc toàn bài

| Phương pháp | Hợp lệ / đã thử | Fact micro F1 | Field F1 | Entity F1 | Mean hợp lệ (giây) | P95 hợp lệ (giây) |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid, đoạn giữa ≤10%, ≤80 từ | 56 / 200 | 0,000621 | 0,034026 | 0,042597 | 11,853 | 17,996 |
| GPT 5.5 trực tiếp | 199 / 200 | 0,092731 | 0,173279 | 0,293022 | 21,198 | 32,260 |

**56 đầu ra hợp lệ của hybrid gồm 52 trạng thái `success` và 4 schema rỗng**.
Theo quy tắc báo cáo đã khóa, `empty_prediction` là đầu ra hợp lệ và được tính
vào `n_success` cùng thời gian hợp lệ; chất lượng của chúng vẫn tính dự đoán
rỗng trên gold. Đây không phải 56 lượt lấy được dữ kiện đúng. Hybrid có 141
schema lỗi tên trùng/dành riêng và 3 lỗi giới hạn đầu vào, tức tỷ lệ lỗi 72%.
Direct có một timeout, tỷ lệ lỗi 0,5%.

Chênh lệch F1 hybrid − direct là −0,092110; CI95% [−0,124225; −0,064005].
Tỷ lệ tổng thời gian hybrid/direct trên **56 cặp hợp lệ, gồm 4 hybrid rỗng** là
**0,620676**, CI95% [0,587854; 0,659408]. Thời gian hybrid bao gồm tạo schema
bằng Codex và toàn bộ bước GLiNER2. Không coi thời gian lỗi nhanh là lợi thế.
Chất lượng chính vẫn dùng đủ 200 bài, không chỉ 56 cặp này.

Hybrid có 2 TP, 283 FP, 6.154 FN; direct có 664 TP, 7.501 FP, 5.492 FN.
Theo giao thức này, mức khớp gold rất thấp của hybrid không hỗ trợ lựa chọn
phương án hiện tại để thay direct chỉ nhằm giảm độ trễ.

## Nguồn lỗi và phạm vi ứng dụng

141 schema bị validator từ chối tạo 4.586 FN. Ba lỗi giới hạn tạo 238 FN, bốn
schema rỗng tạo 43 FN. Trong 52 lượt hybrid `success`, còn 1.095 FN thiếu trường,
172 FN thiếu định danh và 20 FN thiếu/sai giá trị. Tổng `missing_field` là 5.962,
nhưng không thể quy toàn bộ cho đoạn ngắn: nó gồm lỗi validator và tên bảng
ngoài alias. Các nhóm lỗi tự động không xác định quan hệ nhân quả.

Đối chiếu 20 ID chọn trước cho thấy cả thiếu bao phủ của đoạn và sai liên kết
đối tượng–giá trị. Ví dụ `test-0606-ff5842541825` có schema hybrid hợp lệ nhưng
thiếu assists/shooting/minutes; GLiNER2 còn gắn số vào đội trong bảng cầu thủ.
Ở `test-0591-bcb50c8436d6`, đoạn chứa nhiều thống kê nhưng schema vẫn lỗi tên
trường, nên không thể giải thích thất bại chỉ bằng độ ngắn của đoạn.

GLiNER2 có thể lấy đúng một số dữ kiện riêng lẻ, như Spurs turnovers=14 ở
`test-0069-104100335ae2`, với độ trễ cục bộ thấp. Tuy nhiên recall 0,47% và không
có tài liệu khớp hoàn toàn ở nhóm A chưa cung cấp bằng chứng rằng cấu hình này
đáp ứng ứng dụng tự động tạo bảng thống kê đầy đủ. Nếu dùng làm đầu ra gợi ý,
cần kiểm tra đối tượng, giá trị và độ bao phủ; chưa có ngưỡng ứng dụng nào được
đặt để tuyên bố đạt. Những thay đổi schema/adapter hoặc huấn luyện là nghiên
cứu tiếp theo, cần run mới và không nằm trong số đo này.

## Những giới hạn ảnh hưởng trực tiếp đến điểm

- Từ điển đã khóa không nhận mọi cách đặt tên bảng tự do, ví dụ
  `player_game_stats`/`team_game_stats`. Nhiều ô đúng theo bài vẫn bị FP/FN.
- `25 points`, `28 minutes`, `18 dimes` không được bộ chuẩn hóa chuyển thành số
  thuần. Khớp tên cũng không dùng fuzzy/kiến thức ngoài; khác biệt C.J./CJ,
  Milwaukee/Bucks hoặc Jared/Jerryd Bayless có thể bị phạt.
- Gold có ô đáng nghi và thiếu dữ kiện được bài phát biểu. Đã đối chiếu lỗi đại
  diện của cả bốn nhánh trên 20 ID; đây là rà soát bởi Codex, chưa được con người
  xác nhận độc lập. Không sửa nhãn hoặc công bố điểm đã điều chỉnh.
- Máy ngủ idle 128 giây trong lượt direct `test-0637-1821abdaad53`; giữ timeout
  300 giây theo đồng hồ đơn điệu, không chạy lại. Sau đó ngăn idle sleep theo
  PID chiến dịch; tiến trình hỗ trợ đã tự kết thúc cùng benchmark.
- Metadata cửa sổ hạn mức Codex thay đổi trong lúc chạy, nguyên nhân chưa biết.
  Không đổi auth/tài khoản, không mua hạn mức. Model/effort/context quan sát
  được vẫn qua audit ở đủ 600 phiên.

Điểm là mức khớp của toàn pipeline với gold theo giao thức đã khóa, không phải
đánh giá ngữ nghĩa không phụ thuộc định dạng. Phạm vi 200 bài bóng rổ, một
checkpoint/mức suy luận; chưa kiểm chứng nhiễm dữ liệu tiền huấn luyện và chưa
loại sạch trùng trận do thiếu khóa ghép. GPT gồm CLI/mạng/máy chủ từ xa, không
so tốc độ tính toán cùng phần cứng. Trọng số và chỉ dẫn máy chủ không công bố
vẫn chưa biết. CI lấy mẫu lại tài liệu 2.000 lần, seed 2026, không mô tả toàn bộ
ngẫu nhiên của mô hình.

## Xác minh và hồ sơ bàn giao

Môi trường: Apple M1, RAM 16 GiB, macOS 26.6.2 ARM64; Python 3.11.14; GLiNER2
1.2.4, CPU float32/4 luồng; checkpoint `fastino/gliner2-base-v1` revision
`8437ba583a733d87f56ae902f3b197934eedd58e`. Codex CLI 0.154.0-alpha.6.2,
ChatGPT auth, `gpt-5.5`, low; không dùng API key.

600/600 tác vụ chính có payload khớp, phiên riêng và audit `verified`, không
có vi phạm công cụ được phát hiện. Có 600 lần khởi chạy CLI chính, không có
retry bên ngoài; số gọi/retry mô hình nội bộ chưa biết. GLiNER2 có 1.426 lượt
forward thực tế (1.322 nhóm A, 104 hybrid). Pilot validation 12 công việc, gồm
9 tác vụ GPT, được giữ riêng. Ba preflight và một probe CLI có log được đếm
riêng trong `auxiliary_runs.json`, không vào 800 kết quả test.
Danh sách UI xuất 600 tác vụ chỉ là tệp chuẩn bị, không phải lượt suy luận.

**56/56 kiểm thử đạt**, gồm integration GLiNER2 thật, sau khi benchmark kết
thúc. Nguồn đóng băng được lưu trong `source_snapshot.zip`; manifest bàn giao
kiểm tra đủ 200 ID/nhánh và băm 21 tệp nguồn. Không dùng mã commit Git đơn lẻ
để đại diện nguồn vì `.gitignore` hiện loại mã/config/output khỏi theo dõi.

- [Báo cáo đầy đủ](../outputs/rotowire-codex-main-v1/report.md)
- [Xem từng mẫu và lỗi](../outputs/rotowire-codex-main-v1/samples.html)
- [Tất cả chỉ số, phân vị, throughput](../outputs/rotowire-codex-main-v1/summary.csv)
- [Rà soát 20 ID](../outputs/rotowire-codex-main-v1/model_review.md)
- [Giới hạn và điều kiện thực thi](../outputs/rotowire-codex-main-v1/interpretation_notes.md)
- [Trạng thái chiến dịch](../outputs/rotowire-codex-main-v1/campaign.json)
- [Kiểm tra bàn giao và băm tệp](../outputs/rotowire-codex-main-v1/delivery_manifest.json)

Đánh giá lại không gọi mô hình:

```bash
.venv/bin/python -m rotowire_bench report --run-dir outputs/rotowire-codex-main-v1
```

Kết quả SPEC 1.1 nằm riêng ở [RESULTS_SPEC_1_1.md](RESULTS_SPEC_1_1.md).
