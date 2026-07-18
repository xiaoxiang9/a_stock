# Subsystem Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the project into the new `app / agents / data` subsystem layout, then fill subsystem configuration and validate startup end-to-end.

**Architecture:** Move legacy `core / jobs / modules / tools` responsibilities into the new backend DDD layers and the new `agents` and `data` subsystems. Keep the top-level `product/scripts/` as thin orchestration wrappers that invoke subsystem-local scripts. Preserve existing runtime behavior by updating import paths, adding compatibility shims where necessary, and validating the full stack after each phase.

**Tech Stack:** Python, FastAPI, Vue, shell scripts, TOML, unittest

## Global Constraints

- `product/app/`, `product/agents/`, and `product/data/` each keep independent config, install, and startup scripts.
- `product/scripts/` only contains top-level `install.sh` and `start.sh` wrappers.
- `product/app/backend/` uses DDD layering: `app / application / domain / infrastructure / tests`.
- Data acquisition priority remains: local snapshots > code fetchers > Tushare > Eastmoney skill > official sources > authoritative finance sites > web search.
- Important data points must keep source, date or period, primary/validation role, and known口径 differences.

---

### Task 1: Move legacy backend logic into the new DDD layout

**Files:**
- Create: `product/app/backend/application/__init__.py`
- Create: `product/app/backend/domain/__init__.py`
- Create: `product/app/backend/infrastructure/__init__.py`
- Create: `product/app/backend/app/routes/__init__.py`
- Modify: `product/app/backend/app/main.py`
- Modify: `product/app/backend/app/services/report_scheduler.py`
- Modify: `product/app/backend/app/services/market_data.py`
- Modify: `product/app/backend/app/services/pig_cycle.py`
- Modify: `product/app/backend/app/services/__init__.py`

**Interfaces:**
- Consumes: existing FastAPI app, scheduler, market data helpers, pig-cycle helpers
- Produces: DDD-friendly backend layout with the same runtime behavior exposed through the new structure

- [ ] **Step 1: Create the new package markers**

Create empty `__init__.py` files in the new DDD directories so the new layout is importable immediately.

- [ ] **Step 2: Rehome the scheduler and data helpers**

Move scheduling and external data service code into `infrastructure`, then keep the old `app/services/*` modules as thin compatibility wrappers that import from the new location.

- [ ] **Step 3: Update FastAPI startup wiring**

Keep `main.py` as the interface layer only, importing scheduler construction and data endpoints from the new structure.

- [ ] **Step 4: Run the backend unit tests that cover the moved code**

Run:

```bash
python3 -m unittest product.tests.test_app_config product.tests.test_market_data product.tests.test_pig_cycle product.tests.test_report_scheduler -v
```

Expected: the tests still pass after the import path changes.

### Task 2: Move research documents into the backend domain

**Files:**
- Move: `product/modules/companies/README.universe.md` -> `product/app/backend/domain/companies/README.universe.md`
- Move: `product/modules/companies/muyuan/README.md` -> `product/app/backend/domain/companies/muyuan/README.md`
- Move: `product/modules/companies/muyuan/profile/company.md` -> `product/app/backend/domain/companies/muyuan/profile/company.md`
- Move: `product/modules/companies/muyuan/thesis/investment_thesis.md` -> `product/app/backend/domain/companies/muyuan/thesis/investment_thesis.md`
- Move: `product/modules/companies/muyuan/tracking/daily_checklist.md` -> `product/app/backend/domain/companies/muyuan/tracking/daily_checklist.md`
- Move: `product/modules/companies/muyuan/tracking/key_indicators.md` -> `product/app/backend/domain/companies/muyuan/tracking/key_indicators.md`
- Move: `product/modules/companies/muyuan/valuation/valuation_framework.md` -> `product/app/backend/domain/companies/muyuan/valuation/valuation_framework.md`
- Move: `product/modules/companies/muyuan/decision/decision_rules.md` -> `product/app/backend/domain/companies/muyuan/decision/decision_rules.md`
- Move: `product/modules/companies/muyuan/decision/current_view.md` -> `product/app/backend/domain/companies/muyuan/decision/current_view.md`
- Move: `product/modules/companies/muyuan/review/daily/README.md` -> `product/app/backend/domain/companies/muyuan/review/daily/README.md`
- Move: `product/modules/companies/muyuan/review/weekly/README.md` -> `product/app/backend/domain/companies/muyuan/review/weekly/README.md`
- Move: `product/modules/good_companies/README.framework.md` -> `product/app/backend/domain/good_companies/README.framework.md`
- Move: `product/modules/good_companies/good_companies_list.md` -> `product/app/backend/domain/good_companies/good_companies_list.md`
- Move: `product/modules/good_companies/good_company_criteria.md` -> `product/app/backend/domain/good_companies/good_company_criteria.md`
- Move: `product/modules/signals/definitions/muyuan_signals.md` -> `product/app/backend/domain/signals/muyuan_signals.md`

**Interfaces:**
- Consumes: existing research markdown files
- Produces: backend-owned domain research docs, no duplicate copies in `product/modules/`

- [ ] **Step 1: Move the files into the backend domain tree**

Use directory moves so file history and links remain as intact as possible.

- [ ] **Step 2: Remove the now-empty legacy `product/modules/` directories**

Delete the old module directories after confirming their contents exist in the backend domain tree.

- [ ] **Step 3: Run a path sanity check**

Run:

```bash
find product/modules -maxdepth 4 -type f | sort
```

Expected: no project-owned module docs remain under `product/modules/`.

### Task 3: Consolidate core configuration and deployment helpers into the backend/infrastructure boundary

**Files:**
- Move: `product/core/project_config.py` -> `product/app/backend/infrastructure/config/project_config.py`
- Move: `product/core/private_config.py` -> `product/app/backend/infrastructure/config/private_config.py`
- Move: `product/core/model_service.py` -> `product/app/backend/infrastructure/model_service.py`
- Move: `product/tools/deployment_checks.py` -> `product/app/backend/infrastructure/deployment_checks.py`
- Modify: `product/app/backend/app/main.py`
- Modify: `product/app/backend/tests/test_project_config.py`
- Modify: `product/app/backend/tests/test_model_service.py`
- Modify: `product/app/backend/tests/test_deployment_checks.py`
- Modify: `product/data/fetchers/market_data.py`
- Modify: `product/data/fetchers/stock.py`
- Modify: `product/jobs/muyuan_nightly.py`

**Interfaces:**
- Consumes: shared config and model-loading helpers
- Produces: backend-owned infrastructure helpers with updated import paths

- [ ] **Step 1: Move the core utility modules**

Move the configuration and model helper modules into backend infrastructure, then update imports everywhere they are referenced.

- [ ] **Step 2: Move the deployment check utility**

Move deployment checks under backend infrastructure and keep `product/scripts/` calling the new location.

- [ ] **Step 3: Run the Python test suite that depends on the moved helpers**

Run:

```bash
python3 -m unittest product.tests.test_project_config product.tests.test_model_service product.tests.test_deployment_checks -v
```

Expected: all helper tests still pass after import path updates.

### Task 4: Refresh subsystem config and script entry points

**Files:**
- Create: `product/app/config/app.toml`
- Create: `product/agents/config/agents.toml`
- Create: `product/data/config/data.toml`
- Create: `product/app/scripts/install.sh`
- Create: `product/app/scripts/start.sh`
- Create: `product/app/scripts/stop.sh`
- Create: `product/agents/scripts/install.sh`
- Create: `product/agents/scripts/start.sh`
- Create: `product/agents/scripts/run_research.sh`
- Create: `product/data/scripts/install.sh`
- Create: `product/data/scripts/start.sh`
- Create: `product/data/scripts/refresh.sh`
- Modify: `product/scripts/install.sh`
- Modify: `product/scripts/start.sh`

**Interfaces:**
- Consumes: backend and subsystem-local config loaders
- Produces: each subsystem can be installed and started independently, while top-level scripts remain thin orchestrators

- [ ] **Step 1: Add the subsystem-local config files**

Write minimal TOML files that mirror the existing public config defaults for each subsystem.

- [ ] **Step 2: Add the subsystem-local scripts**

Create thin shell wrappers that call the appropriate backend, agent, or data entry points.

- [ ] **Step 3: Wire the top-level scripts to the subsystem scripts**

Keep the root scripts as the only top-level entry points and have them delegate to the subsystem-local scripts.

### Task 5: Validate the full migration

**Files:**
- No new files; use the migrated tree

**Interfaces:**
- Consumes: the migrated repository layout and updated imports
- Produces: verified startup behavior and a recorded migration result

- [ ] **Step 1: Run backend and domain tests**

Run:

```bash
python3 -m unittest product.tests.test_app_config product.tests.test_market_data product.tests.test_pig_cycle product.tests.test_report_scheduler product.tests.test_project_config product.tests.test_model_service product.tests.test_deployment_checks -v
```

- [ ] **Step 2: Run the frontend and script checks**

Run:

```bash
bash -n product/scripts/install.sh
bash -n product/scripts/start.sh
```

- [ ] **Step 3: Start the system and verify the API endpoints**

Run the startup script, then verify `/api/health` and the daily report endpoint return successful responses.

- [ ] **Step 4: Record the migration in `records/build_log.md`**

Add one build-log entry summarizing the migration, configuration split, and validation result.
