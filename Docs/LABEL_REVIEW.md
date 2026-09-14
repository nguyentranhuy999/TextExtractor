# Rà soát đáp án của 20 ID được chọn trước

Rà soát do Codex thực hiện bằng đối chiếu trực tiếp toàn văn với gold, sau khi đóng băng giao thức test. Đây là ghi chú hỗ trợ kiểm tra, **chưa phải xác nhận độc lập của người gán nhãn**. Không sửa gold, không thay đổi từ điển chấm, không điều chỉnh mô hình/prompt từ các nhận xét này. Tất cả điểm chính vẫn dùng đáp án gốc.

Danh sách là đúng 20 ID trong `data/prepared/sample_manifest.json`, seed rà soát 2026. Nhận xét chỉ nêu các trường hợp quan sát được, không khẳng định đã liệt kê mọi lỗi.

| ID gốc | Quan sát cần rà soát | Loại |
|---|---|---|
| 6 | Gold gán Cavaliers field-goal percentage=40 trong khi văn bản có `(40)` ở vị trí thành tích series; không phát biểu tỷ lệ ném 40%. Gold gán JR Smith steals=2/3-pointers made=2 trong đoạn nói về flagrant-2; Love/Olynyk rebounds=1 không có thống kê tương ứng. | Nghi ngờ nhãn, nhầm loại số |
| 167 | Hornets points in 1st quarter=19 không được phát biểu; số 19 là điểm Wall/Zeller. Văn bản có John Wall 3 rebounds nhưng gold không có ô này. | Nghi ngờ nhãn, thiếu dữ kiện |
| 541 | Văn bản gán 3-of-9 cho Rodney Hood, gold lại gán FG made=3/attempted=9 cho Alec Burks. Bài mở đầu ghi Sacramento Kings nhưng sau đó nói New Orleans, Davis/Cousins; cần rà soát chính văn bản. | Sai đối tượng trong nhãn, nội dung nguồn không nhất quán |
| 11 | Greg Monroe được nêu 11 points; gold thêm nhiều thống kê giá trị 1 không có bằng chứng. Jonas Valanciunas 13 rebounds và Raptors 51% FG được nêu nhưng thiếu trong gold. | Nghi ngờ nhãn, thiếu dữ kiện |
| 676 | Carmelo Anthony có một số ô FT made/attempted, offensive rebounds, turnovers=2 không được phát biểu; Porzingis 3-pointers made/turnovers=2 tương tự. Bài vừa nói Rose+Porzingis=53 vừa ghi riêng 28 và 24; không suy diễn sửa số. | Nghi ngờ nhãn, nguồn mâu thuẫn |
| 225 | Thống kê chính Drummond được gán đúng theo văn bản. Paul George 7 rebounds và 5 assists xuất hiện nhưng thiếu trong gold. Đoạn `220 run` có dấu hiệu lỗi biên tập; các tổng của bộ ba dự bị không được chia cho từng người. | Thiếu nhãn, phạm vi số tổng hợp |
| 591 | Bucks points in 4th quarter=36 không được phát biểu; 36 là điểm Jabari Parker. Văn bản ghi Jared Bayless, gold Jerryd Bayless; cần phân biệt lỗi tên nguồn với mô hình. Một số số liệu ném và 17 rebounds của Giannis có trong bài nhưng thiếu gold. | Nghi ngờ nhãn, biến thể/lỗi tên |
| 552 | Hawks three-point percentage=19 và Celtics Q1 points=19 không được nêu; 19 là số free-throw attempts của Boston. Nhiều ô giá trị 1/3 ở cầu thủ không có phát biểu thống kê tương ứng. | Nghi ngờ nhãn, nhầm đơn vị/phạm vi |
| 670 | Bulls assists=27 không có phát biểu; 27 là số FT made của đội và điểm Gasol. Gold Mirotic points=17 có thể nhầm tổng Butler+Mirotic ở hiệp cuối thành điểm cá nhân. Harden turnovers=2 được nói riêng trong hiệp 4, cần phân biệt tổng trận. | Nghi ngờ nhãn, số tổng hợp, phạm vi thời gian |
| 619 | Bulls Q1 points=22 không được nêu, 22 là điểm Carter-Williams. Carter-Williams fouls=3/turnovers=4, Bayless fouls=3 và một số rebound/3PA của Butler không có bằng chứng tương ứng. | Nghi ngờ nhãn, nhầm đối tượng/thuộc tính |
| 551 | CJ McCollum FG attempted=22 không được phát biểu; văn bản nói 22 points. Plumlee 10 offensive rebounds, Nowitzki 16-of-26 và 3 three-pointers xuất hiện nhưng thiếu gold. | Nghi ngờ nhãn, thiếu dữ kiện |
| 108 | Rondo FG attempted=10 có vẻ lấy từ 10 lần ném đầu của Cousins. Một số ô giá trị 1 cho Leonard/Green không được phát biểu. Cousins 22 points và 8-of-23 có trong bài nhưng phần gold cầu thủ chỉ giữ 10 rebounds. | Sai đối tượng/phạm vi trong nhãn, thiếu dữ kiện |
| 659 | Văn bản Embiid có `a block`, gold Blocks=2. Pacers Q2 points=25 không được phát biểu; 25 là điểm Embiid. Jeff Teague FG made=5 không được nêu. | Nhãn sai giá trị/thuộc tính |
| 230 | Gold Kevin Love defensive rebounds=12 không được phát biểu; 12 là tổng rebounds của Thompson, Love có 13 tổng rebounds. FGA=5 của Fournier/Payton không có bằng chứng thống kê; bài nói starting five. | Nghi ngờ nhãn, sai đối tượng |
| 637 | DeRozan turnovers=3 không được phát biểu; `three straight` nói chuỗi trận thua cần tránh. Một số thời gian và chỉ số ném có trong bài nhưng thiếu gold. | Nghi ngờ nhãn, phạm vi thời gian |
| 638 | Perry Jones III minutes=31 không được phát biểu; 31 minutes thuộc Steven Adams. Tổng tỷ số 102–91 trong bài không có cột Total points ở gold. | Sai đối tượng trong nhãn, thiếu dữ kiện |
| 394 | Bài nói Wizards–Magic nhưng có Celtics/Boston giữa bài; `Paul Piece` khác Paul Pierce trong gold. Nhiều ô giá trị 1 và Kyle O'Quinn rebounds=6 không được phát biểu riêng rõ ràng. | Nội dung nguồn không nhất quán, nghi ngờ nhãn/tên |
| 701 | Mo Williams personal fouls=5 không được phát biểu; `all five starters` không phải số lỗi cá nhân. Hornets 16 turnovers xuất hiện nhưng thiếu trong bảng đội. | Nghi ngờ nhãn, thiếu dữ kiện |
| 69 | Các ô gold về thành tích, tỷ số và Spurs turnovers=14 đều có bằng chứng trong văn bản. Không có thống kê cá nhân rõ nên bảng cầu thủ rỗng là phù hợp trong phạm vi rà soát này. | Chưa phát hiện lỗi ở các ô đã đối chiếu |
| 606 | Paul Millsap defensive rebounds=10 không được phát biểu; bài nêu 10 tổng rebounds. Gold đồng thời có total rebounds=10. Các thống kê chính của Schroder, Thomas và tỷ số được nêu rõ. | Nhầm tổng với thành phần trong nhãn |

Các ví dụ cho thấy phải giữ cảnh báo về chất lượng nhãn khi diễn giải F1. Không dùng các ghi chú này để bù điểm cho GLiNER2 hoặc phạt GPT khác đi. Khi có đủ đầu ra bốn phương pháp, rà soát tiếp lỗi schema, thiếu trường do đoạn trích, sai định danh, giá trị và phạm vi thời gian trên cùng 20 ID. Thống kê tự động `missing_field`, `missing_entity`, `missing_or_wrong_value` là nhóm lỗi theo cấu trúc tập hợp, không tự chứng minh nguyên nhân.

Nếu người rà soát quyết định sửa nhãn, phải tạo changelog gồm ID đầy đủ, ô cũ/mới, bằng chứng và lý do; áp dụng cùng bản nhãn cho cả bốn nhánh, xuất điểm phụ riêng. Chưa có sửa nhãn nào được áp dụng ở lần bàn giao này.
