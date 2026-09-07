# Bata SIS Sales Intelligence Platform — PRD

## Original problem statement
Enterprise web app (React / FastAPI / MongoDB) that ingests, standardizes, validates and reports on sales files from Bata's 9 SIS retail partners without breaking when partner formats drift. No LLM: deterministic rules + alias dictionary + fuzzy match + learned mapping memory. INR only. Financial corrections never apply silently (human approval). Roles: Administrator, Data Operations, Management. Full spec in the initial user message (ingestion, recognition engine w/ confidence, mapping review, canonical model with originals preserved, validation engine, exception workbench, batches hero page, masters admin, 9 configurable partners, dashboards + 12 reports, rule-based insights, notifications, audit log, Phase-2 stubs).

## User choices
- Keep React (JavaScript) — no TS conversion. Ship end-to-end slice first.
- Emergent Object Storage for original files. Emergent key for any future LLM usage.
- Demo accounts: admin/Admin@123 (vineetnarangofc@gmail.com), ops/Ops@123, mgmt/Mgmt@123.
- Partners: Shoppers Stop, Lifestyle, Central, Pantaloons, Reliance Trends, Westside, Max Fashion, Brand Factory, Vishal Mega Mart.

## Architecture
- `backend/core`: db (motor), auth (bcrypt + PyJWT, role guards), audit/notify helpers, storage (Emergent object storage).
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

## Backlog (prioritized)
- P1: Email ingestion connector activation (needs mailbox creds: Graph/Gmail/IMAP); scheduled report emails; missing-submission scheduled job (cron) creating notifications.
- P1: Real partner formats + Bata masters onboarding via import.
- P2: WhatsApp alerts, ERP/POS push, BI connector docs, LLM insights / NL query (Emergent key).
- P2: SSO; PDF export; per-partner validation rule overrides; store-level targets vs actuals.
