# Phase 1: Text Document to CSV Table

## 1. Mục tiêu của phase này

Phase 1 của dự án đang tập trung vào bài toán chuyển đổi văn bản tự nhiên thành bảng dữ liệu có cấu trúc.

Cụ thể, hệ thống đọc nội dung từ file văn bản trong thư mục `Code/Input`, gửi nội dung đó cho một mô hình LLM thông qua OpenRouter, yêu cầu mô hình trích xuất dữ liệu quan trọng dưới dạng JSON, sau đó chương trình Python tự chuyển JSON đó thành file CSV trong thư mục `Code/Output`.

Ở trạng thái hiện tại, dự án chưa thực hiện đầy đủ bài toán Text-to-SQL theo nghĩa tạo câu truy vấn SQL. Phần đang làm là bước nền tảng trước đó: biến văn bản phi cấu trúc hoặc bán cấu trúc thành dữ liệu dạng bảng. Khi dữ liệu đã nằm trong CSV, các phase sau có thể dùng bảng này để nạp vào database, sinh schema, hoặc tạo câu SQL.

## 2. Bài toán đang xử lý

Input hiện tại là một file `.txt` chứa dữ liệu dạng văn bản dài. Ví dụ trong `Code/Input/Document.txt`, dữ liệu mô tả bảng điểm môn Dự án bằng tiếng Việt, bao gồm thông tin như:

- Họ tên sinh viên
- Mã sinh viên
- Ngày sinh
- Lớp
- Khóa
- Điểm thành phần
- Điểm cuối kỳ
- Tổng điểm

Điểm khó của bài toán là dữ liệu không nằm sẵn trong bảng CSV/Excel, mà được viết thành câu văn. Vì vậy chương trình không thể chỉ tách bằng dấu phẩy hoặc xuống dòng. Thay vào đó, dự án dùng LLM để hiểu nội dung và suy ra cấu trúc bảng.

Output mong muốn là file:

```text
Code/Output/Table.csv
```

File CSV này có thể mở bằng Excel, Numbers, Google Sheets, hoặc được dùng tiếp trong các bước xử lý dữ liệu.

## 3. Cấu trúc project hiện tại

```text
Text2SQL/
├── Code/
│   ├── Inference.py
│   ├── Evaluate.py
│   ├── .env
│   ├── Expected/
│   │   └── README.md
│   ├── Input/
│   │   ├── Document.txt
│   │   └── Target.csv
│   └── Output/
│       └── Table.csv
├── Docs/
│   └── Phase1.md
├── Paper/
│   ├── 2507.21340v1.pdf
│   └── 2602.14743v1.pdf
├── .vscode/
│   ├── launch.json
│   └── settings.json
├── .gitignore
└── requirements.txt
```

Vai trò của các phần chính:

- `Code/Inference.py`: file chính để chạy inference, đọc input, gọi model, xử lý kết quả và ghi CSV.
- `Code/Evaluate.py`: file đánh giá tự động, so sánh bảng mẫu với bảng model sinh ra.
- `Code/.env`: nơi cấu hình API key OpenRouter, model, base URL và thông tin app.
- `Code/Input/Document.txt`: file văn bản đầu vào.
- `Code/Input/Target.csv`: bảng mẫu dùng làm đáp án chuẩn khi đánh giá.
- `Code/Output/Table.csv`: file bảng kết quả sau khi chạy chương trình.
- `requirements.txt`: khai báo thư viện Python cần cài, hiện tại là `openai`.
- `.vscode/settings.json`: cấu hình VS Code Code Runner dùng `python3`, chạy trong terminal và bỏ qua đoạn text đang bôi chọn.
- `.vscode/launch.json`: cấu hình Run/Debug trong VS Code cho `Inference.py`.

## 4. Cách chương trình chạy

Luồng xử lý chính trong `Code/Inference.py` gồm các bước sau:

1. Nạp biến môi trường từ `.env`

   Chương trình đọc `Code/.env` và `.env` ở thư mục gốc nếu có. Các biến này được dùng để lấy API key, model và endpoint OpenRouter.

2. Xác định file input

   Mặc định chương trình tìm:

   ```text
   Code/Input/Document.txt
   ```

3. Đọc nội dung văn bản

   File input được đọc bằng encoding `utf-8`. Nếu file không tồn tại hoặc rỗng, chương trình dừng và in lỗi rõ ràng.

4. Tạo OpenRouter client

   Chương trình dùng thư viện `openai`, nhưng trỏ `base_url` sang OpenRouter:

   ```text
   https://openrouter.ai/api/v1
   ```

   Vì OpenRouter tương thích với OpenAI Chat Completions API, project có thể dùng OpenAI SDK mà không cần viết HTTP request thủ công.

5. Gửi prompt cho LLM

   Prompt yêu cầu model:

   - Trích xuất dữ liệu quan trọng từ văn bản.
   - Trả về JSON duy nhất, không trả Markdown.
   - Dùng đúng cấu trúc:

     ```json
     {
       "columns": ["column name"],
       "rows": [
         {
           "column name": "value"
         }
       ]
     }
     ```

   Việc yêu cầu JSON giúp Python kiểm soát bước ghi CSV thay vì để model tự tạo CSV, vì CSV do model sinh trực tiếp thường dễ lỗi dấu phẩy, dấu ngoặc kép hoặc xuống dòng.

6. Parse JSON từ phản hồi của model

   Hàm `extract_json()` cố gắng đọc JSON từ output của model. Nếu model lỡ bọc JSON trong markdown block như ```json, chương trình cũng có logic để bóc phần JSON ra.

7. Chuẩn hóa bảng

   Hàm `normalize_table()` kiểm tra phản hồi có `columns` và `rows` hay không. Sau đó chương trình chuẩn hóa từng dòng dữ liệu về danh sách cell theo đúng thứ tự cột.

8. Ghi file CSV

   Kết quả được ghi vào:

   ```text
   Code/Output/Table.csv
   ```

   File được ghi bằng encoding `utf-8-sig` để Excel trên macOS/Windows mở tiếng Việt ổn hơn.

## 5. Cấu hình OpenRouter

File `Code/.env` hiện dùng các biến:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=~openai/gpt-latest
OPENROUTER_MAX_TOKENS=12000
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_HTTP_REFERER=
OPENROUTER_APP_TITLE=Text2SQL
```

Ý nghĩa:

- `OPENROUTER_API_KEY`: API key lấy từ OpenRouter. Đây là biến bắt buộc.
- `OPENROUTER_MODEL`: model slug dùng để chạy inference. Hiện tại dùng `~openai/gpt-latest`.
- `OPENROUTER_MAX_TOKENS`: giới hạn số token tối đa model được phép sinh ra trong một lần gọi. Giá trị hiện tại là `12000`, đủ rộng hơn cho bảng nhiều dòng nhưng vẫn tránh để request dùng mức trần quá lớn của model.
- `OPENROUTER_BASE_URL`: endpoint OpenRouter tương thích OpenAI SDK.
- `OPENROUTER_HTTP_REFERER`: thông tin website/app gửi lên OpenRouter, không bắt buộc.
- `OPENROUTER_APP_TITLE`: tên app hiển thị cho OpenRouter, không bắt buộc.

File `.gitignore` đã ignore `Code/.env` để tránh lộ API key khi đưa project lên GitHub.

## 6. Cách chạy project

Cài thư viện:

```bash
python3 -m pip install -r requirements.txt
```

Chạy bằng terminal:

```bash
python3 Code/Inference.py
```

Hoặc chạy bằng VS Code:

- Mở `Code/Inference.py`
- Bấm `Run Code`
- Hoặc vào tab Run and Debug và chọn `Run Inference.py`

Nếu muốn chỉ định input/output khác:

```bash
python3 Code/Inference.py --input Code/Input/Document.txt --output Code/Output/Table.csv
```

Nếu muốn đổi model ngay khi chạy:

```bash
python3 Code/Inference.py --model "~openai/gpt-latest"
```

Chấm kết quả sau khi đã có bảng mẫu và bảng output:

```bash
python3 Code/Evaluate.py
```

Mặc định script so sánh:

```text
Code/Input/Target.csv
Code/Output/Table.csv
```

và ghi báo cáo chi tiết vào:

```text
Code/Output/evaluation.json
```

Khi chấm, `Evaluate.py` mặc định bỏ qua cột số thứ tự (`STT`/`row_number`) vì đây thường là cột trình bày, không phải nội dung chính được trích xuất từ văn bản. Nếu muốn chấm cả cột này:

```bash
python3 Code/Evaluate.py --ignore-columns ""
```

## 7. Trạng thái VS Code hiện tại

Project đã có cấu hình để chạy thuận tiện trong VS Code.

Trong `.vscode/settings.json`:

- Code Runner dùng `python3 -u` thay vì `python`, vì trên máy hiện tại lệnh `python` không tồn tại.
- Code Runner chạy trong terminal tích hợp.
- Code Runner được cấu hình để chạy cả file Python hiện tại.

Trong `.vscode/launch.json`:

- `Run Inference.py`: chạy trực tiếp `Code/Inference.py`.
- `Run Current Python File`: chạy file Python đang mở.

## 8. Những gì Phase 1 đã hoàn thành

Phase 1 hiện đã có các phần cốt lõi:

- Đọc input từ file `.txt`.
- Gọi LLM qua OpenRouter.
- Dùng OpenAI SDK với `base_url` của OpenRouter.
- Yêu cầu model trả JSON có cấu trúc.
- Parse JSON từ phản hồi của model.
- Chuẩn hóa dữ liệu thành hàng và cột.
- Ghi kết quả ra CSV.
- So sánh CSV output với CSV mẫu bằng `Code/Evaluate.py`.
- Hỗ trợ chạy bằng terminal và VS Code.
- Có xử lý lỗi cơ bản cho thiếu input, input rỗng, thiếu API key, thiếu thư viện.

## 9. Giới hạn hiện tại

Phase 1 vẫn còn một số giới hạn:

- Chưa cố định schema đầu ra. Model tự chọn tên cột dựa trên nội dung văn bản.
- Chưa kiểm tra tính đúng/sai của từng dòng dữ liệu sau khi model trích xuất.
- Chưa có cơ chế chia nhỏ văn bản nếu input quá dài.
- Chưa có retry nếu OpenRouter lỗi mạng, rate limit hoặc model trả JSON không hợp lệ.
- Chưa có logging chi tiết để debug từng request/response.
- Chưa có test tự động.
- Chưa tạo database hoặc sinh SQL, dù tên project là `Text2SQL`.

## 10. Hướng phát triển cho Phase 2

Một số hướng hợp lý cho phase tiếp theo:

- Cố định schema cho bài toán bảng điểm, ví dụ: `student_name`, `student_id`, `date_of_birth`, `class`, `cohort`, `process_score`, `final_score`, `total_score`.
- Thêm validation để kiểm tra số lượng sinh viên, định dạng ngày sinh, điểm số và mã sinh viên.
- Thêm chunking để xử lý văn bản dài hơn giới hạn context của model.
- Ghi thêm file JSON trung gian bên cạnh CSV để dễ debug.
- Thêm retry khi model trả JSON lỗi.
- Tạo script nạp CSV vào SQLite.
- Sinh câu SQL từ câu hỏi tự nhiên dựa trên bảng đã nạp.
- Thêm README hướng dẫn cài đặt và chạy toàn bộ project.

## 11. Tóm tắt ngắn

Ở Phase 1, dự án đang xây dựng pipeline:

```text
Văn bản tiếng Việt -> LLM qua OpenRouter -> JSON có cấu trúc -> CSV
```

Đây là bước đầu để biến dữ liệu phi cấu trúc thành bảng. Sau khi bảng CSV ổn định, dự án có thể đi tiếp sang các bước gần với Text-to-SQL hơn, như tạo database, định nghĩa schema và sinh truy vấn SQL từ câu hỏi tự nhiên.
