# Cập nhật cải thiện GLiNER2 sau SPEC 1.2

Nhánh hybrid hiện dùng `ProposedExtractionSchema` và prompt phân biệt định danh/thuộc tính, tên bảng theo loại đối tượng và phạm vi thống kê. Có lệnh `hybrid-validation` cùng phép đo bao phủ trường trước GLiNER2. Đã chạy pilot và đủ 30 validation, xem [HYBRID_IMPROVEMENT.md](HYBRID_IMPROVEMENT.md). Mọi run cũ vẫn dùng snapshot riêng.

Adapter hiện dùng tên schema có nghĩa, mô tả ngắn và tách bảng theo kết quả
120 công việc trên 30 validation. Xem [GLINER_IMPROVEMENT.md](GLINER_IMPROVEMENT.md).
Cấu hình này chưa được chạy lại trên 200 test; số đo SPEC 1.2 bên dưới là lịch sử
của adapter cũ. Không dùng nguồn mới để resume run cũ đã khóa.

---

# Cập nhật SPEC 1.2 — Codex qua tài khoản ChatGPT

Đã đọc đầy đủ `Docs/SPEC copy.md` (444 dòng). Bản cập nhật bỏ yêu cầu API key,
chuyển nhánh GPT chính sang `models/codex_gpt55_adapter.py` và `codex exec`.
CLI được kiểm tra là 0.154.0-alpha.6.2; `codex login status` xác nhận ChatGPT;
rollout của từng phiên xác nhận gpt-5.5 và low. Không đọc/chép bí mật đăng nhập.

Các phần mới đã thực hiện:

- Phiên và cwd mới từng tác vụ, stdin/JSON Schema, câu trả lời nguyên bản,
  events/exit code/session ID/timestamps; không resume/fork hội thoại.
- Tắt tính năng công cụ, plugin/kết nối/ký ức qua cài đặt hỗ trợ; giữ chính sách
  quyền. Kiểm tra lại ngữ cảnh và mọi sự kiện công cụ, sai giao thức chấm lỗi.
  Chỉ dẫn nền và danh mục hệ thống tự nạp còn lại được băm và lưu làm điều kiện
  thí nghiệm, không giả định đây là API trần hoặc biết hết chỉ dẫn máy chủ.
- Kiểm tra model/effort/version/context hash; dùng auth ChatGPT, không fallback.
  Timeout 300 giây kết thúc nhóm tiến trình; retry có log cho lỗi tạm thời;
  quota/auth/model access dừng nhánh GPT. Hỗ trợ max-tasks/max-seconds và resume.
- Tệp `external_tasks.py`: xuất/nhập UI riêng, kiểm tra ID/băm/trùng/phiên mới,
  giữ nguyên raw answer, lỗi JSON vẫn được chấm, thiếu câu trả lời là pending_external.
  Thời gian UI GPT/hybrid null; không nhập UI vào chiến dịch CLI.
- Báo cáo thêm execution_mode, n_codex_attempts, số mẫu có thời gian; đổi
  schema_api_ms thành schema_codex_ms. Số lượt gọi/retry mô hình nội bộ chưa biết.
- README và notebook đã chuyển sang hướng dẫn đăng nhập ChatGPT.

Kiểm thử cuối sau khi chiến dịch kết thúc: **56/56 đạt**, có bật GLiNER2
integration thật, 12,02 giây. Log: `outputs/codex-setup/final-tests.log`.
Pilot `outputs/pilot-codex-v1` đã thử 12/12 công việc validation: A_GLINER 3/3,
A_GPT 3/3, hybrid 2/3, direct 3/3 đầu ra hợp lệ. Một schema dùng tên trường định
 danh dành riêng bị từ chối; giữ lỗi, không sửa bằng LLM. Tất cả 9 tác vụ GPT
pilot có audit verified. Kết quả pilot không nằm trong 200 test.

Lượt chính `outputs/rotowire-codex-main-v1` đã thử **800/800 công việc**, không
còn blocked/pending. Có 649 trạng thái success, 4 đầu ra rỗng hợp lệ và 147 lỗi;
bộ tổng hợp tính 4 đầu ra rỗng trong n_success, công khai tại [RESULTS.md](RESULTS.md).
Audit đạt 600/600 phiên GPT độc lập, đúng model/low/context; đã rà soát lỗi đại
diện của 20 ID chọn trước, chưa có xác nhận độc lập của con người. Không sửa gold.
Danh sách UI 600 tác vụ đã xuất tại outputs/codex-ui-tasks-v1,
chưa nhập câu trả lời và không được coi là thêm 600 lượt thử.

Các kết quả API bị chặn/GLiNER2 trước đây được giữ nguyên; không trộn thời gian
hoặc đầu ra từ chúng vào lượt Codex. Mục dưới là hồ sơ triển khai lịch sử 1.1.

---

# Bàn giao triển khai SPEC 1.1

## Phần đã triển khai

| Yêu cầu | Mã và bằng chứng kiểm tra |
|---|---|
| Bản RotoWire Text-to-Table, giữ cặp dòng, bảng trống | `rotowire_bench/data.py`; kiểm tra nguồn thật 728 test, 727 validation; tests/test_data_schema.py |
| 200 test seed 42, 30 validation seed 43, 20 ID rà soát chọn trước | `data/prepared/sample_manifest.json`; băm văn bản/gold và thứ tự gốc |
| Không rò rỉ gold | InferenceInput riêng; known_schema chỉ đọc tên bảng/cột; payload B không nhận schema A; kiểm thử số sentinel |
| Đoạn liên tục giữa bài, 10%, tối đa 80 từ | `snippets.py`; kiểm thử cả biên ngắn 0–9 từ, khoảng trắng và băm |
| Hai mô hình đúng phiên bản | GPT `gpt-5.5-2026-04-23`; GLiNER2 base commit cố định; không thay GLiNER2.5/LLM khác |
| Structured Outputs và 3 prompt tiếng Anh | `models/gpt55_adapter.py`, `prompts/`; kiểm tra JSON Schema bắt buộc mọi khóa, không enum cột nhóm B |
| Timeout, retry, request limit, auth stop | Tối đa 3 lần thử, Retry-After cả số/date/0; SDK max_retries=0; ghi mỗi lần trước/sau request |
| GLiNER2 nhiều bản ghi, kiểm tra giới hạn | `models/gliner2_adapter.py`; pilot và integration thật trên validation, ghi số đoạn và span |
| Giữ xung đột, không ghép theo gold | `merge_chunks`; tên chuẩn hóa từ đầu ra, danh sách giá trị không bị chọn số “đúng” |
| 4 pipeline và đo thời gian | `pipelines.py`; kiểm thử tổng thời gian hybrid gồm schema API và extraction |
| Runner có protocol, Latin square, atomic checkpoint/resume | `runner.py`; kiểm thử không chạy lại kết quả đã có và không làm thời gian cache thành 0 |
| Precision/recall/micro/macro, trường/định danh/exact | `evaluation.py`; kiểm thử sai người, trường lạ, trường rỗng, null/0, made/attempted/percent |
| Khoảng tin cậy ghép cặp | Bootstrap document hoặc cụm trận khi có khóa, 2.000 lần seed 2026; kiểm thử tính lại micro |
| CSV/JSON, HTML an toàn, báo cáo/biểu đồ | `reporting.py`; kiểm thử lỗi trong mẫu số, blocked không có số đo, mock bị từ chối, HTML-escape |
| Hướng dẫn và môi trường tái lập | README.md, configs/main.yaml, requirements.lock.txt, requirements-bench.txt, notebooks/start.ipynb |

## Xác minh môi trường

Python 3.11.14, macOS ARM64, 8 CPU logic, RAM 16 GiB; CPU benchmark 4 luồng, float32. Tên thương mại CPU không truy xuất được trong sandbox; environment.json ghi kiến trúc thực thay vì đoán tên chip.

Môi trường đã ghim và kiểm tra `pip check`: gliner2 1.2.4, gliner 0.2.21, torch 2.6.0, transformers 4.51.3, openai 2.28.0. Phụ thuộc gián tiếp đều nằm trong requirements.lock.txt. Không huấn luyện lại.

Đã chạy **45 kiểm thử đạt**, gồm một kiểm thử tích hợp tải checkpoint GLiNER2 thật và trích xuất nhiều bản ghi trên validation. Các kiểm thử dùng MockClient chỉ kiểm tra hành vi phần mềm trong thư mục tạm; không ghi vào kết quả benchmark.

Pilot kỹ thuật lưu riêng ở `outputs/pilot-technical-v1` và `outputs/pilot-technical-v2`. Lần đầu phát hiện chồng lấn quá lớn khi schema chiếm gần hết 512 token. Cấu hình cuối bỏ lặp mô tả và dùng overlap không quá 64 token, đồng thời không quá một phần tư token văn bản của cửa sổ trước. Thay đổi dựa trên chiều dài/số đoạn ở validation, không tối ưu theo F1 test; không dùng kết quả pilot làm điểm test. Hai pilot được giữ để truy nguyên.

Giới hạn đã xác minh bằng thư viện và checkpoint: 512 token nội bộ gồm schema, span tối đa 8 từ của processor, count argmax từ 0 đến 19. Không có giới hạn bảng/cột độc lập trong bản mã đã kiểm tra; tổng schema phải vừa đầu vào. Không âm thầm cắt cột. Lời mô tả có token phân cách nội bộ được chuyển ký hiệu để không thay cấu trúc kỹ thuật.

CLI cố định PYTHONHASHSEED=0 vì thư viện dùng set cho thứ tự trường; torch seed 0. Phiên bản checkpoint được tải đầy đủ vào đường dẫn cục bộ trước khi gọi from_pretrained, do hàm này của thư viện không chuyển tiếp revision tới mọi tệp tải.

## Phần còn phụ thuộc môi trường/dữ liệu

- Chưa có OPENAI_API_KEY trong môi trường. `Code/.env` chỉ có cấu hình OpenRouter, không dùng thay OpenAI Responses. Snapshot được đối chiếu tài liệu chính thức nhưng quyền tài khoản chỉ có thể xác nhận bằng probe thật.
- Chưa có khóa ngày/cặp đội ghép chắc chắn với dữ liệu gốc. Chỉ loại trùng văn bản, không tuyên bố đã loại trùng trận. Validation chỉ dùng kiểm tra kỹ thuật.
- Đã đối chiếu toàn văn và gold của 20 ID chọn trước, lưu trong [LABEL_REVIEW.md](LABEL_REVIEW.md). Đây là rà soát hỗ trợ bởi Codex, chưa được con người xác nhận độc lập; giữ nhãn gốc và không tự sửa gold. Phân tích đầu ra GPT còn thiếu vì chưa chạy được API.
- Chưa có kết quả GPT thì chưa thể so sánh A_GLINER_KNOWN với A_GPT_KNOWN, hay B_HYBRID_SHORT với B_GPT_DIRECT. Các bảng so sánh giữ null đúng chỗ.

## Tiếp tục khi có khóa

Từ môi trường Python 3.11 đã cài, đặt OPENAI_API_KEY qua shell/secret manager, rồi kiểm tra preflight và pilot. Nếu cần chỉnh bất kỳ cấu hình, lời nhắc, mã hoặc từ điển nào, tạo run_id mới. Khi mọi thành phần đã giữ nguyên, có thể resume run đang thiếu GPT; các kết quả GLiNER2 đã thử không bị chạy lại hay thay thời gian. Những phiên chạy cách xa nhau phải được nêu là giới hạn xen kẽ thời gian.

```bash
source .venv/bin/activate
python -m rotowire_bench preflight --config configs/main.yaml
python -m rotowire_bench pilot --limit 3 --run-id pilot-with-gpt-001
python -m rotowire_bench run --run-id rotowire-main-v2 --resume
python -m rotowire_bench report --run-dir outputs/rotowire-main-v2
```

Nếu pilot có sửa đổi kỹ thuật, dùng run_id mới chưa tồn tại thay vì resume. Không trộn điểm các run. Lượt test đã thử, còn thiếu và nguyên nhân nằm trong campaign.json; báo cáo từ log nằm trong report.md và samples.html. Nghiệm thu hoàn tất thí nghiệm vẫn cần đủ 800 công việc **thực sự được thử**, không chỉ đủ 800 tệp trạng thái.

## Phiên bản test được chọn để bàn giao

`rotowire-main-v2` dùng bản triển khai cuối, sau kiểm thử 45 ca và pilot-final. `rotowire-main-v1` được giữ làm dấu vết kỹ thuật: lượt này được khởi chạy trước khi bổ sung resume tự chọn run_id, truyền đủ type/unit sang GLiNER2 và kiểm tra hash gold khi chấm. Việc tạo v2 dựa trên sửa giao ước phần mềm, không chọn theo điểm số. Báo cáo bàn giao dùng duy nhất v2; không trộn bài hoặc chọn kết quả tốt hơn từ v1.
