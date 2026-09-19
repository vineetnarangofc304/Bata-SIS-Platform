"""Builds the KAZO × Fundle techno-commercial proposal PDF from live screenshots. Run: python3 build_proposal.py"""
from pathlib import Path
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether, NextPageTemplate
from PIL import Image as PILImage

D = Path(__file__).parent / "kazo"
OUT = [D.parent / "KAZO_SIS_TechnoCommercial_Proposal_Fundle.pdf", Path("/app/frontend/public/proposal/KAZO_SIS_TechnoCommercial_Proposal_Fundle.pdf")]
RED, INK, GREY, LIGHT = colors.HexColor("#111111"), colors.HexColor("#111827"), colors.HexColor("#64748b"), colors.HexColor("#F1F5F9")
W, H = A4

st = {
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=INK, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=RED, spaceBefore=10, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=INK, spaceBefore=6, spaceAfter=2),
    "p": ParagraphStyle("p", fontName="Helvetica", fontSize=9.2, leading=13, textColor=colors.HexColor("#1f2937")),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=11, textColor=GREY),
    "b": ParagraphStyle("b", fontName="Helvetica", fontSize=9.2, leading=13, leftIndent=10, bulletIndent=0, textColor=colors.HexColor("#1f2937")),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.4, leading=11, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.4, leading=11, textColor=INK),
    "cover_t": ParagraphStyle("ct", fontName="Helvetica-Bold", fontSize=30, leading=36, textColor=colors.white),
    "cover_s": ParagraphStyle("cs", fontName="Helvetica", fontSize=13, leading=18, textColor=colors.HexColor("#cbd5e1")),
}


def P(t, s="p"):
    return Paragraph(t, st[s])


def bullets(items):
    return [Paragraph(f"• {i}", st["b"]) for i in items]


def shot(name, caption, width=170 * mm):
    p = D / name
    im = PILImage.open(p)
    h = width * im.size[1] / im.size[0]
    return KeepTogether([Image(str(p), width=width, height=h), Spacer(1, 2), P(caption, "small"), Spacer(1, 8)])


def table(rows, widths, header=True, zebra=True):
    data = [[Paragraph(str(c), st["cellb" if (header and i == 0) else "cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        data[0] = [Paragraph(f'<font color="white"><b>{c}</b></font>', st["cell"]) for c in rows[0]]
        t = Table(data, colWidths=widths, repeatRows=1)
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(style))
    return t


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(RED)
    canvas.rect(0, H - 6, W, 6, fill=1, stroke=0)
    canvas.drawImage(str(D / "kazo_logo.png"), 15 * mm, H - 21 * mm, width=24 * mm, height=6.8 * mm, mask="auto", preserveAspectRatio=True)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawRightString(W - 15 * mm, H - 16 * mm, "KAZO SIS Sales Intelligence Platform · Techno-Commercial Proposal")
    canvas.setFillColor(INK)
    canvas.rect(0, 0, W, 12 * mm, fill=1, stroke=0)
    canvas.drawImage(str(D / "fundle_logo_white.png"), W - 40 * mm, 3 * mm, width=25 * mm, height=6.5 * mm, mask="auto", preserveAspectRatio=True)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.drawString(15 * mm, 4.5 * mm, f"Confidential · Prepared for KAZO (Kazo Fashion Pvt. Ltd.) · {date.today().strftime('%d %b %Y')}")
    canvas.drawRightString(W - 45 * mm, 4.5 * mm, f"Page {doc.page}   ·   Powered by")
    canvas.restoreState()


def on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(RED)
    canvas.rect(0, H - 10 * mm, W, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.rect(20 * mm, H - 120 * mm, 3 * mm, 40 * mm, fill=1, stroke=0)
    # bata logo white-ish: draw on a white card
    canvas.setFillColor(colors.white)
    canvas.roundRect(20 * mm, H - 45 * mm, 60 * mm, 20 * mm, 3 * mm, fill=1, stroke=0)
    canvas.drawImage(str(D / "kazo_logo.png"), 25 * mm, H - 42.5 * mm, width=50 * mm, height=14 * mm, mask="auto", preserveAspectRatio=True)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.setFont("Helvetica", 10)
    canvas.drawString(20 * mm, 40 * mm, "Powered by")
    canvas.drawImage(str(D / "fundle_logo_white.png"), 20 * mm, 22 * mm, width=55 * mm, height=14.4 * mm, mask="auto", preserveAspectRatio=True)
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(W - 20 * mm, 62 * mm, f"Proposal date: {date.today().strftime('%d %B %Y')}   ·   Version 1.0   ·   Validity 30 days")
    canvas.drawRightString(W - 20 * mm, 56 * mm, "Prepared for: KAZO — Shop-in-Shop / Large-Format-Retail Secondary Sales")
    canvas.restoreState()


def build():
    for out in OUT:
        out.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT[0]), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=25 * mm, bottomMargin=18 * mm, title="KAZO SIS Sales Intelligence Platform — Techno-Commercial Proposal", author="Fundle")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="cover", frames=[Frame(20 * mm, 60 * mm, W - 40 * mm, H - 190 * mm, id="c")], onPage=on_cover), PageTemplate(id="body", frames=[frame], onPage=on_page)])
    s = []
    s += [Spacer(1, 30 * mm), P("SIS Sales Intelligence Platform", "cover_t"), Spacer(1, 4), P("Techno-Commercial Proposal", "cover_t"), Spacer(1, 10),
          P("Automated ingestion, standardisation, validation and reporting of Shop-in-Shop partner sales — with a native SIS Secondary Sales report, 15 standard reports, an AI analytics agent (Ask KAZO) and a full Help Center.", "cover_s"),
          NextPageTemplate("body"), PageBreak()]

    s += [P("1. Executive Summary", "h1"),
          P("KAZO's shop-in-shop and large-format-retail channel (Shoppers Stop, Lifestyle, Central, Pantaloons, Reliance Trends and other partners) sends weekly secondary-sales files in a different layout, naming and style/SKU coding per partner — and the formats drift every season. Today consolidation lives in spreadsheets and BI models that must be rebuilt by hand whenever a file changes."),
          Spacer(1, 4),
          P("Fundle proposes the <b>KAZO SIS Sales Intelligence Platform</b> — a proven, production-ready web application (screenshots in this document show the platform white-labelled to KAZO; figures shown are illustrative reference data and will be replaced by KAZO's own partner data at onboarding). It ingests any partner file, recognises its structure with a deterministic rules engine (no AI in the data path), validates every row against KAZO masters, routes exceptions to people, and publishes trusted, drill-able reporting — including a native <b>Secondary Sales matrix</b> (hierarchy, slicers, YoY, LTL, targets, productivity), an <b>Ask KAZO</b> conversational analytics agent and a Help Center that documents every number."),
          Spacer(1, 6),
          table([["Outcome", "What KAZO gets"],
                 ["One source of truth", "All partner secondary-sales history (current + last year), every SIS counter, the full style/SKU master, targets, stock and partner margins in a single governed data model"],
                 ["Zero-touch ingestion", "Drag-and-drop or email → recognised → validated → published in minutes, with confidence scoring and human approval only where needed"],
                 ["Trust", "Every aggregate traces to the batch and source row; financial values are never auto-corrected; complete audit log"],
                 ["Speed of insight", "Hero KPIs, 16 reports with filters/sorting/pagination/export, and plain-English questions answered from live data by Ask KAZO"],
                 ["Self-service clarity", "Help Center defines every KPI, formula and validation rule exactly as computed"]], [45 * mm, 125 * mm]),
          PageBreak()]

    s += [P("2. Scope Delivered — Modules & Functionality", "h1"), P("All modules below are built and running today. Screenshots show the live application in KAZO branding; partner names and figures are illustrative reference data until KAZO's files are onboarded.", "p"), Spacer(1, 6)]
    s += [P("2.1 Secure access & role model", "h2"), P("Username/e-mail + password login with bcrypt hashing, JWT sessions, brute-force lockout, password change, admin self-lockout protection and automatic administrator recovery. Three roles — <b>Administrator</b>, <b>Data Operations</b>, <b>Management</b> (read-only) — gate every screen and API."), Spacer(1, 4), shot("shot_login.jpeg", "Login — KAZO-branded, role-based entry.", 120 * mm)]
    s += [P("2.2 Executive Dashboard", "h2"), P("Month-to-date SIS sales (as of latest data), weekly target achievement, accepted-record ratio, pending actions; weekly trend (last year → current year), sales by partner, category mix, top articles, data-quality by partner and recent batches. Every card carries a “?” that opens the exact formula in the Help Center."), shot("shot_dashboard.jpeg", "Dashboard — KPIs and charts computed live from the reporting layer.")]
    s += [PageBreak(), P("2.3 Secondary Sales Report (Power BI-style matrix, rebuilt natively)", "h2"),
          P("A Power BI-style sales matrix implemented on the platform's own data model so it never depends on desktop refreshes. The fact table is built from KAZO's partner files and enriched with MRP, cost, partner margin, category/sub-category, cluster/area manager, city/state, LTL (like-to-like) status, top-store and existing/new flags and weekly targets."),
          Spacer(1, 3), *bullets([
              "<b>Hero bar</b>: NSV-26, NSV growth, LTL growth, EST target & EST G, #STR, #PANEL, PROD/WK, QTY & ASP, data window.",
              "<b>Dynamic hierarchy (5 levels)</b>: Partner, Area/Cluster Manager, State, Store Code/Name, City, Category, Sub-category, Style, Existing vs New, Top Stores, Month, Week, LTL — any combination, any order; one-click drill-down per row.",
              "<b>Slicers</b>: 13 cascading multi-select slicers + Till Date, Latest Month, Latest Week toggles + free-text search; shareable URL state.",
              "<b>Measures (all DAX logic reproduced)</b>: CONT %, #STR-25/26, #PANEL-LY/CY (configurable panel weights), NSV-25/26, NSV G, LTL G, EST, EST G, STORE PROD/WK-25/26, QTY-25/26, QTY G, ASP; Finance set: MRP VAL, DISC, DISC %, GST VAL, MARGIN VAL, PRIM BILLING, GST REVERSAL, MARGIN REVERSAL, REALIZED VALUE, COST VAL, MARGIN %, PRIM BILLING G, TO G.",
              "<b>Enterprise grid</b>: server-side computation (seconds on 200k+ rows), sortable columns, 50-row pagination, column sets (Sales / Finance / All) and column chooser, green/red growth colouring, distinct-count-aware totals row, CSV & Excel export honouring the current view."]),
          shot("shot_sis_sales.jpeg", "Secondary Sales matrix — hierarchy, slicers, hero KPIs and measure grid.")]
    s += [PageBreak(), P("2.4 Ingestion engine & batches", "h2"), P("Upload (xlsx/xls/csv, up to 50 MB) or mailbox pickup. Parser detects header rows, skips blank/total rows, coerces numbers/dates. The <b>recognition engine</b> identifies partner, header row and column mapping through learned mappings → exact KAZO field → alias dictionary → fuzzy match, and scores confidence (0.3 partner + 0.1 header + 0.6 columns). High confidence auto-accepts; medium/low routes to review. File-hash and business-key duplicate detection; restatements supersede prior batches only after approval; originals preserved in object storage."), shot("shot_batches.jpeg", "Ingestion Batches — hero counters, status, T·A·W·R·D row counts, confidence, download of the original file.")]
    s += [P("2.5 Validation & Exception Workbench", "h2"), P("Twelve configurable rules (required field, invalid/future date, unknown store, unknown SKU, negative/zero qty, invalid price, discount over limit, arithmetic mismatch, duplicate row, row-count anomaly, missing submission) with severity and blocking flags. Exceptions are worked by people: accept, correct (versioned), map to master (with remembered alias), add master, ignore, reject row/file, assign, comment, re-validate — individually or in bulk."), shot("shot_review.jpeg", "Review Queue — mapping approvals and the exception workbench.")]
    s += [PageBreak(), P("2.6 Standard reports & drill-down", "h2"), P("Fifteen reports (daily, monthly, partner, store, region, category, SKU, top/bottom, discount analysis, data-quality trend, missing-submission calendar, exception summary, target vs actual, stock position, partner margin) plus row-level Source Records. Filters, sorting, column selection, saved views, CSV/Excel export; every aggregate row drills to the exact source rows and batch."), shot("shot_reports.jpeg", "Sales Reports — Target vs Actual with drill-down to source records.")]
    s += [P("2.7 Ask KAZO — AI analytics agent", "h2"), P("A GPT-5.4 agent grounded in the platform: it never estimates — every figure comes from one of 16 live query tools (reports, ad-hoc aggregation, Secondary Sales measures, store-level targets, stock cover, margins, batches, exceptions, data quality, insights, Help Center). Answers stream with tables and insights; the queries executed are shown and expandable; conversations are saved per user; available as a full page and as a drawer on every screen. Read-only by design — the ingestion engine stays 100% rules-based."), shot("shot_ask_answer.jpeg", "Ask KAZO — question, executed query, tabular answer and analyst commentary.")]
    s += [PageBreak(), P("2.8 Masters & configuration", "h2"), P("Stores/SIS, articles, product hierarchy, geo mapping, alias dictionary, validation rules, sender rules — versioned, import/export, deactivate-not-delete. Partner configuration (keywords, frequency, partial-ingestion policy), confidence thresholds, notification channels, e-mail connector (Graph/Gmail/IMAP, encrypted credentials), users & roles."), shot("shot_masters.jpeg", "Masters — versioned reference data that drives recognition and validation.")]
    s += [P("2.9 Help Center", "h2"), P("Twelve sections / 100+ topics: every dashboard KPI, every report, all formulas (incl. every Secondary Sales measure), recognition confidence, validation rules, exception actions, insight rules, roles and glossary. Searchable, deep-linked from every “?” in the application, and used verbatim by Ask KAZO so explanations always match."), shot("shot_help.jpeg", "Help Center — formulas exactly as computed by the platform.")]
    s += [P("2.10 Also included", "h2"), *bullets(["Insights & anomalies: statistical spike/drop, underperforming stores, missing submissions, discount outliers, row-count anomalies, rejection-rate alerts — each linked to records.",
                                                    "Data Quality page: acceptance %, confidence and exceptions by partner and rule, 30-day trend.", "Notifications (in-app) and complete Audit Log with filters/search.",
                                                    "White-label KAZO branding (logo, palette, typography), OpenGraph/WhatsApp link previews, responsive desktop/tablet layout, data-testid coverage for automated QA."]), PageBreak()]

    s += [P("3. Technical Architecture & Stack", "h1"),
          table([["Layer", "Technology", "Notes"],
                 ["Frontend", "React 19, Tailwind CSS, shadcn/ui, Recharts, react-markdown", "SPA; role-gated routing; URL-state for shareable report views"],
                 ["Backend / API", "Python 3.11, FastAPI (async), Pydantic, Uvicorn", "REST under /api; JWT auth; SSE streaming for Ask KAZO"],
                 ["Database", "MongoDB (Motor async driver)", "Layers: raw_files → raw_rows → std_rows (versioned) → sales → exceptions; masters; audit_logs; indexes on all filter keys"],
                 ["Ingestion engine", "pandas, openpyxl/xlrd, rapidfuzz", "Deterministic: header detection, alias dictionary, fuzzy matching, learned mappings, 12 validation rules"],
                 ["Analytics", "MongoDB aggregation pipelines", "Server-side computation of all measures (distinct counts, panels, targets) — no pre-aggregated cubes"],
                 ["AI layer", "OpenAI GPT-5.4 via Emergent Universal Key, function-calling", "Read-only tools over the reporting DB; grounded system prompt; per-user sessions"],
                 ["Storage", "Managed object storage", "Original partner files kept immutable; download from batch"],
                 ["Security", "bcrypt, JWT (12 h), brute-force lockout, Fernet-encrypted connector secrets, role guards, audit trail", "HTTPS; CORS restricted; secrets in environment"],
                 ["Hosting", "Kubernetes-managed containers (frontend, API, DB), CI-style deploys", "Preview + production environments; horizontal scaling of API"],
                 ["Quality", "pytest engine tests, automated UI/API regression suites (7 iterations)", "Every release verified against critical flows"]], [30 * mm, 60 * mm, 80 * mm]),
          Spacer(1, 8), P("Data model (reporting)", "h3"), P("<b>secondary_sales</b>: partner, week, month, store_code, store_name, style, size, colour, nsv, qty, mrp, cost, category, sub_category, year, till_date, ltl, margin, area_manager, top_stores, existing_vs_new, city, state, target + pre-computed row components (mrp_val, cost_val, gst_val, gst_reversal, margin_val, margin_nsv, panel_w, ltl_nsv). <b>sales</b> (partner weekly files via pipeline) with full batch lineage. Masters: partners, stores/counters, styles/SKUs, targets, stock, margins, aliases, partner_mappings, validation_rules — all loaded from KAZO templates."),
          PageBreak()]

    s += [P("4. Computation Standards (extract from Help Center)", "h1"),
          table([["Measure", "Definition"],
                 ["NSV-yy", "Σ NSV where YEAR = yy (2025 / 2026)"], ["CONT %", "NSV-26 of row ÷ NSV-26 of all rows in filter"], ["NSV G / QTY G", "(value-26 − value-25) ÷ value-25"],
                 ["LTL G", "Growth on rows where LTL = 'LTL' (store has sales in the month in both years)"], ["#STR-yy", "Distinct stores with NSV > 0 in year"],
                 ["#PANEL-yy", "Σ over trading stores of Σ over categories with NSV > 0 of panel weight (configurable per category)"], ["EST / EST G", "Σ over (store, week) of max(target), YEAR 2026; EST G = NSV-26 ÷ EST − 1"],
                 ["PROD/WK-yy", "NSV-yy ÷ distinct stores ÷ distinct weeks"], ["GST VAL", "Σ NSV − NSV ÷ (1 + rate), rate 5 % if unit NSV ≤ 2,500 else 18 %"],
                 ["PRIM BILLING-26", "MRP VAL − GST VAL − MARGIN VAL (2025: SECONDARY-PRIMARY column)"], ["REALIZED VALUE", "PRIM BILLING − DISC + GST REVERSAL + MARGIN REVERSAL"],
                 ["MARGIN %", "(REALIZED VALUE − COST VAL) ÷ REALIZED VALUE"], ["Recognition confidence", "0.3 × partner + 0.1 × header + 0.6 × avg column; capped at 45 if a required field is unmapped"],
                 ["Acceptance %", "(accepted + warning rows) ÷ total rows"], ["Retail week", "Week 1 = 1 Jan → first Sunday, then Monday–Sunday (configurable to KAZO calendar)"]], [45 * mm, 125 * mm]),
          Spacer(1, 10), P("5. Hosting, AI Layer & Managed Service (covered by the monthly fee)", "h1"),
          *bullets(["<b>Hosting</b>: production Kubernetes environment (frontend, API, MongoDB), TLS, backups (daily, 30-day retention), monitoring and uptime alerts; 99.5 % monthly availability target.",
                    "<b>AI layer</b>: GPT-5.4 usage for Ask KAZO up to a fair-use pool of 1,000 questions/month; overage billed at cost.",
                    "<b>Object storage</b>: up to 25 GB of original partner files; retention as per KAZO policy (never delete by default).",
                    "<b>Support</b>: business-hours L2/L3 support (IST), 4-hour response for P1, monthly health report, security patches and dependency upgrades.",
                    "<b>Change absorption</b>: onboarding of new partner formats / alias updates / rule tuning up to 4 hours per month; new masters loads.",
                    "<b>Continuous improvement</b>: quarterly review with business owner; minor UI/report tweaks included."]),
          PageBreak()]

    s += [P("6. Commercials", "h1"),
          table([["Item", "Description", "Amount (INR)"],
                 ["One-time setup & implementation", "Discovery, KAZO data model & white-labelling, ingestion engine, up to 6 partner formats, masters onboarding (stores / styles / targets / margins from KAZO templates), dashboard, Secondary Sales matrix, 15 reports, Ask KAZO agent, Help Center, UAT support, production go-live, training (2 sessions)", "₹ 1,49,000"],
                 ["Monthly managed service", "Hosting & infrastructure, backups, monitoring, AI layer usage pool, object storage, L2/L3 support, security updates, format-drift absorption (4 h/month), quarterly reviews", "₹ 49,000 / month"]], [42 * mm, 98 * mm, 30 * mm]),
          Spacer(1, 6),
          P("Indicative first-year total: ₹ 1,49,000 + 12 × ₹ 49,000 = <b>₹ 7,37,000</b> (plus GST @ 18 %).", "p"), Spacer(1, 6),
          P("Payment terms", "h3"), *bullets(["One-time fee: 50 % on signing, 50 % on production go-live / UAT sign-off.", "Monthly fee: invoiced in advance on the 1st of each month; payable within 15 days.", "Minimum term 12 months; 60-day notice for termination thereafter; all data exported to KAZO on exit at no cost.", "Prices exclusive of GST and any third-party licences KAZO may choose (e.g. own OpenAI enterprise key, SSO IdP)."]),
          Spacer(1, 6), P("Optional add-ons (quoted separately)", "h3"),
          table([["Add-on", "Indicative"], ["Automated mailbox ingestion (Microsoft Graph / Gmail / IMAP) activation with KAZO mailbox credentials", "₹ 25,000 one-time"], ["Scheduled e-mail / WhatsApp digests & alerts (partner scorecards, missing submissions)", "₹ 35,000 one-time + messaging cost"],
                 ["Additional partner formats beyond 6", "₹ 8,000 per partner"], ["Additional BI tabs / custom dashboards rebuilt natively", "₹ 20,000 per tab"], ["ERP / POS push and BI (Power BI / Tableau) live connector", "₹ 60,000 one-time"], ["SSO (Azure AD / Google Workspace)", "₹ 25,000 one-time"], ["Weekly digest PDF / partner scorecard export", "₹ 15,000 one-time"]], [125 * mm, 45 * mm]),
          PageBreak()]

    s += [P("7. Out of Scope (current engagement)", "h1"),
          *bullets(["Live mailbox ingestion is built but inactive until KAZO provides mailbox credentials (add-on above).", "E-mail / WhatsApp / SMS delivery of notifications (in-app notifications are live).",
                    "Dashboards beyond the Secondary Sales matrix and the 15 standard reports (e.g. stock, incentive, finance visuals) — available as add-ons.", "Partner formats beyond the first 6 (add-on).",
                    "Primary-sales / ERP (SAP) integration, POS feeds, write-back to partner systems.", "Single sign-on, MFA hardware tokens, on-premise deployment.", "History prior to last financial year unless supplied by KAZO in the standard template.",
                    "Custom mobile apps (the web app is responsive for tablets).", "Changes to partner contracts / margin structures; the platform reflects the margin master supplied by KAZO."]),
          Spacer(1, 10), P("8. Assumptions & Acceptance", "h1"),
          *bullets(["KAZO provides partner files (min. 8 weeks of history per partner), masters and targets in the agreed templates and nominates a business owner for UAT sign-off within 10 working days.",
                    "Partner formats will continue to drift; the recognition engine and alias memory are designed for this and covered under the monthly service.",
                    "Model usage for Ask KAZO routed through the platform key; KAZO may substitute its own OpenAI key at any time.",
                    "Acceptance criteria: all modules in §2 available in production under KAZO branding, Secondary Sales totals reconcile to KAZO's existing partner statements for the same filters, automated regression suite green."]),
          Spacer(1, 10), P("9. Delivery Timeline", "h1"),
          table([["Phase", "Scope", "Status"], ["Week 1–2 — Setup & branding", "KAZO white-label, partner discovery, data model, masters templates", "Planned"], ["Week 3–4 — Data onboarding", "Up to 6 partner formats, stores, styles, targets, margins; history load", "Planned"],
                 ["Week 5 — Intelligence", "Secondary Sales matrix, Ask KAZO agent, Help Center configured to KAZO measures", "Planned"], ["Week 6 — UAT & go-live", "UAT, training (2 sessions), production go-live", "Planned"], ["Optional", "Mailbox ingestion, scheduled digests, extra tabs, BI connector", "On order"]], [45 * mm, 100 * mm, 25 * mm]),
          Spacer(1, 14), P("Prepared by <b>Fundle</b> for KAZO. We look forward to partnering with KAZO on making shop-in-shop data trusted, fast and self-service.", "p"),
          Spacer(1, 16), table([["For KAZO", "For Fundle"], ["Name / Title:\n\n\nSignature & date:", "Name / Title:\n\n\nSignature & date:"]], [85 * mm, 85 * mm], zebra=False)]
    doc.build(s)
    for out in OUT[1:]:
        out.write_bytes(OUT[0].read_bytes())
    print("written", [str(o) for o in OUT])


if __name__ == "__main__":
    build()
