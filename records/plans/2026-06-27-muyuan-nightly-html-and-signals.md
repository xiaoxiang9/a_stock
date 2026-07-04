# Muyuan Nightly HTML Mail and Signal Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the Muyuan nightly report with public signal inputs and deliver it as readable HTML email.

**Architecture:** Keep `jobs/muyuan_nightly.py` as the single orchestration entrypoint. Extend it with small parsing/rendering helpers for official/public signal retrieval, markdown report enrichment, and multipart HTML email generation, then verify through focused unit tests and a live send.

**Tech Stack:** Python 3.14, unittest, Tushare, Eastmoney mx-data/mx-search skills, msmtp, launchd.

## Global Constraints

- Primary investment data source remains Tushare; Eastmoney is only secondary validation.
- Public webpage supplementation should prefer official/authoritative pages over generic financial portals.
- Email output must be readable without Markdown rendering support.
- Keep nightly automation compatible with the existing launchd job and msmtp account.

---

### Task 1: Add failing tests for HTML email and signal enrichment helpers

**Files:**
- Modify: `tests/test_muyuan_nightly.py`
- Test: `tests/test_muyuan_nightly.py`

**Interfaces:**
- Consumes: existing `render_report_markdown()`, `build_email_subject()`
- Produces: `render_email_html(...) -> str`, `build_email_message(...) -> str`, `summarize_mx_search_output(...) -> list[str]`

- [ ] Write failing tests covering HTML body structure, MIME message generation, and mx-search output summarization.
- [ ] Run `python3 -m unittest tests.test_muyuan_nightly` and verify the new tests fail for missing functions/behavior.
- [ ] Implement the minimal helpers in `jobs/muyuan_nightly.py`.
- [ ] Re-run `python3 -m unittest tests.test_muyuan_nightly` until green.

### Task 2: Enrich the nightly job with announcement and cycle signal retrieval

**Files:**
- Modify: `jobs/muyuan_nightly.py`
- Modify: `review/daily/README.md`
- Test: `tests/test_muyuan_nightly.py`

**Interfaces:**
- Consumes: `summarize_mx_search_output(raw: str, limit: int) -> list[str]`
- Produces: enriched report sections for announcement headlines, monthly sales brief, hog-price signal, sow-inventory signal

- [ ] Add failing tests for report sections that consume external signal summaries.
- [ ] Run `python3 -m unittest tests.test_muyuan_nightly` and confirm failure matches the missing report content.
- [ ] Implement mx-search based retrieval and graceful fallback text when some public signals are unavailable.
- [ ] Re-run `python3 -m unittest tests.test_muyuan_nightly` and confirm pass.

### Task 3: Switch outbound mail from plain text to multipart HTML

**Files:**
- Modify: `jobs/muyuan_nightly.py`
- Modify: `jobs/README.md`
- Test: `tests/test_muyuan_nightly.py`

**Interfaces:**
- Consumes: `render_report_markdown(...)`, `render_email_html(...)`
- Produces: `send_email(recipient: str, subject: str, text_body: str, html_body: str) -> None`

- [ ] Add failing tests asserting MIME boundaries and HTML content-type.
- [ ] Run `python3 -m unittest tests.test_muyuan_nightly` and verify failure.
- [ ] Implement multipart/alternative email assembly and wire it into `send_email`.
- [ ] Re-run `python3 -m unittest tests.test_muyuan_nightly` and verify pass.

### Task 4: Live verification and docs update

**Files:**
- Modify: `jobs/README.md`
- Modify: `.learnings/LEARNINGS.md`

**Interfaces:**
- Consumes: updated `jobs/muyuan_nightly.py`
- Produces: live-generated report, sent verification email, updated operational docs

- [ ] Run `python3 -m py_compile jobs/muyuan_nightly.py`.
- [ ] Run `python3 -m unittest tests.test_muyuan_nightly`.
- [ ] Run the nightly job with `--force --send-email --recipient 376597874@qq.com` and confirm success.
- [ ] Update docs/learnings with any non-obvious runtime findings.
