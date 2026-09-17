"""Single source of truth for the Help Center and the Ask Bata agent's knowledge of formulas."""
from services.validation import DEFAULT_RULES

MONEY = "All amounts are INR (₹). Net Sales / NSV = `net_amount` as reported by the partner (after discount; tax-inclusive or exclusive depending on the partner file — the arithmetic check accepts both)."

FORMULAS = [
    {"id": "f-gross", "title": "Gross Amount", "formula": "gross_amount = quantity × unit_price", "body": "Unit price is the partner's reported selling price per pair. If the file has no unit price, it is derived: `unit_price = (net_amount + discount) / quantity` (or MRP when present)."},
    {"id": "f-net", "title": "Net Sales (NSV)", "formula": "net_amount (as reported) ≈ gross_amount − discount + tax", "body": MONEY},
    {"id": "f-discount-pct", "title": "Discount %", "formula": "discount_pct = discount ÷ gross_amount × 100", "body": "Computed per row at load time and re-computed on aggregates as Σdiscount ÷ Σgross × 100 (weighted, not an average of percentages)."},
    {"id": "f-avg-ticket", "title": "Average Ticket", "formula": "avg_ticket = Σ net_amount ÷ transactions", "body": "`transactions` = number of reporting rows (sales lines) in the group. For weekly-aggregated history one row = one article-size-store-week line."},
    {"id": "f-achievement", "title": "Target Achievement %", "formula": "achievement_pct = actual_NSV ÷ target × 100", "body": "Actual NSV is Σ net_amount from `sales` for the selected Bata week (default Week 32, 2026). Target is Σ `targets.target` (Q2 store × GRPCAT weekly targets from the SIS target template)."},
    {"id": "f-gap", "title": "Gap to Target", "formula": "gap = actual_NSV − target", "body": "Negative = shortfall, positive = over-achievement."},
    {"id": "f-weeks-cover", "title": "Weeks of Cover", "formula": "weeks_cover = stock_qty ÷ sold_last_week_qty", "body": "Stock is the Week-32 closing stock (pairs) per store; `sold` is the Week-32 sold pairs of the same store. Blank when the store sold nothing that week."},
    {"id": "f-margin", "title": "Partner Margin & Bata Net", "formula": "partner_margin = NSV × margin_pct ; bata_net = NSV × (1 − margin_pct)", "body": "Margin % comes from the `margins` master per partner and market (BATA vs HP = Hush Puppies, detected when brand contains 'hush')."},
    {"id": "f-acceptance", "title": "Acceptance % (Data Quality)", "formula": "acceptance_pct = (accepted + warning rows) ÷ total rows × 100", "body": "Rows with warnings are loaded into reporting and therefore count as accepted. Rejected (blocking error) and duplicate rows are excluded."},
    {"id": "f-bata-week", "title": "Bata Week", "formula": "week 1 = 1 Jan → first Sunday; then Monday-to-Sunday weeks", "body": "`week = ((sale_date − Jan 1).days + weekday(Jan 1)) // 7 + 1`. This matches the Bata Date Mapping template. Weekly history rows are dated on the week's start date."},
    {"id": "f-as-of", "title": "'As of' date", "formula": "as_of = latest sale_date in reporting data", "body": "Dashboards are computed relative to the newest sale date in the data, not the wall clock, so a late file never makes the dashboard look empty. MTD = month of the as-of date. 'Last 30 days' = as_of − 30 days."},
    {"id": "f-mtd-change", "title": "MTD change vs previous month", "formula": "mtd_change_pct = (MTD_net − prev_month_net_to_same_day) ÷ prev_month_net_to_same_day × 100", "body": "Previous month is truncated to the same number of elapsed days for a like-for-like comparison."},
    {"id": "f-confidence", "title": "Recognition confidence", "formula": "overall = 0.3 × partner_conf + 0.1 × header_conf + 0.6 × avg(column_conf)", "body": "Capped at 45 if any required field (date, store, article, qty, net) is unmapped, and at 40 if no partner was identified. Column confidence: learned mapping 100 · exact standard-field name 98 · known alias 94 · fuzzy ≥80% similarity → similarity × 0.88; ±3 / −30 adjustment when sample values match / contradict the expected type. Levels: high ≥ 90 (auto-accept), medium ≥ 70 (review), low < 70 (review)."},
]

DASHBOARD = [
    {"id": "d-sales", "title": "SIS Sales · month", "body": "Σ net_amount for the as-of month across all partners (or the selected partner). Sub-line shows pairs (Σ quantity) and lines (row count). See *'As of' date*."},
    {"id": "d-target", "title": "Week 32 target achievement", "body": "Σ actual NSV ÷ Σ target for Bata week 32 (2026), all partners with targets. Also shows how many partners have submitted a live file in the last 14 days. Click to open the Target vs Actual report."},
    {"id": "d-acceptance", "title": "Accepted record ratio (30d)", "body": "(accepted + warning) ÷ total rows across non-rejected batches created in the last 30 wall-clock days. See *Acceptance %*."},
    {"id": "d-pending", "title": "Pending action", "body": "Count of exceptions with status `open` plus batches in `Awaiting Review`. Click to open the Review Queue."},
    {"id": "d-weekly", "title": "Weekly net sales chart", "body": "Σ net_amount grouped by (year, Bata week) — last 40 weeks shown. 2025 history comes from the weekly Bata standard template import; 2026 weeks come from live partner files."},
    {"id": "d-partner", "title": "Sales by partner (30 days)", "body": "Σ net_amount by partner for the 30 days ending on the as-of date (always all partners, ignores the partner filter)."},
    {"id": "d-dq", "title": "Data quality by partner", "body": "Stacked accepted / rejected / duplicate row counts of live (non-import) batches per partner."},
    {"id": "d-category", "title": "Category mix", "body": "Top 8 categories by Σ net_amount in the last 30 days of data; bar length is relative to the top category."},
    {"id": "d-top-skus", "title": "Top articles", "body": "Top 5 article codes by Σ net_amount in the last 30 days of data, with pairs."},
    {"id": "d-recent", "title": "Recent ingestion batches", "body": "Latest 8 batches with status, row counts and recognition confidence."},
]

REPORTS = [
    {"id": "r-daily_sales", "title": "Daily Sales Trend", "body": "Group by `sale_date`. Metrics: Qty, Gross, Discount, Net, Txns, Disc %, Avg Ticket. Weekly-imported history appears on the week start date."},
    {"id": "r-monthly_sales", "title": "Monthly Sales Summary", "body": "Group by `month` (YYYY-MM of sale_date)."},
    {"id": "r-partner_performance", "title": "Partner Performance", "body": "Group by partner. Sorted by Net desc."},
    {"id": "r-store_performance", "title": "Store / SIS Performance", "body": "Group by partner, store code, store name, city, region (from the store master)."},
    {"id": "r-region_performance", "title": "Region Performance", "body": "Group by region (North / South / East / West from the store master)."},
    {"id": "r-category_performance", "title": "Category Performance", "body": "Group by category and brand. Category is the Bata GRPCAT (BATA MEN, BATA WOMEN, HP MEN, HP WOMEN, KIDS, FLOATZ, NFT) derived from the article master, or the partner's own category label when the article is unknown."},
    {"id": "r-sku_performance", "title": "SKU / Article Performance", "body": "Group by 7-digit Bata article code, name and category."},
    {"id": "r-top_bottom", "title": "Top / Bottom Articles", "body": "Articles ranked by Net; shows the top N and bottom N (N = 5/10/20)."},
    {"id": "r-discount_analysis", "title": "Discount Analysis", "body": "Group by partner and month with weighted Disc % (Σdiscount ÷ Σgross)."},
    {"id": "r-data_quality_trend", "title": "Data Quality Trend", "body": "Per batch-creation day: batches, rows, accepted, warnings, rejected, duplicates, Acceptance %."},
    {"id": "r-missing_submissions", "title": "Missing Submission Calendar", "body": "For each active partner and each of the last N days: number of files received. Missing = days with zero files."},
    {"id": "r-exception_summary", "title": "Exception Summary", "body": "Exceptions grouped by partner, rule and severity with open / resolved / ignored / rejected counts."},
    {"id": "r-target_vs_actual", "title": "Target vs Actual", "body": "Per partner for a Bata week (default 32): target stores, stores reported, Σ target, Σ actual NSV, Gap, Achievement %, pairs. See *Target Achievement %*."},
    {"id": "r-stock_position", "title": "Stock Position (Week 32)", "body": "Per store: distinct articles, stock pairs, Week-32 sold pairs and Weeks of Cover."},
    {"id": "r-partner_margin", "title": "Partner Margin Contribution", "body": "Per partner and market (BATA / HP): NSV, pairs, margin %, partner margin ₹, Bata net ₹."},
    {"id": "r-records", "title": "Source Records (drill-down)", "body": "Row-level reporting data with every filter; each row links back to its ingestion batch. Clicking any aggregate row in a report opens the matching records."},
]

PIPELINE = [
    {"id": "p-flow", "title": "Ingestion flow", "body": "Upload / email → **Received** → parse (xlsx/xls/csv, header-row detection, blank & total-row skipping) → recognition (partner, header row, column mapping with confidence) → **Awaiting Review** if confidence is medium/low or a required field is unmapped, otherwise auto-accept → **Validating** (12 rules) → **Successfully Processed** or **Partially Processed** (some rows rejected/duplicate) → loaded into `sales` reporting. Other statuses: **Failed** (no data / all rows rejected), **Rejected** (by a user), **Superseded** (replaced by an approved restatement), **Reprocessed**."},
    {"id": "p-recognition", "title": "Recognition engine (rules only, no AI)", "body": "Order of precedence per column: 1) previously approved mapping for the partner (learned memory), 2) exact Bata standard field name, 3) alias dictionary (global + partner-specific), 4) fuzzy match (token-set ratio ≥ 80%). Each field can be claimed by one column only — the highest-confidence column wins. Partner detection: +60 filename keyword, +40 partner name in sheet header, +35 header signature ≥70% overlap with learned mapping; −30 when two partners tie within 10 points."},
    {"id": "p-thresholds", "title": "Confidence thresholds", "body": "Settings → thresholds: high (default 90) and medium (default 70). High → auto-accept mapping. Medium → behaviour per `medium_behavior` setting (default review). Low → always review. Approving a mapping with 'remember' creates a new partner mapping version and learned aliases."},
    {"id": "p-restatement", "title": "Restatements", "body": "A new file overlapping an already-loaded partner/date range goes to Awaiting Review with a restatement flag. Approving it supersedes the previous batch (rows removed from reporting, batch status Superseded); the original file is always kept."},
    {"id": "p-dedup", "title": "Duplicate detection", "body": "File level: SHA-256 hash of the file. Row level: business key = partner | store | date | article | invoice | qty | net. Duplicate rows are not loaded to reporting."},
]

EXCEPTIONS = [
    {"id": "e-actions", "title": "Exception actions", "body": "**Accept** (keep value, warning only) · **Correct** (edit the value; creates a new row version, original preserved) · **Map to master** (link unknown store/article to a master record and optionally remember as alias) · **Add to master** (create the store/article) · **Ignore** · **Reject row** · **Reject file** · **Assign** · **Comment** · **Re-validate**. Financial fields are never auto-corrected — every fix is a human action recorded in the audit log."},
    {"id": "e-status", "title": "Exception statuses", "body": "`open` → `accepted` / `corrected` / `resolved` / `ignored` / `rejected`. Only `open` exceptions count in 'Pending action'."},
]

INSIGHTS = [
    {"id": "i-spike", "title": "Sales spike / drop", "body": "Per partner: latest daily net vs the previous 14-day mean. Flagged when |z-score| > 2 or |Δ| > 40%."},
    {"id": "i-under", "title": "Underperforming store", "body": "Store 14-day net below 50% of the partner's store median (max 3 per partner)."},
    {"id": "i-missing", "title": "Missing submission", "body": "No non-import batch within expected frequency + grace days (MISSING_SUBMISSION rule, default 2)."},
    {"id": "i-discount", "title": "Discount outliers", "body": "Rows with discount % above mean + 2σ of a 5,000-row sample of the last 30 days."},
    {"id": "i-rowcount", "title": "Row count anomaly", "body": "Batch row count deviating more than the ROW_COUNT_ANOMALY deviation % (default 50%) from the partner's usual volume."},
    {"id": "i-rejection", "title": "High rejection rate", "body": "Partner with > 10% rejected rows in the last 7 days."},
]

ROLES = [
    {"id": "role-admin", "title": "Administrator", "body": "Everything: masters, partner configuration, email connector, users & roles, settings, plus all Ops and Management capabilities. An admin cannot remove their own admin role; if no active admin exists the configured admin account is restored at startup."},
    {"id": "role-ops", "title": "Data Operations User", "body": "Upload files, review mappings, work the exception queue, reprocess/reject batches, run reports, view insights, data quality, audit logs, Ask Bata."},
    {"id": "role-mgmt", "title": "Management User", "body": "Read-only: dashboard, batches, reports, insights, data quality, audit logs, Ask Bata."},
]

GLOSSARY = [
    {"id": "g-sis", "title": "SIS", "body": "Shop-in-Shop — a Bata counter inside a partner's store (Shoppers Stop, Lifestyle, Reliance Trends, Centro, etc.)."},
    {"id": "g-nsv", "title": "NSV", "body": "Net Sales Value — see Net Sales."},
    {"id": "g-grpcat", "title": "GRPCAT", "body": "Bata group category: BATA MEN, BATA WOMEN, HP MEN, HP WOMEN, KIDS, FLOATZ, NFT."},
    {"id": "g-hp", "title": "HP", "body": "Hush Puppies — premium brand with a separate partner margin."},
    {"id": "g-cm", "title": "Cluster Manager", "body": "Bata field manager responsible for a set of partner stores (from the Cluster Manager Mapping master)."},
    {"id": "g-article", "title": "Article", "body": "7-digit Bata article (SKU) code. Partner-internal codes are flagged UNKNOWN_SKU until mapped."},
    {"id": "g-batch", "title": "Batch", "body": "One ingested file and everything derived from it (raw rows, standardized rows, reporting rows, exceptions, audit trail)."},
    {"id": "g-partial", "title": "Partial ingestion", "body": "Partner setting: valid rows load even when some rows are rejected. When disabled, any rejected row fails the batch."},
]

ASK = [
    {"id": "a-what", "title": "What Ask Bata is", "body": "A conversational analytics agent (GPT-5.4 via the platform key) that answers questions about SIS sales, targets, stock, margins, data quality and the pipeline. It **never estimates numbers** — every figure comes from a live query tool over the same MongoDB reporting data the dashboards use, and the queries it ran are shown under each answer."},
    {"id": "a-tools", "title": "What it can query", "body": "Any of the 15 reports with filters · ad-hoc aggregation of sales by partner / store / region / city / cluster manager / category / brand / article / size / date / month / week · dashboard KPIs · store-level targets vs actual · stock & weeks cover · partner margins · batches, exceptions, data quality, insights · store and article master lookup · this Help Center."},
    {"id": "a-limits", "title": "What it does not do", "body": "It does not ingest or modify data, cannot change mappings or masters, and the file-ingestion engine remains 100% rules-based. Answers are as good as the loaded data — check the data coverage it reports when in doubt."},
]


SIS_REPORT = [
    {"id": "sis-report", "title": "What the report is", "body": "A live replica of the Power BI **SIS DASHBOARD 2026 → SALES** matrix built on the SIS Secondary Sales fact table (218k rows: 2025 weeks 1–52 and 2026 weeks 1–16, 8 partners, ~320 stores, article × size × store × week). Every measure below is recomputed on the server for the current hierarchy and slicers; nothing is pre-aggregated or hard-coded. Suffix **-25 / -26** = calendar year of the sale (`YEAR` column); **G** = growth."},
    {"id": "s-hierarchy", "title": "Hierarchy levels (Hier1–Hier5)", "body": "Up to five row dimensions, exactly like the Power BI field parameters: Market, Partner, Cluster Manager, State, Store Code, Store Name, City, GRPCAT, Category (CAT NAME), Article, Existing vs New, Top Stores, Month, Week, LTL Status. Rows are the distinct combinations of the chosen levels; the ↳ icon drills into a row by adding it as a filter and moving one level down."},
    {"id": "s-slicers", "title": "Slicers", "body": "Partner, Cluster Manager, Market (BATA / HP), State, City, Store, GRPCAT, Category, Month, Week, LTL, Top Stores, Existing/New — multi-select and **cascading** (each slicer only offers values that exist under the other active slicers). Text search matches store name/code, article, cluster manager or city."},
    {"id": "s-till-date", "title": "Till Date · Latest Month · Latest Wk", "formula": "TILL DATE = 'Yes' when the week has NSV > 0 in BOTH 2025 and 2026", "body": "Till Date restricts both years to the like-for-like weeks that exist in the current year — use it for a fair NSV G. **Latest Wk** = the highest till-date week (currently Wk 16); **Latest Month** = the month (BMONTH) of that week (Apr). Both mirror the Power BI calculated columns."},
    {"id": "s-nsv", "title": "NSV-25 / NSV-26", "formula": "NSV-yy = Σ NSV where YEAR = yy", "body": "Net Sales Value reported by the partner (after discount, tax-inclusive). DAX: `CALCULATE(SUM([NSV]), YEAR=\"2026\")`."},
    {"id": "s-cont_pct", "title": "CONT %", "formula": "CONT % = NSV-26 of the row ÷ NSV-26 of all rows in the current filter", "body": "Share of current-year sales. The Total row is always 100%."},
    {"id": "s-nsv_g", "title": "NSV G", "formula": "NSV G = (NSV-26 − NSV-25) ÷ NSV-25", "body": "Year-on-year growth. Without the Till Date slicer 2025 contains 52 weeks vs 16 in 2026, so the growth is strongly negative — switch Till Date on for a like-for-like view."},
    {"id": "s-ltl_g", "title": "LTL G (like-to-like growth)", "formula": "LTL G = (Σ NSV-26 − Σ NSV-25) ÷ Σ NSV-25, rows where LTL = 'LTL' only", "body": "**LTL status** is computed per store × month: `LTL` when the store has non-zero NSV in that month in both 2025 and 2026; `NEW` when only 2026; `CLOSED` when only 2025. LTL G therefore excludes new and closed stores."},
    {"id": "s-str", "title": "#STR-25 / #STR-26", "formula": "#STR-yy = distinct STORE CODE with NSV > 0 in year yy", "body": "Count of trading stores. In the Total row this is a distinct count across the whole filter — it is not the sum of the rows."},
    {"id": "s-str_25", "alias_of": "s-str"}, {"id": "s-str_26", "alias_of": "s-str"},
    {"id": "s-panel", "title": "#PANEL-25 / #PANEL-26", "formula": "#PANEL-yy = Σ over trading stores of Σ over GRPCATs with NSV > 0 of weight, weight = 1.4 for HP MEN else 1.0", "body": "Panels (display units) in operation. A store selling BATA MEN + HP MEN counts 2.4 panels. Only stores with positive NSV in the year count. DAX: `SUMX(VALUES(STORE CODE), IF(StoreSales>0, SUMX(VALUES(GRPCAT), IF(sales>0, IF(GRPCAT=\"HP MEN\",1.4,1),0)),0))`."},
    {"id": "s-panel_25", "alias_of": "s-panel"}, {"id": "s-panel_26", "alias_of": "s-panel"},
    {"id": "s-est", "title": "EST (Target)", "formula": "EST = Σ over (store, week) of max(OVERALL TARGET) where YEAR = 2026", "body": "Weekly store targets from the SIS target template (available for weeks 14–26). Taking max per store-week avoids double counting the target that is repeated on every article row."},
    {"id": "s-est_g", "title": "EST G", "formula": "EST G = NSV-26 ÷ EST − 1", "body": "Achievement against target (−35% = 35% below target). Meaningful when the weeks in scope have targets — use the Week slicer or Latest Wk."},
    {"id": "s-prod", "title": "PROD/WK-25 / PROD/WK-26 (store productivity per week)", "formula": "PROD/WK-yy = NSV-yy ÷ distinct stores in yy ÷ distinct weeks in yy", "body": "Average NSV per store per week. Store count here includes every store with rows in the year (not only NSV > 0), matching the DAX `DISTINCTCOUNT(STORE CODE)`."},
    {"id": "s-prod_wk_25", "alias_of": "s-prod"}, {"id": "s-prod_wk_26", "alias_of": "s-prod"},
    {"id": "s-qty", "title": "QTY-25 / QTY-26 / QTY G / ASP", "formula": "QTY-yy = Σ QTY ; QTY G = (QTY-26 − QTY-25) ÷ QTY-25 ; ASP-yy = NSV-yy ÷ QTY-yy", "body": "Pairs sold and average selling price."},
    {"id": "s-qty_25", "alias_of": "s-qty"}, {"id": "s-qty_26", "alias_of": "s-qty"}, {"id": "s-qty_g", "alias_of": "s-qty"}, {"id": "s-asp_25", "alias_of": "s-qty"}, {"id": "s-asp_26", "alias_of": "s-qty"},
    {"id": "s-finance", "title": "Finance measures (Finance column set)", "formula": "MRP VAL = Σ MRP×QTY · GST VAL = Σ NSV − NSV÷(1+rate), rate 5% if unit NSV ≤ 2500 else 18% · TO = NSV − GST VAL + GST REVERSAL · DISC = MRP VAL − TO · DISC% = DISC ÷ MRP VAL", "body": "MARGIN VAL = Σ MRP×partner margin×QTY · PRIM BILLING-26 = MRP VAL − GST VAL − MARGIN VAL (2025 uses the SECONDARY-PRIMARY column) · GST REVERSAL = Σ [GST on MRP − GST on NSV] per row (1.05 / 1.18 factors below/above ₹2,500) · MARGIN REVERSAL = MARGIN VAL − Σ margin×NSV · REALIZED VALUE = PRIM BILLING − DISC + GST REVERSAL + MARGIN REVERSAL · COST VAL = Σ STDCOST×QTY · MARGIN% = (REALIZED − COST VAL) ÷ REALIZED · PRIM BILLING G and TO G are year-on-year growths. These are the exact DAX definitions from the Finance tab; they are pre-computed per row at load and summed."},
]
for _k in ("mrp_val_26", "disc_26", "disc_pct_26", "gst_val_26", "margin_val_26", "prim_billing_26", "gst_reversal_26", "margin_reversal_26", "realized_26", "cost_val_26", "margin_pct_26", "mrp_val_25", "disc_25", "disc_pct_25", "prim_billing_25", "realized_25", "margin_pct_25", "prim_billing_g", "to_g"):
    SIS_REPORT.append({"id": f"s-{_k}", "alias_of": "s-finance"})


def build_help():
    rules = [{"id": f"v-{r['code']}", "title": f"{r['code']} — {r['name']}", "body": f"**Severity:** {r['severity']}{' (blocking → row rejected)' if r['blocking'] else ' (row still loads)'}. {r['description']}." + (f" **Parameters:** `{r['params']}`." if r["params"] else "")} for r in DEFAULT_RULES]
    return {"sections": [
        {"id": "overview", "title": "Overview", "intro": "The Bata SIS Sales Intelligence Platform ingests weekly sales files from Bata's Shop-in-Shop retail partners, standardizes them into one Bata data model, validates every row, and reports on the result. The ingestion engine is deterministic (rules, alias dictionary, fuzzy match, learned memory) — no AI touches your data. Ask Bata (the analytics agent) only reads the finished reporting data.", "items": [
            {"id": "o-data", "title": "Data currently loaded", "body": "10 partners (CENTRO, INC 5, KORA, LIFESTYLE, LULU, R. CENTRAL, R. TRENDS, SHOPPERS, SPENCER, ZUUP), 551 stores with city / state / region / cluster manager, ~2.5k Bata articles, 2025 weekly sales history (Bata standard template) plus 2026 live weekly files, Q2 2026 store × GRPCAT weekly targets, Week-32 closing stock, partner margins."},
            {"id": "o-layers", "title": "Data layers", "body": "raw_files → raw_rows (as received) → std_rows (standardized, versioned, originals preserved) → sales (reporting) · exceptions · masters (partners, stores, articles, aliases, mappings, rules) · audit_logs · notifications."}]},
        {"id": "dashboard", "title": "Dashboard", "intro": "Every KPI and chart on the Dashboard and how it is computed.", "items": DASHBOARD},
        {"id": "sis", "title": "SIS Secondary Sales Report", "intro": "The Power BI SALES matrix rebuilt natively: hierarchy, slicers and every DAX measure, computed live.", "items": SIS_REPORT},
        {"id": "reports", "title": "Reports", "intro": "All 15 standard reports plus source-record drill-down. Standard metric columns on the sales reports: Qty = Σ quantity · Gross = Σ gross_amount · Discount = Σ discount · Net Sales = Σ net_amount · Txns = row count · Disc % · Avg Ticket. Totals row = Σ of the visible rows.", "items": REPORTS},
        {"id": "formulas", "title": "Formulas & Metrics", "intro": "Exact definitions used everywhere in the platform.", "items": FORMULAS},
        {"id": "pipeline", "title": "Ingestion Pipeline & Recognition", "intro": "How a file becomes reporting data.", "items": PIPELINE},
        {"id": "validation", "title": "Validation Rules", "intro": "Twelve rules run on every standardized row. Severity and parameters are editable under Masters → Validation Rules. Blocking rules reject the row; non-blocking rules flag a warning and the row still loads.", "items": rules},
        {"id": "exceptions", "title": "Exception Workbench", "intro": "Where flagged rows are resolved by people.", "items": EXCEPTIONS},
        {"id": "insights", "title": "Insights Engine", "intro": "Deterministic statistical anomaly rules. Every insight links to the records behind it.", "items": INSIGHTS},
        {"id": "roles", "title": "Roles & Permissions", "intro": "Three roles.", "items": ROLES},
        {"id": "ask", "title": "Ask Bata (Analytics Agent)", "intro": "", "items": ASK},
        {"id": "glossary", "title": "Glossary", "intro": "", "items": GLOSSARY},
    ]}


def help_text_for_agent():
    """Compact markdown of formulas + report catalogue for the agent system prompt."""
    lines = ["## Metric definitions (quote these exactly when asked how something is computed)"]
    for f in FORMULAS:
        lines.append(f"- **{f['title']}**: `{f['formula']}` — {f['body']}")
    lines.append("## Validation rules")
    for r in DEFAULT_RULES:
        lines.append(f"- {r['code']} ({r['severity']}{', blocking' if r['blocking'] else ''}): {r['description']} {r['params'] or ''}")
    lines.append("## SIS Secondary Sales report (tool sis_sales_report) — measure definitions")
    for f in SIS_REPORT:
        if f.get("formula"):
            lines.append(f"- **{f['title']}**: `{f['formula']}` — {f['body']}")
    lines.append("## Reports (keys for run_report)")
    for r in REPORTS:
        lines.append(f"- {r['id'][2:]}: {r['title']} — {r['body']}")
    lines.append("## Pipeline")
    for p in PIPELINE + EXCEPTIONS + INSIGHTS + ROLES + GLOSSARY:
        if p.get("alias_of"):
            continue
        lines.append(f"- {p['title']}: {p['body']}")
    return "\n".join(lines)


def search_help(query: str):
    q = (query or "").lower().split()
    out = []
    for s in build_help()["sections"]:
        for it in s["items"]:
            if it.get("alias_of"):
                continue
            text = f"{s['title']} {it['title']} {it.get('formula', '')} {it['body']}".lower()
            score = sum(text.count(w) for w in q)
            if score:
                out.append((score, {"section": s["title"], "anchor": it["id"], **{k: it[k] for k in ("title", "body") if k in it}, **({"formula": it["formula"]} if it.get("formula") else {})}))
    out.sort(key=lambda x: -x[0])
    return [o for _, o in out[:8]]
