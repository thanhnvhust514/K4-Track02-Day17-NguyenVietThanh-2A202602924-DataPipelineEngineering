# K4-Track02-Day17 — Report cá nhân

Phần phân tích tối đa một trang, không tính output ở phần 5.
Định dạng tham chiếu và phạm vi tính trang: [SUBMISSION.md](../docs/SUBMISSION.md).

**Họ tên / MSSV:** Nguyễn Việt Thành / 2A202602924
**Repo bài nộp (theo lựa chọn học viên):** https://github.com/thanhnvhust514/K4-Track02-Day17-Data-Pipeline-Engineering
**Tên repo theo đề:** K4-Track02-Day17-NguyenVietThanh-2A202602924-DataPipelineEngineering; repo hiện tại chưa đổi tên.
**Commit chứa code và bằng chứng bài nộp:** `9209b744042e13a280a8771f0001aad2a0c3467b`; commit tài liệu tiếp theo chỉ bổ sung SHA và trạng thái checklist.
**AI đã dùng và phạm vi hỗ trợ (hoặc không dùng):** Codex đọc đề, sửa ba lỗi, làm cache/schema gate B1, chạy kiểm tra, hỗ trợ REPORT và soạn thiết kế đề xuất B2. Học viên cần review, cá nhân hóa thiết kế và giải thích được thay đổi.
**Nguồn tham khảo khác (nếu có):** Tài liệu trong repo đề bài.

## 1. Ba lỗi

| | Lỗi Silver | Lỗi late data | Lỗi xoá (CDC) |
|---|---|---|---|
| **Triệu chứng** | 24 hàng/12 ticket; T-91 có cả trạng thái cũ và mới; chunks bị trùng. | u05 ngày 08-12 chỉ có (2 events, 1 click, 0 down), cần (5, 3, 1); feature lệch full recompute. | T-97 còn thông tin cá nhân ở Silver, snapshot mới nhất và RAG. |
| **Nguyên nhân gốc** | Dedup trong batch nhưng INSERT nối thêm giữa các batch. | LOOKBACK_DAYS=0 bỏ qua partition ngày xảy ra của event đến muộn. | Staging chỉ lấy khóa từ after; delete có after=null nên bị lọc mất. |
| **Cách sửa** (file, vài dòng) | silver.py: MERGE theo ticket_id; update chỉ khi LSN nguồn lớn hơn đích. | config.py: LOOKBACK_DAYS=3 từ ceil(P99) đo ở Bronze. | staging.py: coalesce khóa từ after, key, before; giữ LSN và op; các trường after null trở thành tombstone. |
| **Khái niệm trên slide** | Silver có khóa, idempotency, LSN guard. | Event time, lateness, lookback, overwrite-partition. | CDC delete khác Kafka tombstone; xóa phải lan xuống Gold. |

## 2. Các con số

- P99 lateness đo từ 43 bản ghi Bronze: `3.00` ngày → `LOOKBACK_DAYS = 3` (P50=0, P95=2.90, max=3).
- `submission/checksums.txt`: PASS — Gold checksum: `39e115c510ecdf526800eac227158a4f`; C0=C1=C2=C3.
- dbt build: PASS=19, ERROR=0. Parity: PARITY cho silver_tickets và gold_feature_daily.

## 3. Lựa chọn công cụ / kỹ thuật (mỗi dòng một câu "vì sao")

- MERGE cập nhật thực thể theo khóa; overwrite-partition tính lại aggregate từ Silver để tránh cộng trùng khi replay và nhận late events.
- Tombstone giữ khóa và LSN xóa để batch cũ không hồi sinh ticket; đổi lại phải giữ một hàng trạng thái xóa.
- Snapshot từ Bronze as-of và feedback đã đến tại ngày đó giúp tái lập, tránh dùng tương lai; version cũ bất biến.
- DuckDB xử lý seed nhỏ tại máy, không cần cluster; dbt biểu diễn SQL, contract và test rõ ràng. Spark có chi phí vận hành không cần thiết ở quy mô lab.

## 4. Hai câu hỏi suy ngẫm

**Snapshot cũ và quyền xóa:** Lab giữ snapshot cũ để tái lập. Production cần erasure có audit: chặn ticket ở serving, truy vết snapshot/cache/bản sao, thu hồi version và tạo bản sạch; xóa hoặc crypto-shred dữ liệu cũ theo chính sách. Ghi manifest/checksum mới, không coi version cũ vẫn nguyên vẹn.

**Tên người còn sót:** Đặt gate PII ở Bronze→Silver, kết hợp regex và NER; kiểm lại training/chunks trước khi xuất Gold. Đo precision/recall và tỷ lệ PII sót trên tập gán nhãn, ưu tiên recall; cách ly mẫu nghi ngờ, kiểm tra false negatives. Bronze raw cần giới hạn truy cập và retention.

## 5. Output (thực tế, Windows PowerShell)

Môi trường: Python 3.12.6, DuckDB 1.5.6, dbt-core 1.12.5, dbt-duckdb 1.11.0. Lệnh Python chạy từ gốc repo. Trước dbt build, chạy `main.py --land-only`, đặt `$env:DO_NOT_TRACK = '1'` rồi `Push-Location dbt_project`; sau build dùng `Pop-Location` để chạy parity. Output giữ nguyên, kể cả khoảng trắng của dbt.

```text
$ .\.venv\Scripts\python.exe -m scripts.verify
=== verify.py — Day 17 pipeline contracts ===
  [OK ] Bronze  every daily batch landed as Parquet (7 days x 3 sources)
  [OK ] Bronze  re-landing a batch is a no-op (append-only, no duplicate file)
  [OK ] Bronze  Bronze keeps the raw truth: Kafka tombstone + redelivered events are still there
  [OK ] Silver  silver_tickets has exactly one row per ticket_id
  [OK ] Silver  T-91 shows its latest state: high / closed / bug
  [OK ] Silver  deleted ticket T-97 is a tombstone: is_deleted and no personal data left
  [OK ] Silver  no email / phone number survives past Bronze
  [OK ] Silver  silver_events has one row per event_id (Kafka redeliveries removed)
  [OK ] Silver  2 malformed events quarantined with a reason; the run did not halt
  [OK ] Gold    gold_feature_daily reconciles with a full recompute from Silver
  [OK ] Gold    u05's offline events of 08-12 (arrived 08-15) are counted on 08-12
  [OK ] Gold    LOOKBACK_DAYS covers measured P99 lateness (p99=3.00 days)
  [OK ] Gold    training set uses point-in-time priority (T-91 created as 'low')
  [OK ] Gold    late feedback creates a NEW snapshot version; the old one is untouched
  [OK ] Gold    latest training snapshot excludes the deleted ticket T-97
  [OK ] Gold    deletes propagate to the RAG index: no chunk of T-97
  [OK ] Gold    gold_doc_chunks: one row per chunk, and a re-run embeds 0 new chunks
  [OK ] Rerun   re-run 2026-08-12 three times -> Gold checksum identical to a fresh build

RESULT: 18/18 checks — ALL PASS
re-run checksums written to submission/checksums.txt
```

```text
$ .\.venv\Scripts\python.exe -m pytest
..................................                                       [100%]
34 passed in 2.53s
```

```text
$ .\.venv\Scripts\python.exe -m scripts.rerun_check
# Lab 17 — re-run check for 2026-08-12

run                     gold_feature_daily    gold_training_set     gold_doc_chunks       gold (combined)
fresh build             8630e04a61d1          9370ca77af23          cb9ebd12fdcc          39e115c510ecdf526800eac227158a4f
re-run #1 of 2026-08-12 8630e04a61d1          9370ca77af23          cb9ebd12fdcc          39e115c510ecdf526800eac227158a4f
re-run #2 of 2026-08-12 8630e04a61d1          9370ca77af23          cb9ebd12fdcc          39e115c510ecdf526800eac227158a4f
re-run #3 of 2026-08-12 8630e04a61d1          9370ca77af23          cb9ebd12fdcc          39e115c510ecdf526800eac227158a4f

RESULT: PASS — 3 re-runs, identical checksums
```

```text
$ .\.venv\Scripts\python.exe main.py --lateness
event lateness over 43 Bronze records (calendar days): p50=0.00 p95=2.90 p99=3.00 max=3
-> lookback must be >= ceil(p99) = 3 day(s); config.LOOKBACK_DAYS = 3
```

```text
$ ..\.venv\Scripts\dbt.exe build --profiles-dir . --event-time-start 2026-08-10 --event-time-end 2026-08-17 --no-use-colors
07:23:52  Running with dbt=1.12.5
07:23:52  Registered adapter: duckdb=1.11.0
07:23:53  Found 5 models, 13 data tests, 2 sources, 502 macros, 1 unit test
07:23:53  
07:23:53  Concurrency: 1 threads (target='dev')
07:23:53  
07:23:53  1 of 19 START sql view model main.stg_events ................................... [RUN]
07:23:53  1 of 19 OK created sql view model main.stg_events .............................. [OK in 0.07s]
07:23:53  2 of 19 START sql view model main.stg_ticket_changes ........................... [RUN]
07:23:53  2 of 19 OK created sql view model main.stg_ticket_changes ...................... [OK in 0.03s]
07:23:53  3 of 19 START sql incremental model main.silver_events ......................... [RUN]
07:23:53  3 of 19 OK created sql incremental model main.silver_events .................... [OK in 0.11s]
07:23:53  4 of 19 START unit_test silver_tickets::silver_tickets_latest_change_wins_and_delete_is_tombstone  [RUN]
07:23:53  4 of 19 PASS silver_tickets::silver_tickets_latest_change_wins_and_delete_is_tombstone  [PASS in 0.10s]
07:23:53  8 of 19 START sql incremental model main.silver_tickets ........................ [RUN]
07:23:53  8 of 19 OK created sql incremental model main.silver_tickets ................... [OK in 0.12s]
07:23:53  5 of 19 START test not_null_silver_events_event_id ............................. [RUN]
07:23:53  5 of 19 PASS not_null_silver_events_event_id ................................... [PASS in 0.04s]
07:23:53  6 of 19 START test not_null_silver_events_user_id .............................. [RUN]
07:23:53  6 of 19 PASS not_null_silver_events_user_id .................................... [PASS in 0.01s]
07:23:53  7 of 19 START test unique_silver_events_event_id ............................... [RUN]
07:23:53  7 of 19 PASS unique_silver_events_event_id ..................................... [PASS in 0.02s]
07:23:53  9 of 19 START test accepted_values_silver_tickets_category__bug__billing__other  [RUN]
07:23:53  9 of 19 PASS accepted_values_silver_tickets_category__bug__billing__other ...... [PASS in 0.03s]
07:23:53  10 of 19 START test accepted_values_silver_tickets_priority__low__medium__high . [RUN]
07:23:54  10 of 19 PASS accepted_values_silver_tickets_priority__low__medium__high ....... [PASS in 0.02s]
07:23:54  11 of 19 START test accepted_values_silver_tickets_status__open__pending__closed  [RUN]
07:23:54  11 of 19 PASS accepted_values_silver_tickets_status__open__pending__closed ..... [PASS in 0.02s]
07:23:54  12 of 19 START test not_null_silver_tickets__lsn ............................... [RUN]
07:23:54  12 of 19 PASS not_null_silver_tickets__lsn ..................................... [PASS in 0.01s]
07:23:54  13 of 19 START test not_null_silver_tickets_is_deleted ......................... [RUN]
07:23:54  13 of 19 PASS not_null_silver_tickets_is_deleted ............................... [PASS in 0.01s]
07:23:54  14 of 19 START test not_null_silver_tickets_ticket_id .......................... [RUN]
07:23:54  14 of 19 PASS not_null_silver_tickets_ticket_id ................................ [PASS in 0.02s]
07:23:54  15 of 19 START test unique_silver_tickets_ticket_id ............................ [RUN]
07:23:54  15 of 19 PASS unique_silver_tickets_ticket_id .................................. [PASS in 0.01s]
07:23:54  16 of 19 START sql microbatch model main.gold_feature_daily .................... [RUN]
07:23:54  Batch 1 of 7 START batch 2026-08-10 of main.gold_feature_daily ....................... [RUN]
07:23:54  Batch 1 of 7 OK created batch 2026-08-10 of main.gold_feature_daily .................. [OK in 0.03s]
07:23:54  Batch 2 of 7 START batch 2026-08-11 of main.gold_feature_daily ....................... [RUN]
07:23:54  Batch 2 of 7 OK created batch 2026-08-11 of main.gold_feature_daily .................. [OK in 0.03s]
07:23:54  Batch 3 of 7 START batch 2026-08-12 of main.gold_feature_daily ....................... [RUN]
07:23:54  Batch 3 of 7 OK created batch 2026-08-12 of main.gold_feature_daily .................. [OK in 0.03s]
07:23:54  Batch 4 of 7 START batch 2026-08-13 of main.gold_feature_daily ....................... [RUN]
07:23:54  Batch 4 of 7 OK created batch 2026-08-13 of main.gold_feature_daily .................. [OK in 0.02s]
07:23:54  Batch 5 of 7 START batch 2026-08-14 of main.gold_feature_daily ....................... [RUN]
07:23:54  Batch 5 of 7 OK created batch 2026-08-14 of main.gold_feature_daily .................. [OK in 0.02s]
07:23:54  Batch 6 of 7 START batch 2026-08-15 of main.gold_feature_daily ....................... [RUN]
07:23:54  Batch 6 of 7 OK created batch 2026-08-15 of main.gold_feature_daily .................. [OK in 0.02s]
07:23:54  Batch 7 of 7 START batch 2026-08-16 of main.gold_feature_daily ....................... [RUN]
07:23:54  Batch 7 of 7 OK created batch 2026-08-16 of main.gold_feature_daily .................. [OK in 0.02s]
07:23:54  16 of 19 OK created sql microbatch model main.gold_feature_daily ............... [SUCCESS in 0.20s]
07:23:54  17 of 19 START test dbt_utils_free_unique_combination_gold_feature_daily_user_id__event_date  [RUN]
07:23:54  17 of 19 PASS dbt_utils_free_unique_combination_gold_feature_daily_user_id__event_date  [PASS in 0.03s]
07:23:54  18 of 19 START test not_null_gold_feature_daily_event_date ..................... [RUN]
07:23:54  18 of 19 PASS not_null_gold_feature_daily_event_date ........................... [PASS in 0.02s]
07:23:54  19 of 19 START test not_null_gold_feature_daily_user_id ........................ [RUN]
07:23:54  19 of 19 PASS not_null_gold_feature_daily_user_id .............................. [PASS in 0.01s]
07:23:54  
07:23:54  Finished running 3 incremental models, 13 data tests, 1 unit test, 2 view models in 0 hours 0 minutes and 1.05 seconds (1.05s).
07:23:54  
07:23:54  Completed successfully
07:23:54  
07:23:54  Done. PASS=19 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=19
```

```text
$ .\.venv\Scripts\python.exe -m scripts.parity
=== parity: lite pipeline vs dbt ===
  [OK ] silver_tickets       lite 3c15dfd43701  dbt 3c15dfd43701
  [OK ] gold_feature_daily   lite 8630e04a61d1  dbt 8630e04a61d1
RESULT: PARITY — both implementations agree
```

## 6. Bonus

**B1:** Cache SHA256(input) + model + prompt version; cả output lỗi được cache để replay không gọi lại. JSON phải đúng schema, output sai đưa vào quarantine; Gold chỉ chứa label hợp lệ. Ước lượng chi phí cache miss trước khi gọi; giá giả lập, không phát sinh phí API.

```text
$ .\.venv\Scripts\python.exe -m scripts.bonus_llm
=== bonus: LLM labelling of 11 live tickets ===
  cost estimate before running: ~484 tokens = $0.0010 per full run
  pending cost estimate before running: 11 calls, ~484 tokens = $0.0010 (simulated price; FakeLLM makes no paid API calls)
  pending cost estimate before running: 0 calls, ~0 tokens = $0.0000 (simulated price; FakeLLM makes no paid API calls)
  pending cost estimate before running: 11 calls, ~484 tokens = $0.0010 (simulated price; FakeLLM makes no paid API calls)
  [OK ] first run labels every live ticket
  [OK ] re-run with same model + prompt makes 0 LLM calls
  [OK ] every Gold label is bug / billing / other
  [OK ] off-schema answers go to llm_label_quarantine
  [OK ] new prompt version re-labels on purpose
  [OK ] labels carry their prompt version
BONUS PASS
```

```text
$ .\.venv\Scripts\python.exe -m bonus.check_cache
  pending cost estimate before running: 2 calls, ~50 tokens = $0.0001 (simulated price; FakeLLM makes no paid API calls)
  pending cost estimate before running: 0 calls, ~0 tokens = $0.0000 (simulated price; FakeLLM makes no paid API calls)
  pending cost estimate before running: 1 calls, ~26 tokens = $0.0001 (simulated price; FakeLLM makes no paid API calls)
  pending cost estimate before running: 2 calls, ~51 tokens = $0.0001 (simulated price; FakeLLM makes no paid API calls)
  pending cost estimate before running: 0 calls, ~0 tokens = $0.0000 (simulated price; FakeLLM makes no paid API calls)
CACHE EDGE CHECKS PASS: strict JSON, invalid response cache, content/model invalidation, deletion, fresh client replay
```

**B2:** [Thiết kế pipeline CSKH tiếng Việt](../bonus/DESIGN.md), gồm sáu quyết định có đánh đổi, phương án bị loại và sơ đồ. Đây là thiết kế đề xuất dựa trên giả định, không phải kết quả production; học viên cần review và cá nhân hóa trước khi nộp.
