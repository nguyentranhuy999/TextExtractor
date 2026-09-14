# Khảo sát RotoWire: GLiNER2 và GPT 5.5

Chương trình Python triển khai [Docs/SPEC copy.md](<Docs/SPEC copy.md>) phiên bản 1.2: 200 bài test cố định, bốn cấu hình, chấm độ chính xác và đo độ trễ ứng dụng. Dữ liệu, prompt và đầu ra tiếng Anh; hướng dẫn và báo cáo tiếng Việt. Mã thử nghiệm cũ trong `Code/` vẫn độc lập.

Thử nghiệm hybrid mới và giới hạn còn lại: [Docs/HYBRID_IMPROVEMENT.md](Docs/HYBRID_IMPROVEMENT.md).

Chạy riêng **200 mẫu test hybrid**, giữ GPT trực tiếp ở lượt lịch sử:

```bash
python -m rotowire_bench hybrid-test --out outputs/hybrid-test-new
python -m rotowire_bench hybrid-test --out outputs/hybrid-test-new --resume
python -m rotowire_bench hybrid-test --out outputs/hybrid-test-new --report-only
```

Lệnh `hybrid-test` chỉ chạy `B_HYBRID_SHORT`, không gọi lại các nhánh GPT trực tiếp/biết trước trường hoặc GLiNER2 biết trước trường. Cấu hình và 200 ID được khóa trước chạy; mỗi phiên điều phối còn công việc có một probe riêng. `--max-tasks N` giới hạn số mẫu mới trong phiên hiện tại, vẫn giữ đủ 200 ID trong chiến dịch. Resume đã hoàn tất và `--report-only` không gọi mô hình. Báo cáo lượt mới: [Docs/HYBRID_TEST_RESULTS.md](Docs/HYBRID_TEST_RESULTS.md).

Thí nghiệm bổ sung về vị trí đoạn trích: [Docs/SNIPPET_COMPARISON.md](Docs/SNIPPET_COMPARISON.md). Lệnh dưới đây chạy **60 tác vụ theo mẫu** (30 cặp) và một probe thiết lập; mỗi nhánh dùng phiên GPT mới, cùng ngân sách `min(80,N//10)` từ. `configs/main.yaml` vẫn dùng đoạn giữa theo SPEC chính.

```bash
python -m rotowire_bench snippet-comparison --out outputs/snippet-comparison-new
python -m rotowire_bench snippet-comparison --out outputs/snippet-comparison-new --report-only
# Có thể kiểm tra ba cặp trước rồi tiếp tục bằng đúng bản mã/cấu hình đã khóa:
python -m rotowire_bench snippet-comparison --out outputs/snippet-pilot-new --max-pairs 3
python -m rotowire_bench snippet-comparison --out outputs/snippet-pilot-new --resume
```

Các cặp đã chạy được giữ nguyên khi resume; mỗi phiên thực thi mới còn thiếu công việc có probe riêng. `--report-only` và resume một chiến dịch đã hoàn tất không gọi mô hình. Mỗi mảnh đầu/giữa/cuối có biên ký tự và băm riêng; văn bản ghép bằng dòng trống không phải một chuỗi con liên tục của bài.

Chạy riêng hybrid trên validation bằng cấu hình GLiNER2 đã cải tiến:

```bash
python -m rotowire_bench hybrid-validation --out outputs/hybrid-pilot-new --limit 3
python -m rotowire_bench hybrid-validation --out outputs/hybrid-validation-new --limit 30
python -m rotowire_bench hybrid-validation --out outputs/hybrid-validation-new --report-only
```

Lệnh này chỉ chạy `B_HYBRID_SHORT`, không khởi chạy lại bốn nhánh trên 200 mẫu test. Mỗi thư mục có probe riêng, mã nguồn đóng băng, schema thô, nhật ký Codex, bảng đầu ra và độ bao phủ trường trước GLiNER2. `--resume` chỉ dùng khi cấu hình/mã không đổi; tác vụ đã bắt đầu nhưng thiếu checkpoint không được gửi lại âm thầm. `--report-only` không gọi mô hình. GPT dùng tên thuộc tính dễ đọc, tách khóa `entity_name` khỏi thuộc tính và chỉ tạo trường từ đoạn trích. Schema của nhóm A và bộ chấm giữ nguyên.

## Cài đặt

Python mục tiêu **3.11**, CPU float32, 4 luồng, batch và concurrency đều bằng 1.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-bench.txt
```

`requirements.lock.txt` ghim toàn bộ môi trường đã cài. Các phụ thuộc mô hình chính: gliner2 1.2.4, gliner 0.2.21, torch 2.6.0, transformers 4.51.3. Đây là GLiNER2 base, không phải GLiNER2.5. Không cài fairseq/BART.

Để chỉ kiểm tra dữ liệu, logic và báo cáo, không tải mô hình:

```bash
python -m pip install '.[test,report]'
```

Tệp lock được giải quyết trên macOS ARM64/Python 3.11. Máy Linux/Kaggle/Colab phải kiểm tra khả năng cài các wheel bằng `pip check`, chạy pilot và tạo run_id mới; phiên bản và phần cứng thực được ghi vào protocol. Các gói phụ thuộc CUDA trên Linux có thể do pip bổ sung theo torch, nhưng cấu hình chính vẫn chạy CPU.

## Codex CLI và đăng nhập ChatGPT

Benchmark dùng `codex exec` với **gpt-5.5**, reasoning **low**, tài khoản **ChatGPT**. Không cần khóa API. Xác thực được Codex tự quản lý; chương trình chỉ gọi `codex login status`, không mở hoặc sao chép tệp bí mật đăng nhập. Mã OpenRouter cũ trong `Code/` không tham gia.

```bash
# Nếu máy chưa có CLI: cài theo tài liệu Codex chính thức
npm install -g @openai/codex
codex --version
codex login
codex login status
codex exec --help
```

Máy đã kiểm tra dùng CLI **0.154.0-alpha.6.2** do extension Codex cung cấp. Cấu hình ghim phiên bản này; khi dùng bản khác, chạy preflight/pilot, kiểm tra giao diện thực tế và tạo giao thức mới. Không tự đổi mô hình nếu tài khoản không có GPT 5.5.

Mỗi tác vụ dùng thư mục tạm mới chỉ chứa JSON Schema kỹ thuật, dữ liệu gửi qua stdin, không resume/fork hội thoại. Adapter bỏ cấu hình tùy chỉnh, tắt các tính năng công cụ/kết nối/ký ức, đặt read-only, giữ chính sách quyền bắt buộc và quy tắc hệ thống. Cwd/read-only không tự chặn mọi phép đọc: bộ kiểm tra còn đọc **rollout của đúng phiên vừa tạo**, đối chiếu mô hình/low/ngữ cảnh và bắt mọi sự kiện công cụ. Vi phạm được chấm thất bại, không chạy lại để lấy câu trả lời khác. Chỉ dẫn nền và danh mục hệ thống còn được Codex tự nạp được giữ nguyên, lưu và băm trong `configs/codex-context.json`; không thay chỉ dẫn nền Codex thành mô hình API trần.

`gpt.context_sha256` khóa chỉ dẫn quan sát được từ preflight. Nếu ngữ cảnh thay đổi, không sửa băm để tiếp tục một run cũ: kiểm tra thay đổi, chạy pilot và tạo run mới. Phiên mới không nhận SPEC, gold, báo cáo hay cuộc trò chuyện triển khai. Tên mô hình được kiểm tra từ `turn_context`, không từ lời tự khai của GPT; phiên bản trọng số phía máy chủ và số lần gọi/retry nội bộ để chưa biết.

CLI cần quyền sử dụng trạng thái đăng nhập và ghi trạng thái Codex ở thư mục người dùng. Sandbox chỉ cho ghi trong dự án có thể chặn khởi tạo CLI; khi chạy qua coding agent, cấp quyền cho lệnh benchmark theo cơ chế phê duyệt của môi trường. Không tắt sandbox của tác vụ suy luận.

Tài liệu: [đăng nhập](https://learn.chatgpt.com/docs/auth), [mô hình](https://learn.chatgpt.com/docs/models), [chạy không tương tác](https://learn.chatgpt.com/docs/non-interactive-mode), [cấu hình](https://learn.chatgpt.com/docs/config-file/config-reference).

## Chuẩn bị và chạy

Chạy các lệnh từ thư mục gốc dự án:

```bash
python -m rotowire_bench prepare --config configs/main.yaml
python -m rotowire_bench validate --config configs/main.yaml
python -m rotowire_bench run --config configs/main.yaml --dry-run
python -m pytest -q
python -m rotowire_bench preflight --config configs/main.yaml
python -m rotowire_bench pilot --split validation --limit 3 --run-id pilot-001 --config configs/main.yaml
python -m rotowire_bench report --run-dir outputs/pilot-001
python -m rotowire_bench run --run-id main-001 --config configs/main.yaml
python -m rotowire_bench evaluate --run-dir outputs/main-001
python -m rotowire_bench report --run-dir outputs/main-001
```

Lần đầu preflight có thể tải khoảng 834 MB trọng số và tokenizer từ Hugging Face. `--local-files-only` chỉ dùng cache. Checkpoint mặc định cố định ở commit `8437ba583a733d87f56ae902f3b197934eedd58e`; mã dùng snapshot cục bộ vì hàm `from_pretrained` của gliner2 1.2.4 không truyền revision đầy đủ đến các tệp. Không tải mô hình cho dry-run.

Kiểm thử tích hợp thật trên validation, không tạo số đo benchmark mô phỏng:

```bash
RUN_GLINER_INTEGRATION=1 PYTHONHASHSEED=0 python -m pytest -q -m integration
```

Khi thiếu đăng nhập, quyền GPT 5.5 hoặc mô hình, các phần chạy được vẫn được thực hiện. Mỗi nhánh không đủ điều kiện ghi `blocked`; chiến dịch còn thiếu trong `campaign.json`. Chỉ `attempted=true` mới tính là lượt đã thử. Pilot không thuộc 200 bài test. Không đánh giá chất lượng mô hình từ đầu ra mock của kiểm thử.

## Tiếp tục, giới hạn và khóa giao thức

```bash
python -m rotowire_bench run --run-id main-001 --resume --config configs/main.yaml
python -m rotowire_bench run --run-id main-002 --max-requests 30 --config configs/main.yaml
```

`--max-requests` giới hạn số lần thử GPT, gồm retry và probe preflight trong chiến dịch; GLiNER2 không dùng ngân sách tác vụ Codex. Resume cùng run_id đọc kết quả đã thử, giữ nguyên thời gian cũ; không coi đọc cache là suy luận 0 ms. Khi không truyền run_id, `--resume` chọn chiến dịch mới nhất có cùng cấu hình và split, rồi kiểm tra đầy đủ protocol; không có chiến dịch phù hợp sẽ báo lỗi. Đăng nhập hoặc khôi phục hạn mức sau đó có thể tiếp tục các công việc `blocked`. Thứ tự lịch gốc được giữ, nhưng resume sau thời gian dài làm mất khả năng xen kẽ đầy đủ giữa Codex và CPU; báo cáo phải giữ lịch phiên chạy để người đọc thấy giới hạn này.

`--max-tasks` là tên tương đương `--max-requests`. `--max-seconds` giới hạn thời gian phiên điều phối, gồm preflight; tác vụ Codex bị kết thúc khi hết thời gian còn lại. Một công việc GLiNER2 đang chạy được hoàn tất và checkpoint trước khi dừng. Không đặt giới hạn mặc định ngoài timeout 300 giây mỗi tác vụ CLI.

`protocol.lock.json` lưu cấu hình, SHA256 toàn bộ mã, prompt, từ điển chuẩn hóa, manifest, revision GLiNER2, phiên bản CLI, ngữ cảnh Codex và các phiên bản thư viện. Đổi bất kỳ thành phần đã khóa nào phải dùng run_id mới. Không ghi đè kết quả đã thử. Thất bại hoàn toàn được chấm như dự đoán rỗng; chạy lại để đo mới cần chiến dịch mới. Không lấy kết quả tốt nhất của nhiều chiến dịch.

Ghi nguyên tử từng request, response và đoạn GLiNER2 vào `events/`, sau đó checkpoint kết quả tài liệu. Nếu tiến trình chết sau khi request được gửi nhưng trước checkpoint tài liệu, resume giữ log và ghi `incomplete`; không tự gửi lại một tác vụ đã thực sự khởi chạy. Độ trễ E2E của trường hợp không có biên kết thúc là null, có lý do. Retry tối đa 3 lần khi log Codex xác định lỗi mạng/dịch vụ tạm thời, tôn trọng retry-after quan sát được; số retry nội bộ không quan sát được để null. Timeout mặc định 300 giây, kết thúc cả nhóm tiến trình. Lỗi xác thực/quyền model/hạn mức dừng nhánh GPT, vẫn hoàn thiện phần GLiNER2. Không sửa JSON bằng LLM hay retry để tìm đáp án tốt hơn.

## Dữ liệu và cách đo

Nguồn đã kiểm tra là [xqwu/text-to-table](https://huggingface.co/datasets/xqwu/text-to-table), được [mã tác giả](https://github.com/shirley-wu/text_to_table) liên kết. Revision `58b424d1076bc8752d9857745bfd01e7c1a65c19`. Bốn tệp `rotowire/test.text`, `test.data`, `valid.text`, `valid.data` có lần lượt 728 cặp test và 727 cặp validation; bảng dùng `Team:`, `Player:`, `<NEWLINE>` và ký tự `|`. Có bảng không có cột/hàng, bộ đọc giữ đúng trường hợp này. Đầu vào là văn bản thuần trước BPE, không dịch hoặc diễn đạt lại.

Manifest chứa `random.Random(42).sample(range(728),200)`, ID theo chỉ số dòng và SHA256, cả băm văn bản và gold. Validation lấy 30 ID seed 43 sau khi loại trùng văn bản với test đã chọn. Không có khóa trận ghép chắc chắn, nên không tuyên bố đã loại sạch trùng trận; validation chỉ kiểm tra kỹ thuật, không tối ưu theo nhãn. Từ điển chấm dùng tên cột validation và cách viết tắt cố định trước test.

| Cấu hình | Đầu vào |
|---|---|
| A_GLINER_KNOWN | GLiNER2 nhận toàn bài và tên bảng/cột của từng gold |
| A_GPT_KNOWN | GPT nhận toàn bài và cùng schema như GLiNER2 |
| B_HYBRID_SHORT | GPT chỉ nhận đoạn giữa nguyên văn, tối đa min(80, N//10) từ; GLiNER2 nhận toàn bài và schema GPT |
| B_GPT_DIRECT | GPT nhận toàn bài, tự tạo bảng/trường/giá trị |

Nhóm A được cấp schema nhưng không tên hàng, số hàng, số liệu hay mẫu ô rỗng. Nhóm B không nhận schema A, danh mục trường hoặc gold. `InferenceInput` không có thuộc tính gold. Chỉ hàm dựng schema A và bộ chấm có quyền đọc gold. Lời nhắc B không có ví dụ bóng rổ với danh mục cột.

GLiNER2 trích xuất bản ghi nhiều trường bằng tên schema có nghĩa (`player`, `Points`…), mô tả ngắn và tách bảng theo cấu hình đã chọn trên validation. Khóa được làm sạch ký hiệu điều khiển, xử lý trùng và ánh xạ ngược về tên trường gốc. Chế độ `opaque` với `t0/f0` chỉ giữ để tái tạo baseline cũ. Mô tả được truyền thành dữ liệu, vô hiệu hóa ký hiệu phân cách nội bộ. Giới hạn checkpoint đã kiểm tra: tổng 512 token nội bộ gồm schema; span tối đa 8 từ theo bộ xử lý; dự đoán 0–19 bản ghi mỗi loại. Kiểm tra chiều dài bằng chính bộ xử lý, không âm thầm cắt văn bản hoặc cột. Ưu tiên toàn bài, rồi biên câu; câu quá dài tách tại từ. Chồng lấn tối đa 64 token và tối đa một phần tư token văn bản của cửa sổ trước để bảo đảm tiến triển. Nếu schema không chừa chỗ, ghi `input_limit`. Mọi biên ký tự và lượt mạng được lưu. Ghép theo tên chuẩn hóa, giữ xung đột và cờ nghi ngờ bão hòa. CLI tự cố định `PYTHONHASHSEED=0` vì thư viện sử dụng set cho thứ tự trường; torch seed 0, eval/inference_mode.

Đơn vị chấm là dữ kiện `(sample, loại bảng, đối tượng, trường, giá trị)`; sai người/sai thuộc tính tạo FP và FN dù số đúng. Chuẩn hóa NFC, khoảng trắng, casefold, Decimal và số viết bằng chữ; không suy diễn số liệu hay đổi 0.5 thành 50%. Null khác 0; made khác attempted; phần trăm khác số lần. Tên rút gọn chỉ khớp khi duy nhất trong loại bảng của tài liệu. Trường lạ, trường rỗng và ô dùng trường chưa khai báo vẫn được tính. Giá trị xung đột giữ đủ để tính FP, dữ kiện trùng không tăng TP.

Micro precision/recall/F1 tính từ tổng TP/FP/FN; macro F1 trung bình tài liệu. Cả hai tập rỗng: F1=1, một tập rỗng: F1=0. Đầu ra hỏng cả tài liệu là dự đoán rỗng; ô hỏng trong JSON đọc được được bỏ riêng, ghi lỗi. Điểm chính chỉ có khi một nhánh đã thử đủ 200 bài, kể cả thất bại; chiến dịch chưa đủ không được công bố hoàn tất. Báo thêm điểm chỉ trên thành công, số mẫu gold, trường, định danh, exact-document, lỗi và tách players/teams.

Đo `perf_counter_ns`, lưu ms: prepare, schema Codex, extract, postprocess, retry wait và E2E. Codex/extract không cộng trùng retry wait; E2E bao gồm mọi bước. Tải dữ liệu/mô hình, warmup và phân tích ở ngoài độ trễ tài liệu. Thứ tự tài liệu seed 44, bốn cấu hình luân phiên Latin. Đây là độ trễ ứng dụng CPU so với GPT chạy trong Codex từ xa, không phải cùng phần cứng. Tỷ lệ thời gian dùng tổng trên cùng các ID thành công. CI95% bootstrap ghép cặp 2.000 lần seed 2026; có khóa trận tin cậy thì lấy cụm trận. Không đo/so sánh token hay chi phí tiền.

## Tệp đầu ra

Trong `data/prepared/`: manifest test/validation, văn bản inference, gold riêng, snippets, dry-run/preflight. Trong mỗi `outputs/RUN_ID/`:

- `protocol.lock.json`, `environment.json`, `sample_manifest.json`, `schedule.json`, `campaign.json`, `preflight.json`.
- `results/`: trạng thái, raw references, bảng, dữ kiện chuẩn hóa, thời gian, hash và lỗi mỗi công việc.
- `events/`: stdin, JSON Schema, câu trả lời nguyên bản, sự kiện CLI, exit code, session ID, mô hình quan sát và audit ngữ cảnh, mọi retry, schema GLiNER2, từng đoạn và bằng chứng span cục bộ. Span có biên tương đối với đoạn; cộng `start_char` của đoạn để về toàn bài.
- `predicted_schemas/`: schema GPT tách riêng khỏi bảng cuối; `codex_attempts.jsonl`, `snippets.jsonl`.
- `metrics_per_sample.csv`, `summary.csv`, `table_breakdown.csv`, `schema_errors.csv`, `metrics.json`.
- `report.md`, `samples.html`, CSV bảng rộng trong `tables/`, biểu đồ `quality_latency.png` và `error_types.png` khi có số đo đủ điều kiện.
- `manual_review.json`: 20 ID được chọn trước và trạng thái rà soát. Chỉ trang phân tích và bộ chấm hiển thị/đọc gold.

`samples.html` là tệp tĩnh, mở trực tiếp bằng trình duyệt; văn bản nguồn, schema và kết quả được HTML-escape. Gold và bốn nhánh cùng các FP/FN có thể xem theo mẫu. `evaluate` và `report` chỉ đọc log, không khởi chạy Codex.

Điểm theo nhãn gốc luôn là chính. Nếu rà soát phát hiện lỗi nhãn, lưu changelog gồm sample_id, ô cũ/mới, lý do và người rà soát; không sửa gold trong chiến dịch chính. Phân tích nhãn sửa phải thực hiện trong bản sao riêng, áp dụng cho cả bốn nhánh và ghi rõ là điểm phụ.

## Giới hạn

Chỉ 200 bài bóng rổ, một checkpoint và một mức suy luận GPT. Không kiểm chứng được nhiễm dữ liệu tiền huấn luyện; gold chuyển thể có thể sai; đoạn 10% có thể thiếu phần lớn trường; API gồm mạng và máy chủ từ xa. Bootstrap của một lần chạy không bao quát toàn bộ tính ngẫu nhiên mô hình. Không đặt F1 tối thiểu để nghiệm thu và không tự kết luận GLiNER2 nhanh/chính xác hơn.

Thông tin API được đối chiếu với [GPT 5.5](https://developers.openai.com/api/docs/models/gpt-5.5) và [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). Giao diện GLiNER2 được kiểm tra trên [mã nguồn chính thức](https://github.com/fastino-ai/GLiNER2) và bản thư viện đã ghim. Quyền truy cập snapshot chỉ được xác nhận khi probe thành công.

## Xuất/nhập khi dùng giao diện

```bash
python -m rotowire_bench export-tasks --config configs/main.yaml --out outputs/ui-tasks-001
python -m rotowire_bench import-results --run-dir outputs/ui-tasks-001 --from-dir outputs/codex_answers --local-files-only
python -m rotowire_bench report --run-dir outputs/ui-tasks-001
```

Xuất tác vụ không gọi mô hình và không cần đăng nhập. Đọc `UI_INSTRUCTIONS.md` trong thư mục xuất, gửi **chỉ một prompt** vào phiên mới mỗi lần; tuyệt đối không gắn toàn thư mục vì có dữ liệu của các tác vụ khác và gold phục vụ chấm. Envelope nhập chứa ID/băm, chuỗi `raw_final` nguyên bản và bằng chứng model/low/auth/phiên riêng/ngữ cảnh/công cụ. ID hoặc băm sai, phiên dùng lại hay tác vụ trùng bị từ chối; JSON mô hình hỏng vẫn được giữ và chấm lỗi. Tác vụ thiếu trả `pending_external`.

Chế độ `codex_ui_import` có chiến dịch riêng. Không thể nhập vào chiến dịch CLI. Thời gian GPT/hybrid luôn null với lý do; thời gian thao tác giao diện không phải độ trễ mô hình. Độ chính xác có thể chấm, nhưng phần so sánh thời gian chưa hoàn tất. `gpt55_adapter.py` là mã API cũ giữ để đối chiếu lịch sử; CLI/spec 1.2 không gọi adapter đó.

## Kết quả

Các lượt spec 1.1 trước đây được giữ nguyên trong `outputs/rotowire-main-v2` và ghi nhận tại `Docs/RESULTS.md`; không ghép số đo cũ vào lượt Codex mới. Xem `Docs/IMPLEMENTATION.md` và báo cáo của run mới để biết tiến độ thực tế. Nội dung nguồn/cấu hình/outputs đang nằm trong các mục được `.gitignore` của workspace loại trừ; bàn giao cục bộ có đủ tệp, nhưng cần chủ động chọn tệp trước khi đưa lên Git.

## Cải thiện GLiNER2 bằng validation, không gọi GPT

Đã chạy bốn cấu hình trên cùng 30 mẫu validation; fact F1 tăng từ 0,003937
(adapter cũ) lên 0,488889 (`separate`). Xem [báo cáo](Docs/GLINER_IMPROVEMENT.md).
Đây là kết quả chọn cấu hình trên validation, chưa phải benchmark test mới.

`configs/main.yaml` hiện chọn `schema_labels: semantic`,
`schema_descriptions: compact`, `table_execution: separate`; checkpoint và
ngưỡng 0.5 giữ nguyên. Bảng cầu thủ và đội đọc toàn bài riêng, không dùng gold
để ghép bản ghi. Bộ chuẩn hóa/chấm điểm chưa thay đổi.

```bash
# Lặp lại đối chiếu vào thư mục mới; dùng đủ 30 validation, không gọi Codex.
.venv/bin/python -m rotowire_bench gliner-validation --config configs/gliner-validation.yaml --out outputs/gliner-validation-v2
# Tổng hợp lại log, không tải hay gọi mô hình.
.venv/bin/python -m rotowire_bench gliner-validation --out outputs/gliner-validation-v1 --report-only
```

Dùng `--resume` cùng config/mã nếu bị gián đoạn giữa các công việc. Một công việc
đã bắt đầu nhưng chưa có checkpoint sẽ được báo lỗi, không âm thầm chạy lại.
Bản nguồn/config mới không resume được chiến dịch benchmark cũ đã khóa;
`source_snapshot.zip` trong từng run giữ phiên bản tương ứng. Muốn đo lại test
phải dùng run_id mới. Lượt cải thiện này không khởi chạy thêm 600 tác vụ GPT.
