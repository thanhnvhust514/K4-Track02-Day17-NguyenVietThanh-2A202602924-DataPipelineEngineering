"""Extra bonus checks: run python -m bonus.check_cache from the repo root."""
import duckdb
from pipeline.llm_label import FakeLLM, label_tickets, parse_label

for raw in ['Sure! {"label":"bug"}', '{"label":"bug","extra":1}',
            '["bug"]', 'null', '{"label":null}', '{"label":["bug"]}',
            '{"label":"export"}']:
    assert parse_label(raw) is None, raw
assert parse_label('{"label":"bug"}') == 'bug'

con = duckdb.connect(':memory:')
con.execute('CREATE TABLE silver_tickets (ticket_id VARCHAR, subject VARCHAR, body VARCHAR, is_deleted BOOLEAN)')
con.execute("INSERT INTO silver_tickets VALUES ('A', 'lỗi', 'crash', false), ('B', 'xuất', 'export', false)")
llm = FakeLLM()
assert label_tickets(con, llm)['calls'] == 2
assert label_tickets(con, FakeLLM())['calls'] == 0
assert con.execute('SELECT count(*) FROM llm_label_quarantine').fetchone()[0] == 1
assert con.execute('SELECT label FROM gold_ticket_labels').fetchall() == [('bug',)]
con.execute("UPDATE silver_tickets SET body='crash changed' WHERE ticket_id='A'")
assert label_tickets(con, llm)['calls'] == 1
assert label_tickets(con, FakeLLM(model='fake-model-v2'))['calls'] == 2
con.execute("UPDATE silver_tickets SET is_deleted=true WHERE ticket_id='A'")
assert label_tickets(con, FakeLLM(model='fake-model-v2'))['calls'] == 0
assert con.execute('SELECT count(*) FROM gold_ticket_labels').fetchone()[0] == 0
con.close()
print('CACHE EDGE CHECKS PASS: strict JSON, invalid response cache, content/model invalidation, deletion, fresh client replay')
