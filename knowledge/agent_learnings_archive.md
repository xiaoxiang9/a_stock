# Learnings

## [LRN-20260627-001] best_practice

**Logged**: 2026-06-27T15:05:00+08:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
Third-party skills packaged for OpenClaw may hardcode `/root/.openclaw/...` paths and assume system Python dependencies that are missing on this machine.

### Details
Installing Eastmoney Miaoxiang skills exposed two recurring portability issues: the shipped Python scripts defaulted output paths to `/root/.openclaw/workspace/mx_data/output`, which fails on this macOS setup, and Homebrew Python blocked direct `pip --user` installs under PEP 668. The stable setup was: install a dedicated venv at `/Users/bytedance/.miaoxiang-venv`, prepend that venv to `PATH` in `~/.bash_profile`, persist `MX_APIKEY` there, and patch default output directories to `Path.home() / ".openclaw/workspace/mx_data/output"` before deploying the skills.

### Suggested Action
When installing future vendor skills, inspect for hardcoded root paths and Python dependencies before claiming success; prefer a dedicated venv plus user-home-relative output paths over mutating system Python.

### Metadata
- Source: error
- Related Files: .miaoxiang_extract/mx-data/mx_data.py, .miaoxiang_extract/mx-search/mx_search.py, .miaoxiang_extract/mx-xuangu/mx_xuangu.py, .miaoxiang_extract/mx-zixuan/mx_zixuan.py, .miaoxiang_extract/mx-moni/mx_moni.py, .miaoxiang_extract/mx-poster/mx_poster.py
- Tags: skills, python, portability, miaoxiang
- Pattern-Key: harden.third_party_skill_install

---

## [LRN-20260627-002] best_practice

**Logged**: 2026-06-27T15:45:00+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
This project uses a fixed source-priority and validation standard for investment data, with `tushare` first and Eastmoney second.

### Details
The user established a strict rule for all future research work in this project: use `tushare` as the primary data source, use Eastmoney skills as the secondary validation source, and only if both fail, fall back first to official websites, exchange announcements, and other authoritative public webpages, then to established financial portals such as Tonghuashun, Sina Finance, and Yahoo Finance. Unknown channels should be avoided where stronger sources exist. Key datapoints must always be labeled with their sources, and source discrepancies must be surfaced rather than silently merged.

### Suggested Action
Follow this source-order and source-labeling standard for all subsequent stock-investment research tasks in this repository.

### Metadata
- Source: conversation
- Related Files: AGENTS.md
- Tags: data-quality, source-validation, tushare, eastmoney, research
- Pattern-Key: harden.investment_data_source_priority
- Promoted: AGENTS.md

---

## [LRN-20260627-003] best_practice

**Logged**: 2026-06-27T21:15:00+08:00
**Priority**: medium
**Status**: pending
**Area**: automation

### Summary
On macOS, a venv Python path may resolve to the same system interpreter path, so runtime switching logic should compare the invoked path string, not `Path.resolve()`.

### Details
The nightly mail job initially tried to detect whether it needed to re-exec into `/Users/bytedance/.miaoxiang-venv/bin/python` by comparing `Path(sys.executable).resolve()` with the preferred runtime path. On this machine, the venv Python is a symlink to the Homebrew framework interpreter, so both resolved paths matched and the guard falsely concluded it was already running inside the correct environment. That caused `ModuleNotFoundError: tushare` when the job was started with system `python3`. Comparing `os.path.abspath(sys.executable)` with the preferred path string preserved the venv distinction and fixed the issue.

### Suggested Action
For future macOS automation that depends on a specific venv, compare the invoked executable path directly before re-execing; do not rely on `resolve()` when the venv may symlink to a shared interpreter binary.

### Metadata
- Source: error
- Related Files: jobs/muyuan_nightly.py
- Tags: macos, python, venv, launchd, automation
- Pattern-Key: guard.venv_runtime_path_compare

---

## [LRN-20260627-004] best_practice

**Logged**: 2026-06-27T21:40:00+08:00
**Priority**: medium
**Status**: pending
**Area**: email

### Summary
For investment nightlies, raw Markdown is not an acceptable end-user email format; use multipart email with HTML正文 and plain-text fallback.

### Details
The first nightly email sent the Markdown report as `text/plain`, which left headings, tables, and lists unreadable in the mailbox. The improved pattern is to keep the report markdown as the internal canonical artifact, then derive a readable HTML email body with key metric cards and the full report body, and send it as `multipart/alternative` so HTML-capable clients render well while plain-text clients still have a fallback.

### Suggested Action
Keep markdown as the source artifact for repo history, but treat HTML mail rendering as a separate presentation layer for all future scheduled outbound reports.

### Metadata
- Source: conversation
- Related Files: jobs/muyuan_nightly.py, jobs/README.md
- Tags: email, html, markdown, reporting
- Pattern-Key: present.report_email_html_layer

---

## [LRN-20260627-005] best_practice

**Logged**: 2026-06-27T21:55:00+08:00
**Priority**: medium
**Status**: pending
**Area**: delivery

### Summary
When external execution or outbound mail is rate-limited, generate a local HTML preview artifact so report delivery can still be reviewed immediately.

### Details
During the nightly mail enhancement, the session hit a platform-level limit on new external send/fetch commands. The practical fallback was to keep the real mail path intact, but also always generate a repo-local HTML preview that represents the exact intended HTML mail body. That kept the work reviewable and avoided blocking the whole iteration on mail transport availability.

### Suggested Action
For future scheduled reports, treat local HTML preview generation as part of the normal delivery path, not just as a debugging aid.

### Metadata
- Source: error
- Related Files: jobs/muyuan_nightly.py, jobs/README.md
- Tags: rate-limit, email, html, preview, delivery
- Pattern-Key: fallback.local_html_preview_on_send_limit

---

## [LRN-20260628-001] best_practice

**Logged**: 2026-06-28T00:00:00+08:00
**Priority**: medium
**Status**: pending
**Area**: automation

### Summary
For a nightly investment email, reuse one cached Tushare history bundle for both snapshot metrics and trend charts.

### Details
The Muyuan nightly mail now renders both the top-line snapshot and the trend cards from the same cached Tushare history fetch. That keeps the email internally consistent, avoids duplicated API calls, and prevents slight within-run drift between the headline values and the chart series.

### Suggested Action
When building future scheduled reports, fetch the underlying history once and derive both summary fields and chart series from that shared bundle before rendering.

### Metadata
- Source: conversation
- Related Files: jobs/muyuan_nightly.py
- Tags: tushare, cache, email, trends, consistency
- Pattern-Key: reuse.shared_history_bundle_for_report_rendering

---

## [LRN-20260628-002] best_practice

**Logged**: 2026-06-28T00:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
Project-wide configuration is easier to keep stable when it lives in a single TOML file with inline comments, and model routing is hidden behind a reusable public service.

### Details
The best fit for this repository is to keep operational defaults in `config/project.toml`, annotate each parameter with its purpose and allowed values, and expose model execution through a shared `framework.model_service.ModelService`. That gives business modules a clean object to instantiate and call, while the service owns model profile selection, Codex command construction, and runtime switching behind the scenes.

### Suggested Action
For future project settings or model-routing changes, update the TOML and the shared service first, then keep business code focused on deterministic data flow and prompt construction.

### Metadata
- Source: conversation
- Related Files: config/project.toml, framework/project_config.py, framework/model_service.py, jobs/muyuan_nightly.py
- Tags: config, toml, model-service, architecture, separation-of-concerns
- Pattern-Key: architecture.shared_model_service_with_single_config_file

---

## [LRN-20260628-003] best_practice

**Logged**: 2026-06-28T00:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
When one repository must support both Python 3.14 and an older backend venv, project-wide TOML config should include a lightweight parser fallback so the shared config layer works on both interpreters.

### Details
The unified configuration layer initially used `tomllib`, which works on the main Python 3.14 runtime but fails in the backend's Python 3.9 virtualenv. The stable fix was to keep TOML as the canonical config format, but add a small fallback parser for the repository's limited config shape so both runtimes can load the same `config/project.toml` without adding a new dependency or forcing a venv upgrade.

### Suggested Action
For future shared-config work in mixed-Python environments, prefer the simplest parser fallback that covers the repo's current config shape, and validate the same config file under every runtime the repo uses.

### Metadata
- Source: conversation
- Related Files: framework/project_config.py, config/project.toml, backend/app/main.py, backend/app/services/market_data.py
- Tags: toml, compatibility, python39, backend, shared-config
- Pattern-Key: backend.toml_parser_fallback_for_mixed_python_versions

---

## [LRN-20260628-004] best_practice

**Logged**: 2026-06-28T00:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: frontend

### Summary
The frontend can stay fully aligned with a shared project config file by loading TOML at build time in Vite and injecting the parsed object into browser code.

### Details
Because browser code cannot read repository files directly, the stable pattern is to let Vite read `config/project.toml` during startup, inject the parsed config through a define constant, and expose small helper functions such as `apiUrl()` and `docsUrl()` for views. This keeps the frontend, dev proxy, and backend endpoint links in sync without duplicating hardcoded URLs in components.

### Suggested Action
For future frontend configuration changes, update the shared TOML file first, then let the Vite config and shared frontend helper module consume it rather than reintroducing hardcoded URLs in views.

### Metadata
- Source: conversation
- Related Files: frontend/vite.config.js, frontend/scripts/project-config.js, frontend/src/config/project.js, config/project.toml
- Tags: frontend, vite, toml, config, build-time-injection
- Pattern-Key: frontend.vite_build_time_shared_config_injection

---

## [LRN-20260628-005] best_practice

**Logged**: 2026-06-28T00:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: model-routing

### Summary
The shared model service can cleanly support both DeepSeek and Codex by routing `profile=external` to the DeepSeek API and `profile=current` to Codex CLI, while keeping the business layer unaware of the provider choice.

### Details
For this repository, the stable split is to treat DeepSeek as the default external model, with its own API key/base URL/name settings in the shared project config, and keep Codex as the current-model route used for local or “current” execution. The service owns the branching, JSON parsing, and transport details, so callers only instantiate `ModelService` and ask for structured output.

### Suggested Action
When adding future model providers, extend the shared service and config first, and avoid leaking provider-specific logic into business modules.

### Metadata
- Source: conversation
- Related Files: framework/model_service.py, framework/project_config.py, config/project.toml
- Tags: deepseek, codex, routing, model-service, architecture
- Pattern-Key: model_service.external_deepseek_current_codex

---

## [LRN-20260628-006] best_practice

**Logged**: 2026-06-28T00:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: data-quality

### Summary
Cross-unit market metrics should be normalized exactly once in the service layer, then consumed by the presentation layer in a single canonical unit.

### Details
When pig-cycle data mixed spot prices in `元/公斤` with futures prices in `元/吨`, the safest implementation was to convert the futures series to `元/公斤` inside the data service, recompute basis from the normalized series, and let the report layer render only the canonical unit. This avoided a subtle double-conversion bug where the basis function received already-normalized data and divided again.

### Suggested Action
For future financial metrics that mix source units, normalize at the boundary, keep one canonical display unit, and make basis/spread calculations operate only on normalized values.

### Metadata
- Source: conversation
- Related Files: backend/app/services/pig_cycle.py, backend/tests/test_pig_cycle.py, jobs/muyuan_nightly.py
- Tags: unit-normalization, data-quality, basis, futures, spot
- Pattern-Key: normalize.cross_unit_market_metrics_once

---
