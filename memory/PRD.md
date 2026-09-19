# Bata SIS Sales Intelligence Platform — PRD

## Original problem statement
Enterprise web app (React / FastAPI / MongoDB) that ingests, standardizes, validates and reports on sales files from Bata's 9 SIS retail partners without breaking when partner formats drift. No LLM: deterministic rules + alias dictionary + fuzzy match + learned mapping memory. INR only. Financial corrections never apply silently (human approval). Roles: Administrator, Data Operations, Management. Full spec in the initial user message (ingestion, recognition engine w/ confidence, mapping review, canonical model with originals preserved, validation engine, exception workbench, batches hero page, masters admin, 9 configurable partners, dashboards + 12 reports, rule-based insights, notifications, audit log, Phase-2 stubs).

## User choices
- Keep React (JavaScript) — no TS conversion. Ship end-to-end slice first.
- object storage for original files. platform key for any future LLM usage.
- Demo accounts: admin/Admin@123 (vineetnarangofc@gmail.com), ops/Ops@123, mgmt/Mgmt@123.
- Partners: Shoppers Stop, Lifestyle, Central, Pantaloons, Reliance Trends, Westside, Max Fashion, Brand Factory, Vishal Mega Mart.

## Architecture
- `backend/core`: db (motor), auth (bcrypt + PyJWT, role guards), audit/notify helpers, storage (object storage).
- `backend/services`: parser (xlsx/xls/csv, header-row detection, blank/total-row skipping, number/date coercion), recognition (canonical fields, alias index, learned mappings, partner detection, column mapping w/ rapidfuzz, confidence), validation (12 rule codes, ValidationContext, business-key dedup), pipeline (create_batch → analyse → approve_mapping → validate → load_to_reporting; restatement supersede; reprocess; revise_row versioning), insights (statistical anomaly rules).
- `backend/routers`: auth_users, ingestion (uploads, batches, mapping approval, exceptions actions, review queue), masters (8 masters CRUD/import/export/versions, partners, settings, email connector w/ Fernet-encrypted creds, integrations), analytics (dashboard, 12 reports + records drill-down + exports + saved views, insights, data quality, audit logs, notifications).
- Mongo layers: raw_files → raw_rows → std_rows (versioned, is_current) → sales (reporting) → exceptions → config (partners, stores, skus, aliases, partner_mappings, validation_rules, sender_rules, settings) → audit_logs, notifications.
- Background jobs: asyncio tasks with retry; idempotent re-validation (delete+rebuild per batch); file-hash dedup.
- Frontend: React + shadcn + recharts; AppShell sidebar (13 nav items, role-gated), pages for every nav item; data-testids everywhere.
- Unit tests: `backend/tests/test_engine.py` (parser, mapping, validation, dedup); e2e API suite `tests/test_api_e2e.py` (testing agent).

## Implemented (2026-06 / iteration 1)
- Auth + roles, users admin, brute-force lockout, change password.
- Upload w/ preview, recognition with confidence per partner/header/column/overall, thresholds (settings), auto-accept / review routing.
- Mapping review screen with override, ignore, remember → versioned partner mappings + learned aliases.
- Validation engine (REQUIRED_FIELD, INVALID_DATE, FUTURE_DATE, UNKNOWN_STORE, UNKNOWN_SKU, NEGATIVE_QTY, INVALID_PRICE, DISCOUNT_OVER_LIMIT, ARITHMETIC_MISMATCH, DUPLICATE_ROW, ROW_COUNT_ANOMALY, MISSING_SUBMISSION) with severity/blocking config; partial ingestion per partner.
- Exception workbench: accept/correct/map-to-master/add-master/ignore/reject-row/reject-file/assign/comment/revalidate, bulk actions, row version history.
- Batches hero page + batch detail (mapping, rows raw/standardized/reporting, preview, timeline, audit), download original, reprocess, reject, restatement approve-supersede.
- Dashboard KPIs/charts; 12 reports + source-record drill-down, sort/filter/column select/saved views/CSV+Excel export.
- Rule-based insights (spike/drop, underperformers, missing submissions, discount outliers, row-count anomalies, rejection rate) linked to records; NL query stub.
- Masters admin (stores, SKUs, hierarchy, geo, aliases, rules, sender rules) with versions/import/export; Partner configuration; Email configuration (awaiting credentials); Settings; Audit logs; Notifications (in-app; email/WhatsApp inactive).
- Seed: 9 partners, 45 stores, 24 SKUs, 60 days synthetic sales, 12 demo scenario files run through the real pipeline.

## Implemented (iteration 2 — real Bata data, 2026-06)
- Replaced synthetic seed with `seed_real.py`: onboarded the SIS Automation Templates zip (`/app/data/sis`): 10 partners (Cluster Manager Mapping), 551 stores w/ city/state/region/cluster manager, ~4k article master (from 2025 sales + stock + week-32 files), 165k rows of 2025 weekly history (import batches), Q2 targets (`targets`), Week-32 stock (`stock`), partner margins (`margins`).
- Pre-approved v1 partner mappings for all 9 week-32 formats; the 9 Week-32 files ingested through the live pipeline (all processed; partner-internal article codes flagged as UNKNOWN_SKU warnings, KORA subtotal rows skipped, returns allowed).
- Engine hardening: learned mapping precedence + ignored columns, 7-digit article extraction, derived unit price, tax-inclusive arithmetic tolerance, trailing-minus numbers, total-row detection anywhere in first cell.
- New reports: Target vs Actual, Stock Position, Partner Margin (15 total). Dashboard is "as of" latest sale date with weekly Bata-week trend and Week-32 target achievement KPI.
- Testing agent iteration 2: 54/54 backend + UI flows pass.

## Implemented (iteration 3 — Ask Bata agent + Help Center, 2026-06)
- **Ask Bata** analytics agent: GPT-5.4 via Emergent Universal Key (emergentintegrations `LlmChat` streaming + function calling). Backend `routers/ask.py` (sessions CRUD per user in `chat_sessions`/`chat_messages`, SSE `POST /api/ask/sessions/{id}/messages`, suggestions, `/api/ask/help`), `services/agent_tools.py` (15 live-data tools: get_data_coverage, run_report, aggregate_sales, get_dashboard, get_targets_vs_actual (partner/store/grpcat/cluster_manager), get_stock, get_margins, list_partners, find_store, find_article, get_batches, get_exceptions, get_data_quality, get_insights, search_help). System prompt = business brief + exact formula definitions from `services/help_content.py` + live coverage. Never invents numbers; tool calls shown in UI as expandable chips with data preview. Read-only; ingestion engine unchanged (rules only).
- Frontend: `/ask` page (session list + ChatPanel with streaming markdown, tool chips), floating "Ask Bata" drawer (AskFab) on every page, nav items for all roles; Insights NL stub replaced with link. Friendly error when Universal Key balance is exhausted.
- **Help Center** `/help`: 11 sections / 80 items (dashboard KPIs, 15 reports + records, 13 formulas, pipeline & recognition confidence, 12 validation rules, exceptions, insights rules, roles, Ask Bata, glossary), search, TOC, hash deep-links with highlight. Contextual `HelpLink` "?" icons on Dashboard KPI cards & chart titles, Reports header + per-report, Insights, Ask page.
- Testing agent iteration 7: 10/10 backend + all UI flows pass. NOTE: Universal LLM key balance was exhausted during testing — user must top up (Profile → Manage plan → Universal Key → Add Balance).


- P1: Email ingestion connector activation (needs mailbox creds: Graph/Gmail/IMAP); scheduled report emails; missing-submission scheduled job (cron) creating notifications.
- P1: Real partner formats + Bata masters onboarding via import.
- P2: WhatsApp alerts, ERP/POS push, BI connector docs, LLM insights / NL query (platform key).
- P2: SSO; PDF export; per-partner validation rule overrides; store-level targets vs actuals.

## Implemented (iteration 4 — SIS Secondary Sales report from Power BI + proposal, 2026-06)
- Extracted the Power BI `SIS Secondary Dashboard 2026.pbix` (pbixray): SALES REPORT fact table (218,447 rows: 2025 wk1-52, 2026 wk1-16), 56 DAX measures, 6 calculated columns, Hier1-5 field parameters. Saved as `/app/data/sis/pbix_sales_report.csv.gz`; loaded to `sis_sales` by `backend/seed_pbix.py` (idempotent at startup; `POST /api/sis/reload` admin) with pre-computed row components (mrp_val, cost_val, gst_val, gst_reversal, margin_val, margin_nsv, panel_w, ltl_nsv). `sis_meta` holds latest till-date week (16) / month (Apr).
- `routers/sis_report.py`: `/api/sis/meta`, `/api/sis/filters` (cascading), `/api/sis/sales-report` (5-level dynamic hierarchy, 13 list filters + till_date/latest_wk/latest_month/week range/search, sort, pagination, totals with distinct store counts & panels via 5-stage Mongo aggregation, CONT %), `/api/sis/sales-report/export` (csv/xlsx). All Sales-tab and Finance-tab DAX measures reproduced (help section `sis`).
- Frontend `/sis-sales` (SisSales.jsx + components/sis/*): hero KPI bar, hierarchy selects, multi-select slicers, toggles, sortable paginated grid with growth colouring, column sets (Sales/Finance/All) + chooser, drill-down, CSV/Excel export, URL-persisted state, "?" help links per column. Nav item for all roles.
- Help Center: new "SIS Secondary Sales Report" section (15 topics + alias anchors for every column). Ask Bata: new `sis_sales_report` tool + formula definitions in system prompt.
- Techno-commercial proposal PDF (Bata + Powered by Fundle, live screenshots, scope, stack, formulas, hosting/AI/support, commercials ₹3.75L one-time + ₹1.25L/month, add-ons, out-of-scope, timeline): generator `/app/data/proposal/build_proposal.py` (screenshots in /app/data/proposal), served at `/proposal/Bata_SIS_TechnoCommercial_Proposal_Fundle.pdf`.
- Testing agent iteration 8: 20/21 backend (the 1 "fail" was a spec-count mismatch, not a bug) + all UI flows pass.

## Backlog (prioritized)
- P1: Remaining Power BI tabs natively (Stock, Prosperity, Finance visuals, Incentive, Store/Region Top Art) — Finance measures already computed in sis report.
- P1: Ask Bata answer → Excel export; store target drill dashboard; weekly digest PDF.
- P1: Email ingestion connector activation (needs mailbox creds); scheduled report emails; missing-submission cron; admin one-click password reset.
- P2: WhatsApp alerts, ERP/POS push, BI connector docs; SSO; per-partner validation rule overrides.
- NOTE: Universal LLM key balance exhausted as of iteration 3/4 — user must top up for Ask Bata.

## Iteration 5 (2026-06) — brand layer, KAZO proposal, login resilience
- `lib/brand.js`: `?brand=kazo` white-labels the app (logo, monochrome accent via `.brand-kazo` CSS overrides, "Ask KAZO", hero image); `?brand=reset` back to Bata (default). Used for KAZO proposal screenshots (`/app/data/proposal/kazo/`, generator `build_proposal_kazo.py`, PDF at `/proposal/KAZO_SIS_TechnoCommercial_Proposal_Fundle.pdf`, ₹1.49 L + ₹49k/month).
- Login: Cloudflare 5xx/HTML gateway errors (pod waking up) now show a friendly message and auto-retry ×3 (`isGatewayError` in api.js). Testing iteration 9: all pass.
