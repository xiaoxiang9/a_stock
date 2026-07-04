# Investment Framework Design

## Objective

Build this repository as a research-first investment framework that supports value-investing practice, continuous tracking, and iterative improvement from real trading decisions.

The first implementation target is not a full platform. It is a single-stock end-to-end MVP using `牧原股份 (002714.SZ)` to prove the workflow.

## Project Positioning

This repository is a research main repository.

Application capabilities such as frontend pages, backend APIs, scheduled jobs, and external presentation are supporting layers, not the top-level organizing principle.

The system is intended to:

- identify good companies
- maintain a good-company list and scoring system
- provide trading rationale at appropriate prices and time windows
- support daily review at 21:00
- accumulate weekly and monthly review evidence
- improve indicators and decision rules over time

## Data Standard

The repository follows this fixed data rule:

1. `tushare` is the primary data source.
2. Eastmoney skills are the secondary validation source.
3. If both fail, use official websites, exchange announcements, regulator disclosures, and other authoritative public webpages.
4. If the official path is unavailable, use established financial websites such as Tonghuashun, Sina Finance, and Yahoo Finance.
5. Avoid weakly sourced or unknown channels whenever stronger sources exist.

Every important datapoint must carry:

- source
- date or reporting period
- primary vs validation role
- definition notes when relevant

If sources disagree, the difference must be surfaced explicitly instead of silently merged.

## Decision Framework

The system uses a fixed five-state action layer:

- `观察`
- `持有`
- `加仓观察`
- `减仓观察`
- `卖出复核`

These labels are fixed for the current framework and should not be expanded during the first implementation cycle.

### State Definitions

`观察`

- not yet built into a position
- belongs to the candidate or watchlist stage
- used to judge whether the company meets the good-company standard

`持有`

- the company has already passed the good-company judgment
- no immediate action is needed
- may represent an existing holding with no change required
- may also represent a company worth holding in principle while waiting for a better entry point with no current position

`加仓观察`

- the company is already considered a good company
- valuation, cycle position, or operating confirmation is becoming more favorable
- enters a high-priority add-position review zone, not an automatic buy instruction

`减仓观察`

- the company is still a good company
- the core logic is not broken
- short-term heat, sentiment, or price extension may be too high
- partial profit-taking and later re-entry may be appropriate after heat fades

`卖出复核`

- this is not a short-term profit-taking state
- it means the core logic may have changed
- the system must re-evaluate whether the company is still a good company and whether continued holding remains justified

## Good Company Framework

The good-company system is separate from the trading system.

It should evaluate only company quality, not current price attractiveness.

### Excluded From Good Company Scoring

- valuation
- near-term risk/reward
- short-term market heat
- short-term trading timing

These belong to the trading layer, not the company-quality layer.

### Five-Dimension Good Company Radar

Each dimension is scored on a 10-point scale and rolled up into a 100-point weighted score.

1. `商业模式` — 25%
2. `行业与竞争格局` — 20%
3. `财务质量` — 25%
4. `管理层与治理` — 15%
5. `周期与确定性` — 15%

### Scoring Purpose

The score is used to:

- judge whether a company belongs in the good-company list
- rank research priority among candidate and approved good companies

The score is not used by itself to trigger trading actions.

## MVP Scope

The first implementation pass focuses only on:

1. repository structure and templates
2. `牧原股份` as the first single-stock sample
3. a maintainable good-company list
4. a first-pass good-company scoring template
5. a first-pass indicator definition set
6. a nightly 21:00 review template

The first pass explicitly avoids:

- multi-stock scaling
- portfolio optimization logic
- complex macro-first narration
- heavy automation before the workflow is proven manually

## Repository Structure

The top-level structure for the first pass should be:

```text
a_stock/
├── universe/
│   └── muyuan/
│       ├── profile/
│       ├── thesis/
│       ├── tracking/
│       ├── valuation/
│       ├── decision/
│       └── review/
├── framework/
│   └── good_companies/
├── signals/
│   ├── definitions/
│   ├── snapshots/
│   └── evaluations/
├── data/
│   ├── raw/
│   ├── validated/
│   └── derived/
├── review/
│   ├── daily/
│   ├── weekly/
│   └── monthly/
├── jobs/
├── app/
│   ├── backend/
│   └── frontend/
└── docs/
```

## File Plan For The First Pass

### Good Company Framework

Create:

- `framework/good_companies/good_company_criteria.md`
- `framework/good_companies/good_companies_list.md`

`good_company_criteria.md` stores the five-dimension scoring standard.

`good_companies_list.md` stores the master table of approved and candidate companies.

### Muyuan Sample

Create:

- `universe/muyuan/profile/company.md`
- `universe/muyuan/thesis/investment_thesis.md`
- `universe/muyuan/tracking/daily_checklist.md`
- `universe/muyuan/tracking/key_indicators.md`
- `universe/muyuan/valuation/valuation_framework.md`
- `universe/muyuan/decision/decision_rules.md`
- `universe/muyuan/decision/current_view.md`
- `universe/muyuan/review/daily/`
- `universe/muyuan/review/weekly/`

### Signal Layer

Create:

- `signals/definitions/muyuan_signals.md`

This file defines the first pass of daily and review indicators for Muyuan.

### Review Layer

Create:

- `review/daily/README.md`
- `review/weekly/README.md`
- `review/monthly/README.md`

This keeps system-level review structure separate from single-stock review notes.

## Good Companies Master Table

The good-company list should begin with these fields:

- company name
- stock code
- industry
- included in good-company list: yes/no
- current state
- total score
- business model score
- industry and competitive structure score
- financial quality score
- management and governance score
- cycle and certainty score
- core thesis
- main risks
- current trading rationale
- last review date

This file should function as the master summary table, with each company also having its own detailed page.

## Muyuan Detail Page Template

The Muyuan detailed file should capture:

- base info
- one-line conclusion
- good-company total score
- five-dimension scoring details
- core investment thesis
- main risks
- key tracking indicators
- current trading rationale
- next observation focus
- review history

This page should be the central living document for the single-stock workflow.

## Nightly 21:00 Review Interaction

The nightly review should be stock-first, not portfolio-first.

Default order:

1. review watchlist and key tracked names
2. update key indicators
3. judge whether current state remains appropriate
4. issue next-day suggestion
5. note whether current indicators were useful and whether any should be improved or added

The first implementation only needs a template and storage location. Full automation comes later.

## First Implementation Order

Follow this order:

1. create repository directories and template files
2. create Muyuan detail page
3. create good-company master table
4. define first-pass key indicator file
5. define nightly 21:00 review template
6. only then start gradual automation

## Risks

- over-engineering before one stock is running end to end
- mixing company quality with valuation and timing
- turning the framework into a macro essay repository instead of a decision system
- adding too many indicators before proving which ones actually help

## Recommendation

Keep the first pass intentionally narrow:

- one stock
- one good-company framework
- one review template
- one decision loop

Only after the Muyuan loop is usable should the system expand to more stocks, more sectors, and heavier automation.
