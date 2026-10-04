# B2 — Brainstorm pipeline cho trợ lý chăm sóc khách hàng tiếng Việt

**Học viên:** Nguyễn Việt Thành — 2A202602924.

Đây là thiết kế đề xuất, chưa triển khai production. Các con số bên dưới là giả định để đặt ràng buộc, không phải số đo của một doanh nghiệp. Bài toán được chọn để mở rộng tình huống CSKH trong lab; học viên cần review và điều chỉnh theo trải nghiệm cá nhân trước khi nộp.

## Bài toán và ràng buộc

Một cửa hàng thương mại điện tử muốn trợ lý trả lời câu hỏi về giao hàng, đổi trả và thanh toán. Nhân viên cần câu trả lời có nguồn, có phiên bản chính sách và có thể chuyển cho người thật khi thiếu căn cứ. Dữ liệu gồm ticket từ cơ sở dữ liệu, transcript chat, PDF chính sách, trạng thái đơn hàng và feedback. Giả định ban đầu có 20.000 ticket/ngày, 100 tài liệu thay đổi/ngày, nhóm vận hành hai người và ngân sách pipeline 5 triệu đồng/tháng, chưa tính chi phí trả lời của chatbot. Không coi con số này là báo giá dịch vụ.

Khó khăn nằm ở PDF scan, Unicode tiếng Việt, chat thiếu dấu, mã đơn hàng trong nội dung tự do, ticket cập nhật nhiều lần và sự kiện đến muộn khi mạng gián đoạn. Mục tiêu thiết kế là cập nhật ticket trong 15 phút, chính sách trong một giờ và tập huấn luyện hằng đêm. Tra cứu trạng thái đơn hàng cần gọi hệ thống giao dịch tại thời điểm trả lời, vì dữ liệu cũ có thể khiến khách nhận thông tin sai. Những mục tiêu này phải được đo lại bằng prototype trước khi cam kết.

## Sơ đồ kiến trúc

```text
CDC ticket ────────┐
Transcript/chat ───┼─> Bronze raw + manifest + hash
PDF chính sách ────┘           |
                       Parse/OCR + schema gate
                              |
                   Silver: dedup, LSN, PII, versions
                     /            |             \
        Gold chunks/index   Snapshot train   Daily features
                  |               ^
       RAG + trích nguồn          |
                  |        Trace đã che PII
             Nhân viên <── Feedback ──> Eval holdout/DPO sạch

Erasure registry + lineage áp dụng cho mọi nhánh dữ liệu
Tra cứu đơn hàng trực tiếp qua API giao dịch khi phục vụ
```

## 1. Batch hay streaming: độ tươi nào đủ?

**Quyết định:** dùng microbatch 15 phút cho CDC và transcript; tài liệu chạy theo lịch một giờ, training hằng đêm. Streaming liên tục giảm độ trễ nhưng tăng gánh nặng vận hành, xử lý checkpoint và truy vết lỗi. Microbatch có độ trễ lớn hơn nhưng đủ cho triage và cập nhật kho tri thức trong giả định này. Không dùng dữ liệu batch để trả lời trạng thái đơn hàng cần tức thời.

Tôi sẽ đo từ thời điểm thay đổi ở nguồn đến lúc bản mới xuất hiện ở serving, thay vì chỉ đo thời gian job. Nếu P95 vượt mục tiêu trong nhiều chu kỳ, kiểm tra queue và công suất trước khi chuyển sang streaming. Ở quy mô 10 lần, bottleneck đầu tiên có thể là OCR và embedding; dùng hàng đợi, giới hạn đồng thời và ưu tiên chính sách thay đổi. Không tăng tần suất mọi nguồn chỉ vì một nguồn cần độ tươi cao.

## 2. Hợp đồng dữ liệu và PII: chặn lỗi ở đâu?

**Quyết định:** Bronze giữ raw có giới hạn truy cập và retention; Silver chỉ nhận bản ghi qua schema gate, chuẩn hóa Unicode và PII gate. Ticket phải có khóa, thứ tự CDC và thời điểm hợp lệ. PDF cần mã tài liệu, phiên bản, ngày hiệu lực, trang và độ tin cậy OCR. Email, điện thoại và mã định danh được che; tên người cần detector bổ sung, không chỉ regex.

Chặn quá mạnh làm mất dữ liệu hữu ích; chặn yếu làm lộ thông tin và giảm chất lượng model. Tôi ưu tiên cách ly mẫu nghi ngờ, giữ lý do và source hash để xử lý lại sau khi sửa parser. Giả định cảnh báo quarantine trên 2% trong một giờ gửi đến người phụ trách dữ liệu; ngưỡng cần hiệu chỉnh theo baseline. Đo precision/recall trên tập tiếng Việt gán nhãn, theo dõi PII còn sót và sai OCR theo loại tài liệu. Log và trace cũng phải qua gate, tránh việc nội dung đã che trong Gold nhưng vẫn lộ ở log.

## 3. RAG hay knowledge graph: câu hỏi cần dạng truy hồi nào?

**Quyết định:** bắt đầu bằng RAG kết hợp tìm kiếm từ khóa và vector, lưu metadata phiên bản và ngày hiệu lực. Mã sản phẩm và mã đơn hàng cần exact match, còn cách diễn đạt thiếu dấu cần tìm kiếm linh hoạt. Chunk theo mục chính sách, lưu trang và nguồn để người dùng kiểm tra. Một đoạn liên quan không đồng nghĩa chính sách vẫn còn hiệu lực, nên serving phải lọc theo thời điểm và cửa hàng.

Knowledge graph hỗ trợ truy vấn nhiều quan hệ nhưng đòi hỏi ontology, entity resolution và cơ chế cập nhật quan hệ. Với câu hỏi chủ yếu về đổi trả hoặc phí giao hàng, chi phí đó chưa có bằng chứng sẽ cải thiện chất lượng. Chỉ thử graph khi eval có nhiều câu cần kết nối sản phẩm, phụ kiện và khu vực mà RAG liên tục thất bại. So sánh bằng tỷ lệ câu có nguồn đúng, tỷ lệ không trả lời khi thiếu căn cứ và độ trễ, không chỉ điểm tương đồng embedding.

## 4. Train/serve parity và flywheel: tránh học từ tương lai thế nào?

**Quyết định:** training snapshot dùng trạng thái ticket và chính sách đã biết tại thời điểm cần dự đoán. Lưu cả event time và thời điểm nhận; dùng as-of join để không đưa nhãn đóng ticket hoặc feedback tương lai vào feature lúc tạo ticket. Train và serve dùng chung định nghĩa feature có version; theo dõi phân phối đầu vào để phát hiện lệch.

Trace và feedback được dùng tạo eval holdout trước, sau đó mới tạo cặp DPO từ phần còn lại. Dedup và decontamination theo hash, rồi kiểm tra tương đồng để bắt prompt được viết lại. Phân tách theo cuộc hội thoại, tài liệu và thời gian giảm nguy cơ cùng một nội dung xuất hiện ở cả train và eval. Đánh đổi là ít dữ liệu train hơn, nhưng kết quả đánh giá đáng tin hơn. Không coi mọi câu có lượt thích là nhãn đúng: cần mẫu review của nhân viên và kiểm tra nguồn, vì khách có thể thích câu trả lời sai nhưng nghe thuyết phục.

## 5. Replay, backfill và xóa: trạng thái nào được phép thay đổi?

**Quyết định:** Bronze định danh batch và content hash; Silver MERGE theo khóa với LSN guard; Gold tính lại partition trong lookback đo từ lateness. Cache transform dùng hash input, model và prompt version, kể cả kết quả bị quarantine, để rerun không gọi model lặp lại. Backfill dùng cùng code path, ghi vào staging rồi đối chiếu checksum trước khi thay serving.

Tombstone giữ thứ tự xóa để replay bản cũ không hồi sinh ticket. Snapshot bất biến giúp tái lập nhưng không đủ để bảo đảm erasure: cần registry yêu cầu xóa, lineage đến snapshot, index, cache và bản sao. Quy trình thu hồi version chứa dữ liệu cần xóa, tạo bản sạch và ghi audit. Side-effect như gửi email hay refund tách khỏi replay bằng outbox và idempotency key; việc tái tạo dữ liệu không được tự phát sinh giao dịch. Đánh đổi là nhiều metadata và quy trình hơn, đổi lại có khả năng giải thích trạng thái và sửa sai có kiểm soát.

## 6. Chi phí và vận hành: giảm ở đâu trước?

**Quyết định:** đo số trang OCR, token, số cache miss, kích thước lưu trữ và thời gian job trước khi tối ưu. Dự toán một đợt gán nhãn bằng số input chưa cache nhân token ước lượng và đơn giá giả định; giá thật cần lấy tại thời điểm triển khai. Nội dung không đổi không OCR/embedding lại; gộp small files định kỳ. Lưu metrics riêng cho mỗi model và prompt version để thấy chi phí thay phiên bản.

Ở 100 lần dữ liệu, một máy có thể không đáp ứng cửa sổ microbatch; cần benchmark và chia worker OCR/embedding trước, rồi mới cân nhắc compute phân tán cho SQL. Giảm chi phí bằng cache và giới hạn tài liệu cần xử lý trước khi giảm gate PII hoặc bỏ kiểm tra chất lượng. Tiếng Việt có dấu và chat thiếu dấu cần tập eval riêng; giữ văn bản Unicode chuẩn, không loại dấu trong bản nội dung gốc dùng trích dẫn.

## Phương án bị loại và bước kiểm chứng

Tôi loại phương án gửi toàn bộ transcript raw đến LLM mỗi lần chạy để tạo lại nhãn và index: tốn token, lặp side-effect, không kiểm soát PII và không tái lập được kết quả khi model thay đổi. Tôi cũng chưa chọn streaming toàn hệ thống hay graph toàn bộ vì chưa có yêu cầu độ tươi hoặc bộ câu hỏi chứng minh lợi ích.

Bước kiểm chứng đầu tiên là dùng dữ liệu giả lập có ticket bị xóa, cập nhật bị giao lại, event trễ và PDF lỗi. Chạy cùng batch ba lần, so checksum, số lần gọi model và quarantine; kiểm tra as-of feature bằng những ví dụ có thay đổi sau thời điểm dự đoán. Sau đó dựng eval tiếng Việt có nguồn và phiên bản chính sách, đo lỗi trước khi triển khai. Các quyết định sẽ được điều chỉnh theo số đo; thiết kế này không tự khẳng định đã đạt SLA hay ngân sách.
