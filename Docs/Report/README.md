# Báo cáo GLiNER2 và hybrid — bản ngày 15/09/2026

Báo cáo có ba phần chính theo yêu cầu:

1. Giới thiệu về tập dữ liệu: động lực xử lý local, sử dụng token dịch vụ LLM, kiểm soát dữ liệu nội bộ và RotoWire.
2. Kiến trúc và cách hoạt động GLiNER2: encoder DeBERTa-v3-base, span, dự đoán số bản ghi, biểu diễn thuộc tính theo bản ghi, giải mã và phương án hybrid tạo schema động.
3. Kết quả thí nghiệm và so sánh: cấu hình cuối của GLiNER2 local và hybrid, cùng hai baseline GPT đã lưu; so sánh riêng điều kiện schema cho trước và schema tự xác định.

Thông tin bìa của bản báo cáo là ThS. Nguyễn Thị Thuỳ Linh và sinh viên Nguyễn Trần Huy (23020378). Không trình bày lịch sử lỗi triển khai, kết quả của adapter lỗi hoặc các bước sửa code. Bản này bổ sung lượt chạy GLiNER2 local trên 200 test tại `outputs/gliner-test-v1`; không chạy lại GPT hoặc hybrid.

Danh mục tài liệu tham khảo của bản PDF chỉ giữ hai bài báo học thuật về Text-to-Table và GLiNER2. Các số liệu nội bộ vẫn được trình bày trong phần thí nghiệm nhưng không được liệt kê như tài liệu tham khảo.

Mã nguồn dự án: <https://github.com/nguyentranhuy999/TextExtractor>.

Cả bốn phương pháp được đối chiếu trên **cùng 200 test**. Cấu hình local được chọn trước trên 30 validation rồi giữ cố định khi chạy test. GLiNER2 local và GPT trong điều kiện oracle nhận cùng tên bảng/trường lấy từ gold của từng bài, không nhận tên hàng hoặc giá trị gold; vì thế hai kết quả này chỉ cô lập bước điền dữ kiện, không phải cấu hình triển khai khi schema chưa biết. Hybrid và GPT trực tiếp phải tự xác định schema. Không diễn giải chênh lệch giữa hai nhóm như tác động riêng của mô hình. Token và tiền chưa được đo định lượng. Hybrid vẫn gửi đoạn trích cho GPT; tính linh hoạt đa miền là thiết kế có thể mở rộng, mới kiểm chứng trên RotoWire.

## Tệp chính

- `main.pdf`: bản PDF hoàn chỉnh.
- `main.tex`: LaTeX chính, dùng ba tệp nội dung trong `sections/`.
- `figures/`: hai biểu đồ kết quả cuối; hai sơ đồ được vẽ trực tiếp bằng TikZ.
- `report_source.zip`: PDF và đủ nguồn để biên dịch, không kèm các phần báo cáo cũ.
- `sources_manifest.json`: băm nguồn số đo và mã GLiNER2 dùng đối chiếu kiến trúc.
- `quality_check.json`: kiểm tra bản PDF cuối.

Báo cáo ngày 14/09 được giữ riêng trong `archive/2026-09-14/`; bản trước khi bổ sung local test nằm ở `archive/2026-09-15-before-local-test/`. Mẫu giảng viên ban đầu vẫn ở `main.template.tex`. Các bản lưu không được đưa vào PDF hoặc gói nguồn mới.

## Biên dịch

Từ thư mục `Docs/Report`, dùng XeLaTeX:

```bash
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

Trên Overleaf, tải gói nguồn, đặt `main.tex` làm main document và chọn XeLaTeX. Nguồn ưu tiên Times New Roman, Arial, Courier New; có các font dự phòng. Giữ tệp `uet.png`, `sections/` và `figures/` cùng tệp chính.

Các hình và bảng đã tạo sẵn, không cần chạy Python để biên dịch PDF. Nếu muốn dựng lại chúng từ repository đầy đủ, chạy tại thư mục gốc:

```bash
MPLCONFIGDIR=/private/tmp/rotowire-mpl .venv/bin/python Docs/Report/build_assets.py
```

Script chỉ đọc log và cấu hình/mã thư viện cục bộ, không gọi mô hình.
