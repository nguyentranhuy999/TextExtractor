# Đặc tả khảo sát GLiNER2 và GPT 5.5 trên RotoWire

Phiên bản 1.2 · Ngày 13 tháng 9 năm 2026 · Người thực hiện: Codex

## 1 Mục tiêu và phạm vi

Xây dựng chương trình thí nghiệm có thể chạy lại để khảo sát khả năng chuyển văn bản thành bảng của GLiNER2 trên đúng 200 mẫu kiểm tra RotoWire. So sánh với GPT 5.5 về **độ chính xác và thời gian xử lý**. Theo yêu cầu cập nhật, bỏ phần đo và so sánh token để giảm độ phức tạp triển khai.

Thực hiện hai nhóm thí nghiệm:

1. Khi biết trước các trường cần lấy: so sánh GLiNER2 và GPT 5.5 trên cùng văn bản đầy đủ và cùng bộ trường.
2. Khi không được cung cấp trường: GPT 5.5 chỉ đọc một đoạn rất ngắn để đề xuất cấu trúc; GLiNER2 sử dụng cấu trúc đó để trích xuất toàn bài. So sánh hệ thống kết hợp với GPT 5.5 đọc toàn bài và tự tạo bảng trực tiếp.

Tên bộ dữ liệu trong mã và báo cáo là **RotoWire**; “Rotowise” trong yêu cầu ban đầu chỉ cùng bộ dữ liệu này. Dùng tiếng Anh nguyên bản cho dữ liệu và lời nhắc mô hình; viết hướng dẫn và báo cáo phân tích bằng tiếng Việt. Không dịch hoặc diễn đạt lại các bài kiểm tra. Không huấn luyện bổ sung GLiNER2 trong khảo sát chính. Không thay GPT 5.5 bằng mô hình khác, không thay GLiNER2 bằng GLiNER2.5.

GPT 5.5 được sử dụng qua Codex đăng nhập bằng tài khoản ChatGPT của người dùng. Không yêu cầu khóa OpenAI API hoặc tích hợp Responses API. Trong báo cáo, ghi rõ đối tượng so sánh là **GLiNER2 cục bộ và GPT 5.5 chạy trong Codex**; môi trường chỉ dẫn và cách thực thi của Codex là một phần điều kiện thí nghiệm.

Đây là đặc tả triển khai, chưa phải kết quả thí nghiệm. Mọi số liệu hiệu năng phải được tính từ các lần chạy thực tế; không điền số minh hoạ vào bảng kết quả chính.

## 2 Cấu hình thí nghiệm bắt buộc

| Mã | Phương pháp | Thông tin cung cấp khi chạy | Đầu ra | Số mẫu |
|---|---|---|---|---:|
| A_GLINER_KNOWN | GLiNER2 với trường biết trước | Toàn bài và bộ trường của mẫu | Các bảng và giá trị | 200 |
| A_GPT_KNOWN | GPT 5.5 với trường biết trước | Toàn bài và cùng bộ trường như A_GLINER_KNOWN | Các bảng và giá trị | 200 |
| B_HYBRID_SHORT | GPT 5.5 tạo trường rồi GLiNER2 trích xuất | GPT chỉ thấy đoạn trích; GLiNER2 thấy toàn bài và cấu trúc GPT vừa tạo | Cấu trúc dự đoán và các bảng | 200 |
| B_GPT_DIRECT | GPT 5.5 tự tạo bảng | Toàn bài; không có danh sách trường | Cấu trúc dự đoán và các bảng | 200 |

Hai so sánh chính là A_GLINER_KNOWN với A_GPT_KNOWN, và B_HYBRID_SHORT với B_GPT_DIRECT. Không gộp A và B vào một bảng xếp hạng mà bỏ qua sự khác nhau về thông tin được cung cấp.

Mặc định chạy mỗi cấu hình một lần trên mỗi mẫu. Có 800 kết quả cấp tài liệu, trong đó dự kiến 600 tác vụ GPT qua Codex thành công: 200 lần A_GPT_KNOWN, 200 lần tạo trường của B_HYBRID_SHORT, 200 lần B_GPT_DIRECT. GLiNER2 có 400 công việc cấp tài liệu; số lượt chạy mạng có thể lớn hơn nếu phải chia văn bản. Các lượt kiểm tra môi trường, thử trên tập phát triển và chạy lại do lỗi được đếm riêng. Một tác vụ Codex không đồng nghĩa một lượt gọi mô hình nội bộ; không khẳng định biết số lượt nội bộ khi công cụ không cung cấp.

Không tự mở rộng thành nhiều mô hình hoặc nhiều mức đoạn trích trong lần chạy chính. Có thể chuẩn bị cờ cấu hình cho nghiên cứu bổ sung, nhưng không chạy mặc định.

## 3 Dữ liệu và cách chọn 200 mẫu

### 3.1 Nguồn dữ liệu

Dùng **bản RotoWire đã được xử lý cho nghiên cứu Text-to-Table**, lấy từ [kho dữ liệu của tác giả](https://huggingface.co/datasets/xqwu/text-to-table), được liên kết từ [kho mã Text-to-Table](https://github.com/shirley-wu/text_to_table). Theo [mô tả xử lý dữ liệu trong bài báo](https://arxiv.org/html/2109.02707v2#S5.SS1), các nội dung trong bảng không xuất hiện trong văn bản đã được lọc khi tạo bản chuyển thể.

Codex phải kiểm tra cấu trúc tệp thực tế trước khi viết bộ đọc. Ưu tiên văn bản và bảng dạng văn bản thuần trước bước mã hoá BPE, tức bước chia văn bản thành các mảnh nhỏ phục vụ mô hình. Không đưa mã token hoặc các mảnh BPE chưa giải mã vào GPT hoặc GLiNER2. Không cần cài toàn bộ môi trường huấn luyện BART/fairseq cũ chỉ để đọc dữ liệu.

Không âm thầm dùng nguyên bảng RotoWire gốc làm đáp án thay thế. Nếu chỉ tải được bản gốc, hoàn thiện bộ đọc và hạ tầng, ghi rõ dữ liệu đáp án chuyển thể còn thiếu; chỉ tái tạo khi xác minh được quy trình chuyển đổi và gắn một phiên bản dữ liệu riêng. [RotoWire gốc](https://github.com/harvardnlp/boxscore-data) chỉ dùng bổ trợ nguồn gốc và thông tin trận đấu khi ghép tương ứng được một cách xác định.

Ghi nguồn tải, mã phiên bản hoặc mã commit nếu có, tên tệp, thời điểm tải và SHA256 của tệp. Không giả định tên cấu hình Hugging Face hay tên cột nếu chưa kiểm tra.

### 3.2 Tập kiểm tra

- Kiểm tra số mẫu test; bản được bài báo mô tả có 728 mẫu. Nếu khác, ghi rõ và xác minh nguồn trước khi gắn nhãn kết quả là thí nghiệm này.
- Gán `sample_id` ổn định theo chỉ số dòng gốc và mã băm văn bản.
- Dùng `random.Random(42).sample(range(n_test), 200)` trên thứ tự tệp đã đóng băng; lưu cả thứ tự lấy mẫu và danh sách ID.
- Không lựa chọn theo độ dễ, số trường, độ dài, kết quả mô hình hoặc độ bao phủ của đoạn trích.
- Không thay mẫu lỗi hoặc bài ngắn bằng mẫu khác sau khi đã tạo danh sách. Mọi cấu hình phải có một trạng thái kết quả cho mỗi ID.
- Bảng cầu thủ và bảng đội bóng của cùng bài thuộc một mẫu. Không tính chúng là hai bài kiểm tra.
- Lưu `sample_manifest.json` với seed, 200 ID, chỉ số gốc, băm văn bản và băm đáp án. Lần chạy lại đọc danh sách này, không lấy mẫu lại.

### 3.3 Tập phát triển và đóng băng cấu hình

Chọn 30 mẫu từ tập validation bằng seed 43 để kiểm tra bộ đọc, lời nhắc, định dạng và khả năng chạy mô hình. Không dùng 200 mẫu test để chỉnh ngưỡng, chọn đoạn hoặc chọn câu lệnh tốt nhất.

RotoWire gốc có cảnh báo trùng trận giữa các tập. Khi ghép được thông tin trận, loại khỏi validation các trận trùng tập test đã chọn theo ngày và cặp đội; đồng thời kiểm tra văn bản trùng. Không ghép theo suy đoán chỉ vì hai tệp có cùng độ dài. Nếu thiếu khóa trận đáng tin cậy, ghi giới hạn kiểm tra trùng lặp và chỉ dùng validation để kiểm tra kỹ thuật, không tối ưu theo nhãn. Không tuyên bố đã loại sạch trùng trận khi chỉ so sánh chuỗi văn bản.

Trước lần chạy test đầu tiên, lưu `protocol.lock.json`: phiên bản mã, dữ liệu, mô hình, phiên bản và chế độ chạy Codex, các chỉ dẫn bổ sung quan sát được, lời nhắc, bộ ánh xạ tên, quy tắc chuẩn hoá, ngưỡng, cách lấy đoạn và cấu hình đo. Mọi thay đổi sau đó tạo `run_id` mới; không ghi đè kết quả cũ hoặc lấy kết quả tốt nhất của nhiều lần chạy để báo cáo.

## 4 Quyền truy cập đáp án và bộ trường

“Bộ trường”, hay schema, gồm loại bản ghi, trường định danh đối tượng, tên thuộc tính và mô tả ngắn. “Đáp án”, hay gold, gồm cả đối tượng cụ thể và các giá trị đúng.

### 4.1 Nhóm A biết trước trường

Tạo `known_schema` từ tên bảng và các tiêu đề thuộc tính của **từng mẫu đáp án**. Cho cả hai phương pháp A cùng nội dung này. Đây là thông tin được cho trước theo thiết kế thí nghiệm, phải công khai trong báo cáo.

- Chỉ lấy tên nhóm bảng và tên thuộc tính; không lấy tiêu đề hàng chứa tên cầu thủ/đội.
- Không cung cấp số hàng, tên các đối tượng, giá trị, ô trống hoặc dấu hiệu một đối tượng có những trường nào.
- Thêm khóa kỹ thuật `entity_name` để lưu định danh đối tượng; khóa này không chứa tên thật từ đáp án.
- Nếu bổ sung mô tả trường, lấy từ một từ điển cố định xây dựng trước test bằng tài liệu dữ liệu hoặc tập phát triển. Không dùng LLM để đọc giá trị gold rồi viết mô tả.
- Giữ cùng nội dung ngữ nghĩa của schema cho GPT và GLiNER2; chỉ khác cú pháp mà thư viện yêu cầu. Bộ thích ứng cú pháp phải có kiểm thử.

### 4.2 Nhóm B tự tìm trường

GPT tạo schema của B_HYBRID_SHORT chỉ nhận đoạn trích cùng chỉ dẫn chung. GPT của B_GPT_DIRECT chỉ nhận toàn bài cùng chỉ dẫn chung. Không cung cấp danh mục các cột RotoWire, enum các trường lấy từ gold, schema nhóm A, đầu ra cấu hình khác hoặc danh sách đối tượng đúng.

Cho phép cả hai biết nhiệm vụ là trích xuất dữ liệu từ bài tường thuật bóng rổ. Khung JSON kỹ thuật là giống nhau và không chứa sẵn danh mục thuộc tính. Không tự bổ sung các trường GPT bỏ sót bằng từ điển RotoWire trước khi đưa sang GLiNER2.

Tách kiểu dữ liệu và hàm xử lý `InferenceInput` khỏi `EvaluationGold`. Chỉ hàm tạo schema nhóm A và bộ chấm được đọc đáp án. Bộ chọn đoạn, GPT nhóm B và GLiNER2 không nhận đối tượng dữ liệu có thuộc tính gold.

Codex đang viết chương trình có thể kiểm tra cấu trúc dữ liệu để xây bộ đọc, nhưng các phiên GPT dùng để lấy kết quả thí nghiệm phải mới hoàn toàn và không kế thừa hội thoại triển khai. Đặc biệt, phiên tạo trường của B_HYBRID_SHORT chỉ nhận đoạn ngắn; không nhận tệp toàn bài, đường dẫn có thể đọc toàn bài, bản spec chứa ví dụ trường, đầu ra nhóm A hoặc báo cáo đáp án.

## 5 Đoạn văn ngắn cho GPT tạo trường

### 5.1 Quy tắc chính

Mặc định dùng **một đoạn liên tục ở giữa văn bản**, dài không quá **10% số từ của toàn bài và tối đa 80 từ**. Đây là lựa chọn thiết kế của khảo sát, không phải đặc tính của dữ liệu hoặc bảo đảm đoạn đó chứa đủ trường.

Để cách đếm đơn giản và tái lập được, định nghĩa một “từ” là một chuỗi ký tự không chứa khoảng trắng: `words = list(re.finditer(r"\S+", full_text))`. Dùng trực tiếp biên ký tự của các kết quả này; không cần thêm thư viện đếm token để chọn đoạn.

Gọi `N = len(words)` và `B = min(80, N // 10)`. Nếu `B < 1`, ghi `insufficient_fragment`; không tăng ngân sách và không thay mẫu. Ngược lại, lấy `i = (N - B) // 2`, `start_char = words[i].start()` và `end_char = words[i + B - 1].end()`. Đoạn trích là `full_text[start_char:end_char]`, với biên cuối không bao gồm ký tự tại `end_char`. Không thêm câu, tóm tắt hoặc viết lại nội dung.

Đoạn gửi GPT phải là một chuỗi con nguyên văn của `full_text`, giữ nguyên dấu câu và khoảng trắng bên trong. Lưu `start_char`, `end_char`, nội dung, băm đoạn, `full_word_count`, `snippet_word_count` và `word_ratio = B / N`. Tỷ lệ 10% tính riêng phần văn bản dữ liệu, không gồm chỉ dẫn và khung JSON.

### 5.2 Những hành vi không được dùng ở cấu hình chính

Không đọc bảng gold để tìm đoạn giàu trường. Không dùng LLM đọc toàn bài trước để chọn/tóm tắt đoạn rồi gọi đó là “LLM chỉ đọc 10%”. Không dựa trên kết quả B_GPT_DIRECT để tạo đoạn hoặc schema. Không tự gọi GPT bổ sung khi phần sau bài xuất hiện thuộc tính mới. Trường bị thiếu do đoạn ngắn là một kết quả cần đo của phương án này.

Có thể hỗ trợ cấu hình bổ sung như đoạn đầu, nhiều đoạn rải đều, hoặc tỷ lệ 5%/20%, nhưng phải có mã cấu hình riêng và không chạy trong 800 kết quả chính. Nếu bổ sung phương pháp chọn đoạn thông minh, tính cả thời gian của nó.

## 6 Mô hình và môi trường thực thi

### 6.1 GLiNER2

Mặc định tải `fastino/gliner2-base-v1`, chạy cục bộ, không huấn luyện lại. [Trang mô hình](https://huggingface.co/fastino/gliner2-base-v1) công bố bản cơ sở khoảng 205 triệu tham số và hỗ trợ trích xuất có cấu trúc. Dùng chức năng tạo các bản ghi nhiều trường, không chỉ lấy các danh sách tên và số rồi ghép theo vị trí. [Tài liệu thư viện](https://github.com/fastino-ai/GLiNER2).

- Ghim phiên bản thư viện `gliner2`, `torch`, `transformers` và mã revision của trọng số sau bước kiểm tra môi trường. Không để `latest` trong bản khóa cuối cùng.
- Python mục tiêu 3.11. Một môi trường CPU chạy được là yêu cầu tối thiểu; GPU là cấu hình bổ sung có nhãn riêng.
- Cấu hình mặc định: CPU, float32, một tài liệu mỗi lần, số luồng CPU được khai báo và ghi lại. Dùng chế độ đánh giá và tắt tính gradient.
- Ngưỡng mặc định 0.5 nếu giao diện phiên bản chọn hỗ trợ; ghi cả các ngưỡng thực tế khác của bộ giải mã. Không chỉnh theo test.
- Tải mô hình một lần; chạy làm nóng bằng văn bản ngắn ngoài test. Ghi thời gian tải và thời gian làm nóng riêng.
- Kiểm tra giới hạn độ dài đầu vào tính cả schema, giới hạn đoạn trích và giới hạn số bản ghi của checkpoint. [Kiến trúc GLiNER2 gốc](https://arxiv.org/html/2507.18546v1#A1) có bộ dự đoán số bản ghi hữu hạn; không giả định mô hình xử lý số đối tượng vô hạn.
- Ưu tiên toàn bài trong một lần nếu vừa giới hạn. Nếu dài quá, chia theo ranh giới câu, giữ vùng chồng lấn tối đa 64 token nội bộ trong phần ngân sách còn lại; nếu schema chiếm hết ngân sách thì trả lỗi giới hạn rõ ràng. Không cho thư viện âm thầm cắt cuối bài.
- Dùng cùng quy tắc chia và ghép cho A_GLINER_KNOWN và B_HYBRID_SHORT; số đoạn có thể khác vì độ dài schema khác. Ghi lại mọi đoạn và số lượt chạy mạng.
- Ghép bản ghi theo tên đối tượng chuẩn hoá từ văn bản/đầu ra, không dùng gold. Gộp dữ kiện trùng hệt. Khi có giá trị xung đột, giữ cả hai trong danh sách giá trị và ghi xung đột; không dùng LLM hoặc đáp án để chọn số đúng.
- Khi đầu ra đạt trần số bản ghi, ghi cờ nghi ngờ bão hoà nếu có thể quan sát, vẫn giữ kết quả thực. Không sử dụng số hàng gold để quyết định chạy lại.

### 6.2 GPT 5.5 trong Codex

Dùng tài khoản ChatGPT đã đăng nhập vào Codex. Tài liệu chính thức mô tả đăng nhập bằng tài khoản ChatGPT và lệnh `codex login`; không cần khóa API riêng cho cách đăng nhập này. Người dùng thực hiện bước đăng nhập nếu chưa có phiên hợp lệ. [Đăng nhập Codex](https://learn.chatgpt.com/docs/auth).

Chọn rõ **`gpt-5.5`**, được liệt kê trong [danh sách mô hình Codex](https://learn.chatgpt.com/docs/models). Kiểm tra quyền truy cập trên đúng máy/tài khoản dùng để chạy. Không tự chuyển sang mô hình khác. Ghi tên mô hình yêu cầu và tên quan sát được; nếu công cụ không công bố phiên bản trọng số cụ thể, để thông tin đó là chưa biết. Không tự gắn snapshot của API cho mô hình chạy qua Codex.

Cách chạy tự động mặc định là **Codex CLI**, tức chương trình Codex chạy từ dòng lệnh. Chương trình Python điều phối các phiên mới bằng `codex exec`. Tài liệu hỗ trợ nhận đầu vào từ stdin, xuất sự kiện bằng `--json`, ràng buộc kết quả bằng `--output-schema`, lưu câu trả lời cuối bằng `-o` và dùng lại trạng thái đăng nhập CLI. [Chạy Codex từ chương trình](https://learn.chatgpt.com/docs/non-interactive-mode).

Các yêu cầu triển khai dưới đây là thiết kế thí nghiệm, cần kiểm tra khả năng thực tế trong bước thiết lập:

- Ghim phiên bản Codex CLI cùng các phụ thuộc. Kiểm tra lệnh trợ giúp, trạng thái đăng nhập và quyền chọn `gpt-5.5`; không giả định phiên đăng nhập trên giao diện web tự có sẵn trong máy chạy Python.
- Mức suy luận mục tiêu là `low`, thống nhất cho ba loại tác vụ GPT. Xác minh tên tham số của phiên bản CLI đã cài; ghi mức thực tế và khóa trước test. Không truyền các tham số riêng của Responses API vào CLI.
- Mỗi mẫu × phương pháp × lần thử dùng một phiên mới; không tiếp tục hoặc sao chép phiên đã thấy mẫu khác. Việc tiếp tục chiến dịch chỉ là đọc danh sách công việc còn thiếu, không nối lịch sử suy luận.
- Gửi chỉ dẫn và văn bản trực tiếp qua stdin. Dùng thư mục thực thi riêng, có cấu hình cố định, chỉ chứa dữ liệu được phép của tác vụ. Kiểm tra các nguồn tự nạp như chỉ dẫn dự án, ký ức, kết nối và lịch sử; không đưa đáp án hoặc nội dung từ quá trình triển khai vào ngữ cảnh.
- Phép đo chính yêu cầu mô hình trả bảng/schema trực tiếp. Không sử dụng trình duyệt, tìm kiếm, công cụ đọc tệp, chương trình trích xuất khác hoặc tác nhân bổ sung để tìm dữ kiện. Áp dụng giới hạn công cụ được môi trường hỗ trợ và kiểm tra nhật ký sự kiện. Chỉ đặt thư mục làm việc hoặc chế độ chỉ đọc không bảo đảm không thể đọc các tệp bên ngoài.
- Giữ nguyên các chính sách quyền bắt buộc của môi trường. Nếu không kiểm soát được nguồn ngữ cảnh, không xác nhận được đúng mô hình hoặc không quan sát đủ để kiểm tra công cụ, ghi rõ hạn chế và không gắn nhãn các kết quả đó là cấu hình chính đã kiểm soát. Nếu phát hiện công cụ bị cấm đã dùng, ghi `protocol_violation`, giữ log và chấm như thất bại trong điểm chính; không âm thầm chạy lại để lấy câu trả lời khác.
- Với nhóm B, JSON Schema chỉ ràng buộc hình dạng các mảng/bản ghi, để tên thuộc tính là chuỗi tự do. Dùng cùng yêu cầu định dạng và cấu hình đầu ra được hỗ trợ cho A_GPT_KNOWN và B_GPT_DIRECT. Kiểm tra JSON bằng mã sau khi nhận.
- Lưu đầu vào đã gửi, cấu hình, câu trả lời cuối nguyên bản, sự kiện công cụ, mã thoát, ID phiên nếu có và dấu thời gian do chương trình điều phối ghi. Không yêu cầu mô hình xuất chuỗi suy luận hoặc tự báo thời gian chạy.
- Chỉ ghi trạng thái/phương thức đăng nhập; không đọc hoặc chép nội dung bí mật đăng nhập vào dữ liệu thí nghiệm. Xác minh đang dùng tài khoản ChatGPT theo yêu cầu; không tự chuyển sang API key khi gặp lỗi hoặc hết hạn mức.
- Cách chạy này sử dụng quyền và hạn mức Codex của tài khoản. Không coi số tác vụ chạy được là vô hạn; khi dịch vụ báo hết hạn mức, lưu tiến độ để tiếp tục sau.

### 6.3 Khi người dùng chỉ sử dụng giao diện Codex

Không giả định một chương trình Python có thể gọi trực tiếp mô hình của cuộc trò chuyện hiện tại. Nếu máy chạy chưa có CLI hoặc người dùng muốn thao tác trên giao diện, cung cấp chế độ xuất/nhập tác vụ: xuất lời nhắc riêng cho từng mẫu/phương pháp, người dùng mở phiên Codex mới với GPT 5.5, rồi nhập lại câu trả lời nguyên bản để chương trình tiếp tục GLiNER2 và chấm điểm.

Mỗi tác vụ có `task_id`, `sample_id`, `arm`, `input_hash` và băm lời nhắc; bộ nhập kiểm tra trùng, thiếu, nhầm tác vụ và định dạng. Không chỉnh tay giá trị dự đoán. Tách kết quả chế độ này bằng `execution_mode = codex_ui_import`; không trộn với `codex_cli` trong một bảng thời gian chính. Ghi mức suy luận, mô hình và nguồn bằng chứng mà giao diện thực sự cung cấp. Việc mở phiên mới và ngăn truy cập dữ liệu ngoài tác vụ vẫn áp dụng.

Nếu giao diện không cung cấp cách đo thời gian đáng tin cậy, để các chỉ số thời gian GPT/hệ thống kết hợp là null kèm lý do và chỉ báo độ chính xác của phần đó. Không dùng thời gian sao chép/dán hoặc thời gian do GPT tự ước lượng để thay thế. Khi ấy phần so sánh thời gian chưa hoàn tất; nêu rõ trong báo cáo.

## 7 Giao ước dữ liệu trung gian

Các cấu trúc dưới đây mô tả giao ước nội bộ. Codex tạo lớp kiểm tra dữ liệu tương ứng, ví dụ bằng Pydantic. JSON Schema gửi Codex phải tương thích với phiên bản CLI được chọn; bộ thích ứng phải giữ nguyên ngữ nghĩa và kiểm tra lại đầu ra bằng mã.

### 7.1 Cấu trúc trường

```json
{
  "tables": [
    {
      "table_name": "players",
      "entity_type": "basketball player",
      "identity_field": "entity_name",
      "fields": [
        {
          "name": "points",
          "description": "Points scored by this player in the game being reported",
          "value_type": "number",
          "unit": "points"
        }
      ]
    }
  ]
}
```

Ví dụ này chỉ minh hoạ định dạng cho người triển khai, **không chèn vào lời nhắc nhóm B dưới dạng ví dụ bóng rổ**. Trong schema do GPT tạo, không yêu cầu trả tên cầu thủ hay giá trị của đối tượng. Các tên trường phải không trùng nhau trong cùng bảng. `value_type` là mô tả cho chuẩn hoá; GLiNER2 vẫn lấy chuỗi trong nguồn trước khi đổi sang số bằng mã.

Bộ chuyển schema sang GLiNER2 dùng khóa kỹ thuật an toàn `t0`, `f0`… và bảng ánh xạ ngược, giữ nguyên tên/mô tả ngữ nghĩa. Nếu API thư viện chèn mô tả bằng cú pháp chuỗi như dấu `::`, phải tránh để nội dung GPT tạo làm thay đổi cú pháp. Xác minh khả năng hỗ trợ giới hạn số bảng/trường; vượt giới hạn phải ghi trạng thái, không cắt trường một cách im lặng.

### 7.2 Đầu ra bảng chung

```json
{
  "tables": [
    {
      "table_name": "players",
      "entity_type": "basketball player",
      "field_names": ["points"],
      "rows": [
        {
          "entity_name": "Example Player",
          "cells": [
            {"field_name": "points", "raw_values": ["24"]}
          ]
        }
      ]
    }
  ]
}
```

Mỗi ô chứa danh sách chuỗi để biểu diễn một giá trị hoặc xung đột/multiple values. Danh sách rỗng hoặc ô vắng là thiếu dữ kiện; số 0 là một giá trị thực. Xuất bảng rộng CSV/HTML từ cấu trúc này; mọi giá trị xung đột phải còn truy xuất được.

GPT được yêu cầu trả định dạng này; GLiNER2 có thể trả định dạng gốc rồi chuyển bằng mã. Các khóa `entity_name`, `cells`, `raw_values` là hạ tầng, không tính là thuộc tính số liệu dự đoán. `field_names` giữ cả trường đã dự đoán nhưng chưa có giá trị.

Trường ô chưa có trong `field_names` được ghi là lỗi cấu trúc ngữ nghĩa nhưng vẫn đưa vào tập trường và tập dữ kiện khi chấm để không bỏ qua dự đoán thừa. Bản ghi không có định danh nhưng có số liệu được gắn ID chưa giải quyết riêng để tính lỗi; không tự lấy tên từ gold.

Thông tin bằng chứng hoặc điểm tin cậy GLiNER2 được lưu trong tệp phụ theo vị trí ký tự nếu có. Không ép GPT sinh thêm tọa độ từng đoạn trong phép so sánh chính, vì đó là một nhiệm vụ khác. Không dùng điểm tin cậy giữa hai mô hình như đại lượng đã được hiệu chuẩn tương đương.

### 7.3 Kết quả cấp tài liệu

Mỗi cấu hình × mẫu lưu: `run_id`, `sample_id`, `arm`, `status`, phiên bản mô hình, băm đầu vào/lời nhắc/schema, đầu ra thô, đầu ra chuẩn hoá, thời gian từng bước, lỗi, số lần thử và đường dẫn tệp bằng chứng. Trạng thái phân biệt `success`, `empty_prediction`, `invalid_output`, `refusal`, `incomplete`, `timeout`, `request_failed`, `input_limit`, `insufficient_fragment`, `protocol_violation`, `pending_external`, `blocked`. Lưu thêm `execution_mode`, thông tin mô hình thực sự quan sát được và tình trạng kiểm soát ngữ cảnh/công cụ; không giả định mọi tác vụ đều có số đo thời gian.

## 8 Nội dung lời nhắc và phạm vi trích xuất

Viết ba lời nhắc bằng tiếng Anh, đặt trong tệp riêng và tính SHA256: `known_table.txt`, `short_schema.txt`, `direct_table.txt`. Không dùng ví dụ có nhãn trong cấu hình chính. Không xem gold test để sửa lời nhắc.

Chỉ dẫn chung cho bước trích xuất: lấy dữ kiện được văn bản hỗ trợ về trận đang tường thuật; gắn đúng cầu thủ/đội và đúng đại lượng; bỏ số liệu của trận khác, thống kê trung bình mùa, dự đoán tương lai và con số gây nhiễu. Không bổ sung kiến thức từ bên ngoài. Không tự điền 0 khi thiếu thông tin. Không tính ra giá trị mới nếu văn bản không phát biểu; chuẩn hoá cách viết số do mã chung thực hiện. Phân biệt số lần ném trúng, số lần thử và tỷ lệ ném trúng; không lấy tỷ số đội làm điểm cầu thủ.

Lời nhắc nhóm A yêu cầu đúng các trường được cho, tự tìm đối tượng và số liệu, không bắt buộc có mọi ô. Lời nhắc tạo schema chỉ yêu cầu cấu trúc có căn cứ trong đoạn đã thấy, gộp cách diễn đạt đồng nghĩa, không bịa thuộc tính “thường có” trong bóng rổ. Lời nhắc trực tiếp yêu cầu tự xác định bảng, trường và số liệu từ toàn bài trong một yêu cầu.

GLiNER2 nhận các hạn chế phù hợp qua mô tả loại bản ghi/trường và cấu hình; không giả định nó hiểu một system prompt như GPT. Không bổ sung bộ luật trích xuất số liệu riêng cho GLiNER2 trong lần chạy chính, vì khi đó sẽ khảo sát thêm một hệ thống khác.

Lưu bản yêu cầu đã kết xuất cho từng mẫu, che bí mật xác thực. Không dùng nội dung dữ liệu như lệnh hệ thống. Không cho các câu trong bài thay đổi công cụ, đường dẫn, phương pháp chấm hoặc schema nhóm A.

## 9 Chuẩn hoá và chấm độ chính xác

### 9.1 Đáp án và đơn vị chấm

Chấm theo các ô không rỗng của bản Text-to-Table đã chọn. Không lấy bảng đầy đủ từ RotoWire gốc để phạt những thông tin chưa xuất hiện trong văn bản.

Biểu diễn một dữ kiện bằng `(sample_id, table_type, entity_id, field_id, normalized_value)`. Sai đối tượng hoặc sai thuộc tính đều là sai dù con số có xuất hiện trong bài. Thứ tự bảng, hàng và cột không ảnh hưởng kết quả.

### 9.2 Chuẩn hoá chung

- Chuỗi: Unicode NFC, bỏ khoảng trắng thừa, chuẩn hoá hoa thường khi so sánh tên; giữ nguyên bản thô.
- Tên bảng và trường: dùng từ điển đồng nghĩa được khóa trước test, có phạm vi theo loại đối tượng. Không gộp “attempted” với “made”, phần trăm với số lần, điểm đội với điểm cầu thủ.
- Thuộc tính số: dùng Decimal, hỗ trợ số viết bằng chữ và biểu diễn thập phân hợp lệ. Quy tắc phần trăm phải theo định nghĩa trường; không tự hiểu `0.5` là `50%` nếu thiếu căn cứ. Không chấm bằng độ gần ngữ nghĩa của con số.
- Không tính tổng, tỷ lệ hoặc suy ra dữ kiện mới để lấp ô. Không sửa số dự đoán thành số gần gold.
- Định danh đối tượng: khớp tên chuẩn trước; cho phép tên rút gọn/họ khi ánh xạ duy nhất trong loại đối tượng của tài liệu. Chỉ bộ chấm được dùng danh sách gold để đối chiếu định danh. Nếu mơ hồ thì không nhận là khớp; không dùng giá trị thống kê để chọn người có điểm phù hợp.
- Từ điển dùng để chấm không được truyền ngược vào mô hình nhóm B. Tên trường chưa ánh xạ vẫn là dự đoán chưa khớp, không bị xóa.
- Khử dữ kiện trùng hệt bằng phép lấy tập hợp. Các số khác nhau trong cùng ô giữ thành các dữ kiện khác nhau: một số đúng có thể được TP, các số thừa là FP.

Đối với những tên trường mới chưa nằm trong từ điển, có thể tạo một đánh giá ngữ nghĩa phụ do người rà soát ẩn danh phương pháp. Không dùng kết quả phụ để thay âm thầm ánh xạ của điểm chính. Không dùng GPT 5.5 tự chấm đối thủ và chính nó làm thước đo duy nhất.

### 9.3 Các thước đo bắt buộc

Với tập dữ kiện dự đoán P và đáp án G: `TP = |P ∩ G|`, `FP = |P − G|`, `FN = |G − P|`. Tính precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2TP/(2TP+FP+FN). Precision là tỷ lệ đúng trong dữ kiện lấy ra; recall là tỷ lệ dữ kiện đúng đã tìm thấy.

- **Micro precision, recall, F1 của dữ kiện**: cộng TP/FP/FN trên toàn bộ 200 tài liệu rồi tính. Đây là thước đo chính cho “độ chính xác”.
- **Macro F1**: tính mỗi tài liệu rồi lấy trung bình, để các bài dài không lấn át hoàn toàn.
- **F1 trường**: chấm tập `(loại bảng, tên thuộc tính)`; tính cả các trường dự đoán rỗng trong `field_names`. Báo riêng nhóm B. Điểm trường của nhóm A không thể hiện khả năng tự tìm trường.
- **F1 định danh hàng**: chấm tập đối tượng, độc lập với số liệu.
- **Tỷ lệ tài liệu đúng toàn bộ**: đúng tập trường, đối tượng và dữ kiện sau chuẩn hoá; không yêu cầu cùng thứ tự trình bày.
- **Tỷ lệ đầu ra hợp lệ, thất bại và trùng/xung đột**.
- Báo theo toàn bộ bảng và tách bảng cầu thủ/đội bóng; thêm số lượng dữ kiện gold để biết mẫu số.

Nếu dự đoán rỗng nhưng gold không rỗng: F1 = 0. Nếu cả hai rỗng: document F1 = 1 theo quy ước ghi công khai, đồng thời báo số trường hợp này. Nếu chỉ một mẫu số precision/recall bằng 0 còn tập kia không rỗng, đặt chỉ số đó bằng 0. Không dùng nhiều ô trống để làm tăng accuracy.

Kết quả lỗi hoàn toàn được xem là dự đoán rỗng trong điểm chính, nên tất cả dữ kiện gold là FN. JSON bị cắt/hỏng ở cấp tài liệu không được sửa bằng LLM; giữ đầu ra thô và chấm thất bại. Với JSON đọc được nhưng từng ô không hợp lệ, giữ các ô đọc được theo quy tắc xác định, ghi lỗi và tính các ô không có dự đoán là thiếu. Báo thêm điểm trên các trường hợp thành công như phân tích phụ, không thay thế điểm của 200 mẫu.

### 9.4 Độ không chắc chắn và kiểm tra lỗi nhãn

Tính khoảng tin cậy 95% cho chênh lệch F1 và tỷ lệ thời gian bằng lấy mẫu lại có hoàn lại theo tài liệu, cùng chỉ số mẫu cho hai phương pháp; seed 2026, 2000 lần. Nếu có nhiều bài cùng trận và khóa trận tin cậy, lấy mẫu lại theo cụm trận. Tính lại micro F1 từ TP/FP/FN mỗi lần, không lấy trung bình các F1 rồi gọi là micro.

Phương pháp này đo biến thiên theo mẫu dữ liệu của một lần chạy; không đo toàn bộ tính ngẫu nhiên của mô hình. Không tuyên bố hơn tuyệt đối từ một lần chạy.

Bản đáp án chuyển thể vẫn có thể có lỗi. Chọn trước 20 ID trong 200 để kiểm tra thủ công, phân biệt lỗi schema, thiếu trường do đoạn trích, sai đối tượng, sai giá trị, sai phạm vi thời gian, và nghi ngờ nhãn. Giữ điểm theo nhãn gốc làm chính. Mọi sửa nhãn phải có tệp thay đổi, áp dụng đồng đều cho bốn cấu hình và xuất điểm phụ riêng.

## 10 Đo thời gian

Đo bằng đồng hồ đơn điệu độ phân giải cao, ví dụ `time.perf_counter_ns()`. Đơn vị lưu là mili giây. Số liệu chính là độ trễ ứng dụng của từng phương pháp khi GLiNER2 đã được tải. Thời gian phía GPT gồm quá trình chạy Codex và mạng tới máy chủ; đây không phải thời gian tính toán riêng của GPT hay so sánh cùng phần cứng.

- `prepare_ms`: lấy đoạn, chuẩn bị schema và yêu cầu; chỉ tính các bước cần khi xử lý bài mới.
- `schema_codex_ms`: thời gian GPT tạo schema qua Codex, từ ngay trước khi khởi chạy tác vụ đến khi nhận câu trả lời cuối và tác vụ kết thúc; gồm khởi động CLI, điều phối và mạng.
- `extract_ms`: với GLiNER2, gồm tiền xử lý, tất cả đoạn, giải mã và ghép kết quả; với GPT, gồm toàn tác vụ Codex tạo bảng và chi phí khởi chạy phiên. Không cộng lại phần này lần nữa vào thời gian toàn công việc.
- `postprocess_ms`: đọc/kiểm tra JSON, chuẩn hoá và dựng bảng.
- `retry_wait_ms`: thời gian chờ gọi lại nếu có.
- `latency_e2e_ms`: thời gian từ bắt đầu xử lý mẫu đến bảng chuẩn hoá cuối cùng hoặc trạng thái lỗi; bao gồm mọi lần thử và chờ trong công việc đó.

Với B_HYBRID_SHORT, độ trễ phải gồm lấy đoạn, GPT tạo trường, chuyển schema, GLiNER2 xử lý toàn bài và hậu xử lý. Không báo riêng thời gian GLiNER2 như thời gian của cả hệ thống.

Tải dữ liệu, tải mô hình, làm nóng, chấm điểm và vẽ báo cáo là chi phí thiết lập/phân tích riêng. Lưu thời gian toàn chiến dịch, số thành công, tốc độ tài liệu/giây, median, mean, p90, p95. Báo độ trễ khi thành công và độ trễ của toàn bộ nỗ lực riêng; lỗi nhanh không được diễn giải là một cải thiện tốc độ.

Mặc định mức đồng thời của benchmark là 1, batch size cục bộ là 1. Xáo thứ tự tài liệu cố định; luân phiên thứ tự bốn cấu hình theo vòng Latin để giảm ảnh hưởng thời điểm chạy Codex. Không chạy tất cả GPT vào một thời điểm và GLiNER2 vào một thời điểm khác rồi bỏ qua điều kiện môi trường. Nếu GPU được dùng, đồng bộ thiết bị ở biên đo và ghi rõ GPU, phiên bản CUDA, kiểu số.

Báo cấu hình CPU, RAM, hệ điều hành, số luồng, GPU nếu có, phiên bản thư viện, thời gian UTC, phiên bản Codex, chế độ chạy, mức suy luận và các cài đặt bổ sung quan sát được. Không tuyên bố tốc độ GPU, chi phí phần cứng hoặc thời gian máy chủ nội bộ khi chỉ đo được độ trễ phía khách.

Khi báo tỷ lệ thời gian giữa hai phương pháp, dùng `sum(latency_method_1) / sum(latency_method_2)` trên cùng tập ID thành công ở cả hai phương pháp; công khai số mẫu ghép cặp và tỷ lệ lỗi riêng. Lấy mẫu lại trên chính tập ID ghép cặp này để tính khoảng tin cậy của tỷ lệ. Nếu không có cặp thành công, để tỷ lệ là null kèm lý do. Điểm chất lượng chính vẫn dùng đủ 200 mẫu, gồm cả mẫu lỗi. Chỉ tính tỷ lệ thời gian khi các cặp có cùng chế độ đo và số đo thật; công khai số mẫu có thời gian hợp lệ. Với chế độ nhập từ giao diện, áp dụng giới hạn ở mục 6.3, không ước lượng thời gian còn thiếu.

## 11 Phạm vi đo tài nguyên

Không yêu cầu thống kê token đầu vào/đầu ra, token suy luận, token cache, token nội bộ GLiNER2 hoặc quy đổi chi phí tiền. Không tạo mô-đun, kiểm thử hoặc biểu đồ riêng cho các hạng mục này. Nếu nhật ký Codex có sẵn `usage`, có thể giữ nguyên cùng log mà không phân tích; việc có trường này không ảnh hưởng nghiệm thu.

Các giới hạn độ dài cần để mô hình chạy đúng vẫn được kiểm tra bằng bộ xử lý của mô hình; chúng không phải phép đo tài nguyên nghiên cứu. Tỷ lệ số từ chỉ mô tả mức rút ngắn đầu vào của bước tạo trường. Báo cáo không suy ra mức tiết kiệm tiền hoặc token từ tỷ lệ này.

## 12 Lỗi chạy và tiếp tục công việc

Lưu sau mỗi yêu cầu bằng ghi tệp nguyên tử. Hỗ trợ tiếp tục chạy từ kết quả đã có; khóa kết quả gồm mẫu, cấu hình, băm văn bản/schema/lời nhắc, phiên bản mô hình và cấu hình suy luận. Thay bất kỳ thành phần nào phải tránh tái dùng kết quả cũ sai điều kiện.

Không coi việc đọc kết quả lưu sẵn là một lượt suy luận mới có độ trễ 0. Đánh giá lại từ log không mở tác vụ Codex mới. Chạy lại để đo mới cần `run_id` mới; không lấy độ trễ đọc đĩa trộn với độ trễ mô hình.

Mặc định tối đa 3 lần thử tác vụ với lỗi mạng hoặc dịch vụ tạm thời mà Codex xác định được; tôn trọng thời gian chờ do dịch vụ báo. Ghi mọi lần khởi chạy lại và thời gian chờ; các lần thử nội bộ không quan sát được phải ghi là chưa biết, không giả định bằng 0. Thời gian tác vụ vẫn bao gồm phần chờ nội bộ đã xảy ra. Không chạy lại để tìm đáp án hay hơn. Lỗi đăng nhập/quyền mô hình hoặc hết hạn mức dừng nhánh GPT và lưu trạng thái rõ ràng, vẫn hoàn thiện phần không cần Codex. Các bài chưa được thử tiếp tục ở trạng thái chờ, không tính như đã hoàn tất.

Schema rỗng ở B_HYBRID_SHORT tạo bảng rỗng, không tự điền schema phổ biến. Schema sai định dạng tạo trạng thái lỗi, không gọi LLM sửa bằng toàn bài. Không tự chuyển sang GPT trực tiếp khi GLiNER2 lỗi trong cấu hình kết hợp.

Đặt thời gian chờ tối đa có cấu hình, mặc định 300 giây mỗi tác vụ CLI, xác nhận bằng pilot trước khi khóa. Khi hết thời gian, kết thúc đúng tiến trình và các tiến trình con của tác vụ để tránh chúng tiếp tục chạy ngầm. Khi người dùng đặt giới hạn số tác vụ hoặc tổng thời gian, dừng có lưu tiến độ. Bản triển khai phải có chế độ kiểm tra dữ liệu và liệt kê công việc mà không khởi chạy Codex. Không tự mua thêm hạn mức hoặc thay phương thức đăng nhập.

## 13 Các thành phần phần mềm cần bàn giao

Xây một dự án Python có giao diện dòng lệnh. Không yêu cầu website hoặc cơ sở dữ liệu. Ưu tiên các mô-đun nhỏ, có giao ước rõ, không viết toàn bộ trong một notebook khó tiếp tục chạy.

| Thành phần | Trách nhiệm |
|---|---|
| `data` | Tải/đọc bản chuyển thể, kiểm tra cặp văn bản và bảng, chuẩn hoá ID, lấy mẫu |
| `schemas` | Cấu trúc dữ liệu, schema biết trước, kiểm tra schema dự đoán, chuyển cú pháp GLiNER2 |
| `snippets` | Chọn đoạn theo số từ, đo tỷ lệ số từ, lưu biên ký tự |
| `models/gliner2_adapter` | Tải mô hình, xử lý giới hạn, trích xuất có cấu trúc |
| `models/codex_gpt55_adapter` | Phiên Codex CLI mới, stdin/JSON Schema, sự kiện, thời gian, lỗi và kiểm tra giao thức |
| `external_tasks` | Xuất/nhập tác vụ cho chế độ giao diện, kiểm tra ID/băm và giữ câu trả lời gốc |
| `pipelines` | Bốn cấu hình; không trộn dữ liệu giữa các cấu hình |
| `evaluation` | Ánh xạ bảng/trường/đối tượng, chuẩn hoá, TP/FP/FN, khoảng tin cậy |
| `runner` | Thứ tự chạy, checkpoint kết quả, resume, dấu vết cấu hình |
| `reporting` | CSV, JSON, bảng HTML xem từng mẫu, biểu đồ và báo cáo tiếng Việt |

Bàn giao `README.md`, mã nguồn, cấu hình mẫu, tệp khóa phụ thuộc, ba lời nhắc, kiểm thử, hướng dẫn cài Codex CLI, đăng nhập bằng tài khoản ChatGPT và chọn GPT 5.5, và notebook khởi động Kaggle/Colab mỏng nếu thuận tiện. Notebook phải gọi lại mô-đun chung; không có một bản logic benchmark thứ hai.

### 13.1 Giao diện lệnh đề xuất

```bash
python -m rotowire_bench prepare --config configs/main.yaml
python -m rotowire_bench validate --config configs/main.yaml
python -m rotowire_bench pilot --split validation --limit 3 --config configs/main.yaml
python -m rotowire_bench run --config configs/main.yaml --dry-run
python -m rotowire_bench run --config configs/main.yaml --resume
python -m rotowire_bench export-tasks --config configs/main.yaml --out outputs/tasks
python -m rotowire_bench import-results --run-dir outputs/RUN_ID --from-dir outputs/codex_answers
python -m rotowire_bench evaluate --run-dir outputs/RUN_ID
python -m rotowire_bench report --run-dir outputs/RUN_ID
```

Đây là giao diện yêu cầu cho chương trình sẽ xây, không khẳng định các lệnh đang tồn tại. `dry-run`, kiểm thử logic và đánh giá log phải chạy được khi chưa đăng nhập Codex. `export-tasks`/`import-results` phục vụ chế độ giao diện; không bắt buộc đi qua các lệnh này khi dùng CLI tự động. `pilot` có gọi mô hình thật khi môi trường đã cấu hình; kết quả pilot không nằm trong 200 test.

### 13.2 Cấu hình mặc định

```yaml
dataset:
  source: xqwu/text-to-table
  subset: rotowire
  test_size: 200
  sample_seed: 42
  validation_size: 30
  validation_seed: 43
  # Adapter phải xác minh cấu trúc nguồn thực tế; subset không mặc định là HF config.
arms:
  - A_GLINER_KNOWN
  - A_GPT_KNOWN
  - B_HYBRID_SHORT
  - B_GPT_DIRECT
gliner:
  model: fastino/gliner2-base-v1
  revision: null  # Giải quyết thành revision thật trong preflight và khóa trước test.
  device: cpu
  dtype: float32
  batch_size: 1
  cpu_threads: 4
  threshold: 0.5
gpt:
  execution_mode: codex_cli  # Chế độ giao diện: codex_ui_import, báo cáo riêng.
  auth_mode: chatgpt
  model: gpt-5.5
  codex_cli_version: null  # Xác minh phiên bản thực và khóa trước test.
  reasoning_effort: low
  fresh_session_per_task: true
  tool_policy: no_external_tools  # Yêu cầu nghiên cứu; adapter xác minh cách áp dụng.
  concurrency: 1
  timeout_seconds: 300
  max_attempts: 3
snippet:
  strategy: center_contiguous
  count_unit: whitespace_words
  ratio: 0.10
  max_words: 80
evaluation:
  bootstrap_repetitions: 2000
  bootstrap_seed: 2026
  primary_metric: fact_micro_f1
run:
  repetitions: 1
  order_seed: 44
  resume: true
```

## 14 Kết quả và báo cáo cần xuất

Tối thiểu có `sample_manifest.json`, `protocol.lock.json`, `environment.json`, `snippets.jsonl`, kết quả thô và chuẩn hoá cho 800 công việc, `codex_attempts.jsonl`, `metrics_per_sample.csv`, `summary.csv`, `schema_errors.csv`, `report.md` và tệp HTML xem từng mẫu. Tệp schema dự đoán phải được lưu riêng với bảng cuối.

`summary.csv` có ít nhất: arm, execution_mode, n_expected, n_completed, n_success, n_failed, fact precision/recall/F1, macro F1, field F1, entity F1, exact-document rate, mean/median/p90/p95 latency, throughput, số lần thử và số mẫu có thời gian hợp lệ. Báo riêng độ trễ trên mẫu thành công và trên toàn bộ nỗ lực như mục 10. Dùng null/not_applicable đúng chỗ, không điền 0 cho số đo chưa có.

Báo cáo tiếng Việt trả lời trực tiếp:

1. Khi cùng biết trước trường, GLiNER2 giữ được bao nhiêu chất lượng so với GPT 5.5 và mất bao lâu để xử lý mỗi bài?
2. Khi GPT chỉ đọc đoạn ngắn, chất lượng và tổng thời gian của hệ thống kết hợp thay đổi ra sao so với GPT tạo bảng trực tiếp?
3. Sai số của phương án kết hợp chủ yếu do bỏ sót trường hay do trích sai giá trị/đối tượng?
4. Trường hợp nào GLiNER2 đáp ứng được yêu cầu ứng dụng và trường hợp nào cần xử lý thêm, dựa trên dữ kiện quan sát được?

Xuất hai bảng so sánh chính tương ứng nhóm A/B; biểu đồ F1 cạnh độ trễ; biểu đồ lỗi theo loại. Biểu đồ phải dùng số đo thực và ghi đơn vị. Không ép một kết luận GLiNER2 nhanh hơn hoặc chính xác hơn nếu số liệu không hỗ trợ. Dùng tệp HTML tĩnh để xem văn bản, đoạn trích, schema dự đoán, gold, kết quả bốn cấu hình và lỗi từng ô; chỉ trang phân tích được hiển thị gold.

Giới hạn cần nêu: chỉ 200 mẫu miền bóng rổ; một mức suy luận GPT và một checkpoint GLiNER2; khả năng nhiễm dữ liệu tiền huấn luyện không kiểm chứng được; đáp án chuyển thể có thể còn lỗi; đoạn 10% không đại diện đầy đủ; thời gian GPT gồm khởi động/điều phối Codex, mạng và máy chủ từ xa; các chỉ dẫn hệ thống và phiên bản trọng số Codex có thể không được công bố đầy đủ. Chế độ nhập qua giao diện có thể thiếu thời gian đo đáng tin cậy. Kết quả là khảo sát của cấu hình đã khóa, không đại diện mọi LLM hoặc mọi phiên bản GLiNER.

## 15 Kiểm thử và tiêu chí nghiệm thu

Các kiểm thử dùng ví dụ nhỏ do mã tạo chỉ để kiểm tra logic; không thay 200 bài thật trong benchmark. Cần các kiểm thử có khả năng bắt sai lệch đánh giá:

1. Bộ đọc giữ đúng cặp văn bản–bảng, tách được bảng cầu thủ/đội và không biến tên hàng thành tên trường.
2. Cùng seed và dữ liệu tạo đúng cùng 200 ID; resume không thay ID.
3. Một số đặt trong gold nhưng không có trong văn bản không xuất hiện trong payload nhóm B; sơ đồ đối tượng inference không chứa gold. Cả hai cấu hình A nhận cùng schema không có tên cầu thủ hoặc số liệu. Kiểm tra payload, tệp khả dụng và ngữ cảnh tự nạp của phiên Codex: phiên tạo trường B chỉ có đoạn ngắn, không có toàn bài hoặc lịch sử triển khai.
4. Đoạn trích là chuỗi con, giữ nguyên từ và đáp ứng cả ngưỡng 10% số từ lẫn tối đa 80 từ; lựa chọn không phụ thuộc gold. Bài quá ngắn trả đúng `insufficient_fragment`.
5. Lấy đúng số nhưng gắn nhầm người bị tính FP và FN; đảo thứ tự bảng/hàng/cột không đổi điểm.
6. Thiếu trường làm giảm recall; tên đồng nghĩa theo từ điển vẫn khớp; trường lạ không bị loại để làm tăng precision.
7. Null khác 0; phần trăm khác số lần; dữ kiện trùng không tăng TP; giá trị xung đột không bị che giấu.
8. Mẫu lỗi vẫn nằm trong mẫu số 200 và giảm điểm chính; bảng đọc từ cache không được tính như suy luận tức thời.
9. Thời gian hệ thống kết hợp gồm cả GPT tạo trường và GLiNER2 trích xuất; mọi lần thử và thời gian chờ gọi lại được ghi và nằm trong thời gian toàn công việc, không bị tính hai lần khi tổng hợp.
10. Có kiểm thử GLiNER2 thực trên validation nếu tải được mô hình, kiểm tra nhiều đối tượng và không cắt văn bản im lặng. Kiểm thử mô phỏng Codex phải được gắn nhãn mock và không đi vào báo cáo hiệu năng thật.
11. Bộ điều phối tạo phiên Codex mới cho từng tác vụ, thu đúng câu trả lời cuối, nhận ra lỗi/vi phạm công cụ, kiểm tra mô hình và phương thức đăng nhập, không tự chuyển sang API key.
12. Chế độ nhập từ giao diện nhận ra ID/băm không khớp, giữ nguyên câu trả lời và để thời gian không đo được là null. Không trộn độ trễ giữa các chế độ.

Nghiệm thu triển khai khi có mã chạy được, kiểm thử logic đạt, cấu hình đã giải thích, hướng dẫn tái lập và báo cáo từ log. Nghiệm thu **thí nghiệm hoàn tất** cần đủ 800 công việc đã thực sự được thử của bốn cấu hình trên cùng 200 ID, bao gồm lỗi nếu có, và tất cả thước đo bắt buộc hoặc lý do đo không được. Trạng thái `blocked` hoặc `pending_external` do thiếu đăng nhập, thiếu mô hình hoặc chưa nhận câu trả lời không được tính là công việc đã thử; phải ghi chiến dịch chưa hoàn tất. Nếu chỉ hoàn thành phần độ chính xác qua giao diện và chưa đo được thời gian, phải ghi phần so sánh thời gian chưa hoàn tất. Không đặt ngưỡng F1 tối thiểu để nghiệm thu: điểm thấp vẫn là kết quả khoa học hợp lệ.

Nếu thiếu dữ liệu, Codex CLI/phiên đăng nhập, quyền truy cập GPT 5.5 hoặc khả năng tải trọng số, Codex vẫn hoàn thiện mọi phần không bị chặn, chạy kiểm thử không cần dịch vụ, lưu danh sách công việc còn lại và hướng dẫn tiếp tục. Không bịa số đo, đổi mô hình hoặc tuyên bố benchmark hoàn tất khi mới chạy mô phỏng.

## 16 Thứ tự triển khai cho Codex

1. Kiểm tra workspace và hướng dẫn dự án hiện có; xác minh tệp dữ liệu, model ID, giao diện Codex, phương thức đăng nhập và phụ thuộc. Chỉ sửa các hạng mục phục vụ đặc tả này.
2. Hoàn thiện giao ước dữ liệu, bộ đọc, danh sách 200 mẫu và các kiểm thử chấm điểm trước khi gọi mô hình hàng loạt.
3. Viết bộ chọn đoạn và ba lời nhắc; triển khai hai bộ thích ứng mô hình và bốn cấu hình.
4. Chạy pilot trên validation, sửa lỗi kỹ thuật, khóa cấu hình và từ điển chuẩn hoá. Lưu báo cáo preflight, bao gồm giới hạn GLiNER2, quyền truy cập GPT 5.5 trong Codex và khả năng tách ngữ cảnh của các tác vụ.
5. Chạy bốn cấu hình trên danh sách đã khóa khi môi trường cho phép, ghi kết quả từng mẫu và hỗ trợ tiếp tục khi gián đoạn.
6. Chấm tự động, kiểm tra lỗi nhãn theo danh sách kiểm tra thủ công đã chọn trước, tạo bảng/biểu đồ và báo cáo tái lập.

Thực hiện đủ hai mục tiêu người dùng đã nêu. Những phần mở rộng như huấn luyện lại, GLiNER2.5, thêm LLM, sinh dữ liệu hoặc nhiều chiến lược đọc đoạn chỉ là nghiên cứu tiếp theo, không phải điều kiện để hoàn thành đặc tả này.
