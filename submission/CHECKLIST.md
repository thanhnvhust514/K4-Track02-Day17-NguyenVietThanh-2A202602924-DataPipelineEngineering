# Checklist trước khi nộp

**Học viên:** Nguyễn Việt Thành / 2A202602924.

## Đã kiểm tra trên máy

- [x] Ba lỗi được sửa trong pipeline; không sửa tests, data, scripts chấm hay checksum.
- [x] Verify 18/18 — ALL PASS.
- [x] Pytest: 34 passed.
- [x] Rerun: fresh build và ba lần chạy lại 2026-08-12 cùng checksum `39e115c510ecdf526800eac227158a4f`.
- [x] `checksums.txt` được sinh bởi script chấm, có PASS.
- [x] Bronze P99=3 ngày; LOOKBACK_DAYS=3, đã ghi REPORT.
- [x] dbt build PASS=19, WARN=0, ERROR=0; parity PARITY cho hai bảng chung.
- [x] REPORT có triệu chứng, nguyên nhân, cách sửa, lựa chọn kỹ thuật, hai câu suy ngẫm và output thực tế.
- [x] B1: BONUS PASS; cache đúng phiên bản, output sai schema vào quarantine, ước lượng chi phí trước gọi.
- [x] Kiểm tra thêm B1: đổi input/model, replay bằng client mới, không gọi lại output lỗi, ticket xóa không vào Gold.
- [x] B2: `bonus/DESIGN.md` trên 600 từ theo đếm khoảng trắng; sáu quyết định có đánh đổi, phương án bị loại và sơ đồ.
- [x] Không có `.env`, private key trong danh sách file Git theo mẫu kiểm tra; venv, DB và logs được ignore. Đây không phải quét secret toàn diện.

## Học viên còn cần hoàn thành

- [ ] Review code và REPORT; giải thích được thay đổi; cá nhân hóa B2 vì bối cảnh và số liệu hiện là giả định thiết kế.
- [x] URL repo bài nộp đã điền theo lựa chọn học viên: https://github.com/thanhnvhust514/K4-Track02-Day17-Data-Pipeline-Engineering.
- [ ] Tên repo hiện tại chưa theo mẫu `K4-Track02-Day17-NguyenVietThanh-2A202602924-DataPipelineEngineering`; học viên đã yêu cầu push lên repo hiện tại.
- [ ] Commit code, REPORT, checksums và bonus. Ghi commit chứa code bài nộp trong REPORT; có thể dùng commit riêng cho phần ghi nhận SHA.
- [ ] Push lên origin đúng URL học viên đã chỉ định ở trên.
- [ ] Mở URL repo ở trạng thái chưa đăng nhập để xác nhận public và các file bằng chứng hiện diện.
- [ ] Nộp URL vào K4 / Track 02 / Day 17 trên LMS; kiểm tra deadline theo lịch lớp/thông báo key coach. Ngày seed không phải deadline.

Không cần commit `.venv/`, `lake/`, DuckDB databases, dbt `target/`, `logs/`. Không cần nộp PR hay PDF. B2 đã chọn brainstorm nên không cần ảnh Airflow.
