# Thử nghiệm vị trí đoạn trích cho hybrid

Ngày 14/09/2026. Đây là bước thử cách lấy đoạn đầu–giữa–cuối mà người dùng yêu cầu, trên 30 mẫu validation seed 43. Thí nghiệm chính trong SPEC và cấu hình mặc định vẫn lấy một đoạn giữa liên tục.

**Kết quả không ủng hộ thay đoạn giữa bằng ba mảnh trong ngân sách này.** Fact F1 giảm từ **27,96% xuống 12,18%**. Độ bao phủ dữ kiện bằng schema giảm, và không có bằng chứng tiết kiệm thời gian. Giữ nguyên đoạn giữa làm mặc định.

## Kết quả ghép cặp, 30 mẫu mỗi nhánh

| Chỉ số | Đoạn giữa | Đầu–giữa–cuối |
|---|---:|---:|
| Schema hợp lệ | 30/30 | 30/30 |
| Schema có thuộc tính | 29/30 | 27/30 |
| Trạng thái success / bảng rỗng | 30 / 0 | 29 / 1 |
| Fact TP / FP / FN | 164 / 156 / 689 | 65 / 149 / 788 |
| Fact precision | 51,25% | 30,37% |
| Fact recall | 19,23% | 7,62% |
| Fact F1 | **27,96%** | **12,18%** |
| Recall cặp bảng–trường | 20,06% (67/334) | 5,69% (19/334) |
| Dữ kiện gold thuộc trường đã đề xuất | **356/853 (41,74%)** | **101/853 (11,84%)** |
| Mean e2e, giây/bài | 11,457 | 11,907 |
| Median e2e, giây/bài | 11,136 | 11,189 |
| P95 e2e, giây/bài | 16,470 | 18,319 |
| GLiNER2 forward passes | 50 | 48 |

Chênh F1 là **−15,78 điểm phần trăm**, CI95 **[−23,06; −8,43]**. Chênh độ bao phủ dữ kiện bằng schema là **−29,89 điểm phần trăm**, CI95 **[−41,84; −16,67]**. Hai khoảng đều nằm dưới 0 trong phép bootstrap theo tài liệu này.

Tỷ số thời gian đầu–giữa–cuối/giữa trên 30 cặp hợp lệ là **1,039**, CI95 **[0,921; 1,179]**; chưa có bằng chứng chênh lệch thời gian rõ ràng. Bảng rỗng là đầu ra hợp lệ và vẫn được tính vào cặp thời gian, đồng thời nhận điểm dữ kiện bằng 0 khi gold không rỗng. Mean bước GPT tạo schema lần lượt 10,342 và 10,727 giây; GLiNER2 1,101 và 1,166 giây. Không có retry bên ngoài.

![So sánh vị trí đoạn trích](../outputs/snippet-comparison-v1/comparison.png)

Điểm đoạn giữa ở đây là lần chạy mới **27,96%**, khác **27,07%** của hybrid v3 trước đó. Hai lượt nhận cùng yêu cầu nhưng dùng phiên GPT mới; schema/đầu ra có thể khác. Baseline mới được chọn trước khi chạy để so sánh xen kẽ, không chọn lượt nào có điểm tốt hơn.

## Vì sao cách chia ba mảnh chưa hiệu quả

Ở cấp dữ kiện gold thuộc trường được schema đề xuất, cách trải đoạn **thêm được 26 nhưng mất 281 dữ kiện** so với đoạn giữa. Ở đầu ra cuối, nó lấy đúng thêm 19 dữ kiện nhưng mất 118 dữ kiện vốn được nhánh giữa lấy đúng. Các con số này là phép đối chiếu theo từng mẫu, không phải chỉ so hai tổng độc lập.

Quan sát định tính ba mẫu sau giúp giải thích kết quả. Hai mẫu đầu có mức giảm bao phủ lớn nhất; mẫu cuối có mức tăng lớn nhất. Đây là phân tích sau chạy bởi Codex, không phải đánh giá mù độc lập và không được dùng để sửa kết quả:

| Mẫu | Quan sát |
|---|---|
| `0019-16d9c103e326` | Đoạn giữa có tên Carlos Boozer gắn với points/FG/FT/rebounds. Mảnh giữa rút ngắn bắt đầu bằng `12 points`, mất chủ ngữ; mảnh cuối là lịch trận sau. GPT chỉ tạo bảng team với `Game points`/`Game result`; bao phủ theo bộ chấm giảm 44 → 0. |
| `0473-b1f278ff9d83` | Đoạn giữa chứa nhiều thống kê cầu thủ. Mảnh giữa mới bắt đầu bằng `bench, and added ...`, mất liên kết tên người; phần cuối là lịch thi đấu. GPT chỉ tạo schema đội; bao phủ giảm 40 → 0. |
| `0109-aa5bc978381b` | Đoạn giữa chủ yếu là nhận xét và thành tích đội. Mảnh cuối có points/rebounds; cách trải đoạn tìm được thêm trường hữu ích, bao phủ tăng 0 → 13 và TP tăng 0 → 10. |

Không phải mọi mất điểm đều do thiếu nội dung. Ví dụ `Game points` và `Full game points` có thể gần nghĩa với điểm đội, nhưng không thuộc alias đã khóa. Vì vậy một phần giảm bao phủ là do cách đặt tên trường của GPT thay đổi khi đổi đoạn. Không mở rộng alias hoặc sửa tên dự đoán sau chạy để tăng điểm. Kết luận ở đây áp dụng cho pipeline và bộ chấm đã khóa, không chứng minh rằng mọi cách chọn nhiều đoạn đều kém hơn.

Với tổng 14–59 từ, chia ba khiến từng mảnh chỉ khoảng 4–20 từ. Những ví dụ trên cho thấy lợi ích phân bố vị trí có thể bị mất bởi câu bị cắt, thiếu chủ ngữ và phần cuối nói về trận tương lai. **Không đưa biến thể này vào cấu hình chính.** Nếu nghiên cứu tiếp cách chọn đoạn trọn câu hoặc tăng ngân sách, cần một thí nghiệm mới; chưa chạy các phương án đó trong lần bàn giao này.

## Thiết kế khóa trước chạy

Hai nhánh dùng cùng GPT 5.5 low qua Codex/ChatGPT, cùng prompt và JSON Schema của hybrid v3, cùng GLiNER2 base-v1 đã ghim, cùng bộ chấm/alias/gold. GLiNER2 dùng CPU float32, 4 luồng, ngưỡng 0.5, nhãn có nghĩa, mô tả gọn và tách bảng. Mỗi bảng đọc đủ toàn bài. Không fine-tune, không sửa schema bằng GPT, không bổ sung trường từ gold.

| Nhánh | Văn bản gửi GPT |
|---|---|
| `center_contiguous` | Đoạn giữa đúng quy tắc cũ: B từ bắt đầu tại `(N-B)//2`. |
| `head_middle_tail` | Ba mảnh nguyên văn ở đầu, giữa và cuối; tổng vẫn đúng B từ. |

Đếm từ bằng `re.finditer(r"\S+", text)`, ngân sách `B=min(80,N//10)`. Chia `q,r=divmod(B,3)`, độ dài lần lượt là `[q+(r==2), q+(r>=1), q]`: phần dư ưu tiên giữa rồi đầu. Mảnh đầu bắt đầu ở từ 0, mảnh giữa ở `(N-middle_length)//2`, mảnh cuối kết thúc ở từ N. Ghép bằng `\n\n`, không thêm từ, dấu ba chấm, tóm tắt hoặc tên đối tượng. Giữ nguyên dấu câu/khoảng trắng trong từng mảnh.

Nếu B nhỏ hơn 3, bộ chọn quay về một đoạn giữa để không tạo mảnh rỗng; B bằng 0 trả `insufficient_fragment`. Cả 30 mẫu thực đều có đủ ba mảnh; B nằm trong khoảng **14–59 từ**, mỗi mảnh khoảng 4–20 từ. Không nới biên đến cuối câu vì sẽ đổi ngân sách. Mảnh ngắn có thể thiếu chủ ngữ hoặc cắt một cụm thống kê; dòng trống không bảo đảm GPT hiểu đúng tính gián đoạn. Đây là giới hạn của cách biểu diễn đang kiểm tra.

Mỗi mẫu có hai phiên GPT mới. Thứ tự tài liệu xáo bằng seed 44; thứ tự hai nhánh luân phiên, mỗi nhánh đứng trước 15 lần. Tổng dự kiến 60 tác vụ theo mẫu, thêm probe ngoài dữ liệu đánh giá. Lượt giữa cũ không được tái sử dụng làm baseline đo thời gian: baseline được chạy mới trong cùng chiến dịch.

Kiểm tra trước chạy đã xác nhận đầu vào của 30 yêu cầu đoạn giữa giống từng byte của hybrid v3, cấu hình không đổi, và prompt/JSON Schema/adapter GLiNER2/adapter Codex/scorer/alias không đổi. Độ khác biệt nằm ở lựa chọn các từ đưa vào phần dữ liệu của GPT.

## Cách chấm

Chấm precision/recall/F1 của dữ kiện cuối, tỷ lệ schema hợp lệ, recall cặp bảng–trường, phần dữ kiện gold thuộc trường được schema đề xuất, số GLiNER2 forward và toàn bộ thời gian e2e. Các lỗi vẫn tính như dự đoán rỗng trong điểm dữ kiện; chỉ số bao phủ schema được chấm riêng trước GLiNER2.

Chênh lệch tính theo đầu–giữa–cuối trừ giữa. Bootstrap ghép cặp theo tài liệu, 2000 lần, seed 2026, cho chênh lệch micro F1 và độ bao phủ dữ kiện; tỷ số thời gian dùng những ID thành công ở cả hai nhánh. CI không đo đầy đủ tính ngẫu nhiên của GPT qua các lần gọi. Tập validation chưa loại sạch trùng trận; đây không phải kết quả test độc lập.

## Chạy lại

```bash
.venv/bin/python -m rotowire_bench snippet-comparison --out outputs/snippet-comparison-new
.venv/bin/python -m rotowire_bench snippet-comparison --out outputs/snippet-comparison-v1 --report-only
```

`--max-pairs 3` chạy sáu công việc đầu theo lịch cố định; `--resume` tiếp tục các cặp còn lại với cùng mã/cấu hình, không lấy dự đoán tốt nhất hay đo lại mẫu đã xong. Mỗi lần resume còn việc sẽ có probe riêng. Tác vụ có dấu vết đã khởi chạy nhưng thiếu checkpoint không được tự gửi lại. Một lượt đã hoàn tất hoặc `--report-only` không gọi mô hình.

Kiểm thử trước khi khóa: `RUN_GLINER_INTEGRATION=1 PYTHONHASHSEED=0 .venv/bin/python -m pytest -q` — **80 passed, 23.25 giây**, gồm GLiNER2 thật. Các kiểm thử mới kiểm tra biên từ/ký tự, nguyên văn, tổng ngân sách, không chồng mảnh, bài rất ngắn, đầu vào không nhận từ ngoài đoạn, prompt chung, thứ tự ghép cặp, tính CI, checkpoint/resume và tính toàn vẹn giao thức.

Kết quả và nhật ký được lưu ở [outputs/snippet-comparison-v1](../outputs/snippet-comparison-v1/). `source_snapshot.zip` của thư mục cha lưu bản nguồn chung; mỗi thư mục nhánh lưu schema, bảng, đoạn trích và chỉ số riêng.

Đã xác minh **61 phiên mới**: 60 tác vụ đo và một probe, tất cả đúng GPT 5.5/low, ngữ cảnh đã khóa, không công cụ. Kiểm tra từng đoạn, ngân sách, schema gửi GLiNER2, các chunk phủ toàn bài và thứ tự chạy xen kẽ đều qua. Giữ nguyên băm 21 artifact benchmark test cũ, 11 artifact GLiNER2 validation và 306 artifact hybrid v3.

Thư mục con của hai nhánh dùng để đọc kết quả. Khi cần resume chiến dịch ghép cặp, dùng `snippet-comparison` với **thư mục cha**, theo các lệnh ở trên.

Artifact chính: [metrics.json](../outputs/snippet-comparison-v1/metrics.json), [báo cáo tự sinh](../outputs/snippet-comparison-v1/report.md), [inference_audit.json](../outputs/snippet-comparison-v1/inference_audit.json), [diagnostics.json](../outputs/snippet-comparison-v1/diagnostics.json), [gói mã và kết quả](../outputs/snippet-comparison-v1/delivery_package.zip).

Script kiểm tra sau chạy: `PYTHONPATH=. .venv/bin/python outputs/snippet-comparison-analysis/audit.py`. Script vẽ: `MPLCONFIGDIR=/private/tmp/rotowire-mpl .venv/bin/python outputs/snippet-comparison-analysis/plot.py`. Hai script chỉ xử lý log, không gọi mô hình; dùng cùng phiên bản nguồn đã khóa để kiểm tra băm.
