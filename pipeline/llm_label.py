"""BONUS — an LLM inside the pipeline (slide "LLM là một bước transform").

The support team wants an LLM pre-triage label on every live ticket
(gold_ticket_labels), to compare with the human `category` and to triage new
tickets faster. An LLM step is a transform like any other — except it is
expensive, slow and NOT deterministic, so the slide's four rules apply:

  1. key = hash(input) + model + prompt version  -> a re-run makes 0 LLM calls;
     changing the prompt re-labels everything ON PURPOSE
  2. force a structured output, validate it; invalid -> quarantine, never Gold
  3. estimate the cost BEFORE running (rows x tokens x price)
  4. LLM labels are versioned data (model + prompt_version stored on every row)

`label_tickets` caches answers by input hash, model and prompt version, validates
strict JSON labels and quarantines invalid answers. Run `python -m scripts.bonus_llm`
to verify the bonus. Zero-key: `FakeLLM` stands in for a real model.
"""
from __future__ import annotations

import hashlib
import json
import re

import duckdb

MODEL = "fake-llm-2026-09"
PROMPT_VERSION = "triage-v1"
ALLOWED_LABELS = ("bug", "billing", "other")
PRICE_PER_1K_TOKENS_USD = 0.002          # pretend price, for the cost estimate


PROMPT_TEMPLATE = """You triage customer-support tickets.
Answer ONLY with JSON: {{"label": "bug" | "billing" | "other"}}.
Ticket: {text}"""


class FakeLLM:
    """Deterministic stand-in for a chat model. Counts calls and tokens."""

    def __init__(self, model: str = MODEL) -> None:
        self.model = model
        self.calls = 0
        self.tokens = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        self.tokens += len(prompt.split()) + 8
        text = prompt.lower()
        if "xuất" in text:
            return 'Sure! Here is the label: {"label": "export"}'   # off-schema answer
        if re.search(r"crash|lỗi|sso|đăng nhập|chatbot", text):
            return '{"label": "bug"}'
        if re.search(r"tiền|hoá đơn|thanh toán|gói|vat", text):
            return '{"label": "billing"}'
        return '{"label": "other"}'


def estimate_tokens(texts: list[str]) -> int:
    return sum(len(PROMPT_TEMPLATE.format(text=t).split()) + 8 for t in texts)


def parse_label(raw: str) -> str | None:
    """Accept only a JSON object with exactly one allowed label field."""
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(obj, dict) or set(obj) != {"label"}:
        return None
    label = obj["label"]
    return label if isinstance(label, str) and label in ALLOWED_LABELS else None


def live_tickets(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    return con.execute("""
        SELECT ticket_id, subject || '. ' || body AS text
        FROM silver_tickets
        WHERE NOT is_deleted
        ORDER BY ticket_id
    """).fetchall()


def label_tickets(con: duckdb.DuckDBPyConnection, llm: FakeLLM) -> dict:
    """Cache both valid and invalid answers; publish only validated live labels."""
    con.execute("""CREATE TABLE IF NOT EXISTS llm_label_cache (
        input_hash VARCHAR, model VARCHAR, prompt_version VARCHAR,
        raw_output VARCHAR, label VARCHAR,
        PRIMARY KEY (input_hash, model, prompt_version))""")
    con.execute("""CREATE TABLE IF NOT EXISTS llm_label_quarantine (
        ticket_id VARCHAR, input_hash VARCHAR, model VARCHAR, prompt_version VARCHAR,
        raw_output VARCHAR, reason VARCHAR,
        PRIMARY KEY (ticket_id, input_hash, model, prompt_version))""")
    model = llm.model
    tickets = live_tickets(con)
    cached = {
        h: (raw, label) for h, raw, label in con.execute(
            "SELECT input_hash, raw_output, label FROM llm_label_cache "
            "WHERE model = ? AND prompt_version = ?", [model, PROMPT_VERSION]
        ).fetchall()
    }
    inputs = [(ticket_id, text, hashlib.sha256(text.encode("utf-8")).hexdigest())
              for ticket_id, text in tickets]
    pending = {h: text for _, text, h in inputs if h not in cached}
    tokens = estimate_tokens(list(pending.values()))
    print(f"  pending cost estimate before running: {len(pending)} calls, "
          f"~{tokens} tokens = ${tokens / 1000 * PRICE_PER_1K_TOKENS_USD:.4f} "
          "(simulated price; FakeLLM makes no paid API calls)")
    before = llm.calls
    for h, text in pending.items():
        raw = llm.complete(PROMPT_TEMPLATE.format(text=text))
        label = parse_label(raw)
        con.execute("INSERT INTO llm_label_cache VALUES (?, ?, ?, ?, ?)",
                    [h, model, PROMPT_VERSION, raw, label])
        cached[h] = (raw, label)
    rows = []
    quarantined = 0
    for ticket_id, _, h in inputs:
        raw, label = cached[h]
        if label is None:
            con.execute("""INSERT INTO llm_label_quarantine VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT DO NOTHING""",
                        [ticket_id, h, model, PROMPT_VERSION, raw,
                         "Expected JSON object with only label: bug, billing or other"])
            quarantined += 1
        else:
            rows.append((ticket_id, label, model, PROMPT_VERSION))
    con.execute("""CREATE OR REPLACE TABLE gold_ticket_labels (
        ticket_id VARCHAR, label VARCHAR, model VARCHAR, prompt_version VARCHAR)""")
    if rows:
        con.executemany("INSERT INTO gold_ticket_labels VALUES (?, ?, ?, ?)", rows)
    return {"labeled": len(rows), "calls": llm.calls - before,
            "quarantined": quarantined, "estimated_tokens": tokens}
