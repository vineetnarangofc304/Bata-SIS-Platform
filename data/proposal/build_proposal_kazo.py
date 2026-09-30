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


KAZO_REPORTS = [
    ("Broken / Non-Broken Size Report (AW26)", "Broken-Non-Broken report 20-Sep AW26.xlsb — 41k SKU-store rows",
     "Store × Option size availability: sizes in stock (XS S M L XL / 26–36), size length, Full-Size vs Broken status, with and without in-transit; cuts by Zone, Store Grade (A+/A/B/C/FO), Option Grade, Category/Sub-category, Season; store count by grade.",
     "Broken = option present in store with fewer than the full size set (size table drives Full/Broken); Cut/Full ratio per store & grade; option count with/without in-transit."),
    ("Buying vs Plan (AW26)", "Buying Vs Plan AW26 20-Sep.xlsb — base data, projections, size ratio, replenishment, in-transit, stock",
     "Option-wise buy plan vs actual: EBO buy qty, in-store date, ageing days & bucket, Store SOH, WH qty, in-transit, STD sale qty / revenue, STR %, ROS, monthly projected sale & closing (Sep–Nov), secured sale, projected STR %, discount budget, target achievement buckets, Top-10 options, size-wise stock ratio vs sale ratio (size gap), replenishment list.",
     "STR % = Sale ÷ (Sale + Closing stock) · ROS = Sale qty ÷ selling days · Proj. sale = ROS × days × ageing factor (age-bucket table) · Days cover = SOH ÷ ROS · Size gap = Sale ratio − Stock ratio · Tgt Ach % = STD sale ÷ STD target."),
    ("L2L Sale Data (Sep'26)", "L2L Sale Data Sep'26.xlsx — 21 sheets: Sep'26 vs Sep'25 sale, opening/closing stock, day-wise & option-wise targets, offer list, wardrobe, in-transit",
     "Like-to-like store performance: Sep'26 vs Sep'25 gross sale, qty, bills by store / zone / ASM; day-wise target vs achievement %; option-wise targets; opening vs closing stock and inward; sale & stock summary by category; live offer list per option.",
     "L2L growth = (CY − LY) ÷ LY for stores operational in both periods (Store Master L2L flag) · Day Ach % = actual ÷ day target · Stock movement = Opening + Inward − Sale − Transfers = Closing."),
    ("Product Review — Weekly Dashboard", "Product Review 20-Sep.xlsb — weekly dashboard, SOH size matrix, IST, aging & grade",
     "Per sub-category weekly review: STD sale qty & gross, option count, Top-5 styles by qty and revenue, ageing buckets (<30, 30–60, 60–90, 90–120, 120+ days) with inventory mix, sales mix and sell-out %; A+/A option list; store × option SOH size matrix; inter-store transfer (IST) suggestions donor → receiver; WH in-transit.",
     "Sell-out % = Sale qty ÷ (Sale qty + Inventory) per ageing bucket · Mix % = bucket ÷ total · Option grade from ROS/STR ranking · IST = broken sizes in receiver matched with surplus in donor."),
    ("Sell-Through — Category & Store", "Sell Through Category Level and Store- 13.Sep.xlsb",
     "Sell-through by category and by store with drop-down selection; stock (SOH) vs sale since season launch (06-Jun'26).",
     "Sell Through = Sale qty ÷ (Sale qty + Stock qty)."),
    ("Offer Analysis — ATV / UPT week-on-week", "Offer Analysis ATV 15-Sep & 21-Sep.xlsb",
     "Zone-wise comparison of offer weeks vs previous weeks: bill count, qty, gross sale, discount %, ASP, UPT, discount value and growth.",
     "ATV = Gross ÷ Bills · UPT = Qty ÷ Bills · ASP = Gross ÷ Qty · Dis % = Discount ÷ MRP value."),
    ("Offer Analysis — Buy 2 Get 30% Off", "Buy 2 get 30% off Analysis 9-Sep & 21-Sep.xlsx",
     "Last week vs this week during the offer: qty, gross, discount % by zone; store-wise and product-wise qty growth; bill-level detail.",
     "Qty growth = This week − Last week; offer uplift by store and style."),
    ("Pujo Offer Analysis & Pujo Working", "Pujo Offer Analysis.xlsb · Pujo Working 17th-Aug'26.xlsx",
     "Festive (Pujo) performance for East stores: Pujo'24 vs Pujo'25 gross, qty, bills, ABS, ASP, avg MRP, discount, ATV; bill-value buckets (e.g. 10K & above); plan for Pujo'26 — store × category opening SOH, option count, inward, mix, STR %, projected sale, avg MRP vs ASP.",
     "ABS = Qty ÷ Bills · ATV = Gross ÷ Bills · Projection = LY sale × growth assumption; SOH adequacy = plan qty vs opening SOH."),
    ("Footfall Aug'25 vs Aug'26", "Footfall Aug'25 vs Aug'26.xlsx",
     "Store-wise footfall by grade and zone with growth %, feeding conversion (bills ÷ footfall) once POS bills are joined.",
     "Growth % = (Aug'26 − Aug'25) ÷ Aug'25 · Conversion = Bills ÷ Footfall."),
]
KAZO_DATA = [["Source", "Content seen in the files", "Platform treatment"],
             ["POS / BC sales dump", "Bill-level lines: store, ASM, zone, date, receipt & invoice, customer, season, occasion, category, sub-category, HSN, SKU/option/variant, colour, size, qty, MRP, discount, gross, tax", "Daily automated ingestion → standardised fact `sales_lines`; drives L2L, offers, ATV/UPT, sell-through, product review"],
             ["Stock (SOH) extract", "SKU × location qty with unit price/cost, discount %, MRP value, season group, zone, option & store grade, store MDQ", "Daily snapshot → `stock_snapshots`; drives broken-size, ageing, STR %, days cover, size ratio"],
             ["Transfer orders / in-transit", "TO number, posting date, from/to location, qty, value at cost & MRP", "→ `transfers`; in-transit added to availability; IST recommendations"],
             ["Item master (102k SKUs)", "SKU, option, item no., variant, colour, size/new size, barcode, price, cost (NAV/BC), brand, main category, category, sub-category, actual/current season, discount %", "Versioned master with duplicate/cost-mismatch checks (the file's 'Duplicacy Check' and 'Diff-Nav/BC' columns become validation rules)"],
             ["Store master (≈65 EBOs + LFR)", "Location code, name, status, old/new grade, type, state, zone, cluster/ASM, MDQ, city, L2L flag", "Versioned master; grade and MDQ history kept for like-to-like comparisons"],
             ["Targets & plans", "Day-wise store targets, option-wise targets, buy plan (EBO buy qty, re-order qty/date), offer list per option", "→ `targets`, `buy_plan`, `offers`; achievement and buying-vs-plan measures"],
             ["Footfall", "Store × month footfall", "→ `footfall`; conversion KPI"]]


def kazo_reports_section():
    out = [P("3. KAZO Reporting Suite — analysed and in scope", "h1"),
           P("Fundle reviewed the 12 working files shared by KAZO (Kazo Files.zip — Report folder and Offer Analysis sub-folder). Today these are hand-built Excel/XLSB workbooks refreshed from Business Central / POS extracts, each carrying its own copy of the sales dump, stock, item and store masters. The platform replaces them with one governed data model and rebuilds every report as a live, filterable screen with hero KPIs, drill-down, pagination and Excel export — the same engine already shown in §2.3. Every formula is documented in the Help Center.", "p"), Spacer(1, 6),
           P("3.1 Source data identified in the files", "h2"), table(KAZO_DATA, [32 * mm, 78 * mm, 60 * mm]), Spacer(1, 8),
           P("3.2 Reports to be delivered (one screen each, same filters/sorting/hero-bar pattern)", "h2")]
    for i, (name, src, what, formulas) in enumerate(KAZO_REPORTS, 1):
        out.append(KeepTogether([P(f"3.2.{i} {name}", "h3"), P(f"<i>Source: {src}</i>", "small"), P(what, "p"), Spacer(1, 2), P(f"<b>Key computations:</b> {formulas}", "p"), Spacer(1, 4)]))
    out += [Spacer(1, 6), P("3.3 Common dimensions & slicers across the KAZO suite", "h2"),
            P("Zone (Delhi NCR, North, Upper North, East, West, South) · ASM / Cluster · Store & Store Grade (A+, A, B, C, FO) · Location type (EBO / LFR / Online) · L2L status · Category → Sub-category → Option → SKU/Size · Option Grade (A+…E) · Season / Season Group (AW26, SS26, OSM, In-season) · Ageing bucket · Date / Week / Month · Offer / Remarks. Standard measures: Sale Qty, Gross Sale, MRP Value, Discount & Dis %, Bills, ATV, UPT, ABS, ASP, SOH, In-transit, WH Qty, STR %, ROS, Days Cover, Sell-out %, Ach %, Growth %."),
            Spacer(1, 6), P("3.4 Automation that removes the manual work", "h2"),
            *bullets(["Scheduled pulls of the BC/POS sales, stock and transfer extracts (SFTP / mailbox / API) with the same recognition & validation engine — no more copy-paste of 40k-row dumps into each workbook.",
                      "Single item & store master with versioning; grade changes and MDQ revisions tracked, so L2L and grade-wise views stay consistent across reports.",
                      "Ageing, broken-size, STR and projection routines run nightly; alerts for options crossing ageing thresholds, stores with broken A+/A options, offer weeks under-performing, stores below day target.",
                      "Ask KAZO answers questions across all of the above (e.g. 'which A+ options are broken in Delhi NCR A+ stores?') from the same data."]),
            PageBreak()]
    return out


def build():
    for out in OUT:
        out.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT[0]), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=25 * mm, bottomMargin=18 * mm, title="KAZO SIS Sales Intelligence Platform — Techno-Commercial Proposal", author="Fundle")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="cover", frames=[Frame(20 * mm, 60 * mm, W - 40 * mm, H - 190 * mm, id="c")], onPage=on_cover), PageTemplate(id="body", frames=[frame], onPage=on_page)])
    s = []
    s += [Spacer(1, 30 * mm), P("SIS Sales Intelligence Platform", "cover_t"), Spacer(1, 4), P("Techno-Commercial Proposal", "cover_t"), Spacer(1, 10),
          P("Automated ingestion, standardisation, validation and reporting of KAZO EBO, LFR and partner sales & stock — the KAZO reporting suite rebuilt as live screens, 15 standard reports, an AI analytics agent (Ask KAZO) and a full Help Center.", "cover_s"),
          NextPageTemplate("body"), PageBreak()]

    s += [P("1. Executive Summary", "h1"),
          P("KAZO runs ~65 exclusive brand outlets plus large-format-retail and online counters. Sales, stock, transfer and master extracts from Business Central / POS are pulled into a dozen hand-maintained workbooks every week — Broken/Non-Broken sizes, Buying vs Plan, L2L, Product Review, Sell-Through, Offer and Pujo analyses, Footfall — each with its own copy of the data, its own pivots and its own risk of error. Partner (LFR) files add a second set of formats that drift every season."),
          Spacer(1, 4),
          P("Fundle proposes the <b>KAZO SIS Sales Intelligence Platform</b> — a proven, production-ready web application (screenshots in this document show the platform white-labelled to KAZO; figures shown are illustrative reference data and will be replaced by KAZO's own partner data at onboarding). It ingests every extract and partner file, recognises its structure with a deterministic rules engine (no AI in the data path), validates every row against KAZO masters, routes exceptions to people, and publishes trusted, drill-able reporting — the native <b>Sales matrix</b> (hierarchy, slicers, YoY, L2L, targets, productivity), the full <b>KAZO reporting suite rebuilt as live screens (§3)</b>, an <b>Ask KAZO</b> conversational analytics agent and a Help Center that documents every number."),
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

    s += kazo_reports_section()
    s += [P("4. Technical Architecture & Stack", "h1"),
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

    s += [P("5. Computation Standards (extract from Help Center)", "h1"),
          table([["Measure", "Definition"],
                 ["NSV-yy", "Σ NSV where YEAR = yy (2025 / 2026)"], ["CONT %", "NSV-26 of row ÷ NSV-26 of all rows in filter"], ["NSV G / QTY G", "(value-26 − value-25) ÷ value-25"],
                 ["LTL G", "Growth on rows where LTL = 'LTL' (store has sales in the month in both years)"], ["#STR-yy", "Distinct stores with NSV > 0 in year"],
                 ["#PANEL-yy", "Σ over trading stores of Σ over categories with NSV > 0 of panel weight (configurable per category)"], ["EST / EST G", "Σ over (store, week) of max(target), YEAR 2026; EST G = NSV-26 ÷ EST − 1"],
                 ["PROD/WK-yy", "NSV-yy ÷ distinct stores ÷ distinct weeks"], ["GST VAL", "Σ NSV − NSV ÷ (1 + rate), rate 5 % if unit NSV ≤ 2,500 else 18 %"],
                 ["PRIM BILLING-26", "MRP VAL − GST VAL − MARGIN VAL (2025: SECONDARY-PRIMARY column)"], ["REALIZED VALUE", "PRIM BILLING − DISC + GST REVERSAL + MARGIN REVERSAL"],
                 ["MARGIN %", "(REALIZED VALUE − COST VAL) ÷ REALIZED VALUE"], ["Recognition confidence", "0.3 × partner + 0.1 × header + 0.6 × avg column; capped at 45 if a required field is unmapped"],
                 ["Acceptance %", "(accepted + warning rows) ÷ total rows"], ["Retail week", "Week 1 = 1 Jan → first Sunday, then Monday–Sunday (configurable to KAZO calendar)"]], [45 * mm, 125 * mm]),
          Spacer(1, 10), P("6. Hosting, AI Layer & Managed Service (covered by the monthly fee)", "h1"),
          *bullets(["<b>Hosting</b>: production Kubernetes environment (frontend, API, MongoDB), TLS, backups (daily, 30-day retention), monitoring and uptime alerts; 99.5 % monthly availability target.",
                    "<b>AI layer</b>: GPT-5.4 usage for Ask KAZO up to a fair-use pool of 1,000 questions/month; overage billed at cost.",
                    "<b>Object storage</b>: up to 25 GB of original partner files; retention as per KAZO policy (never delete by default).",
                    "<b>Support</b>: business-hours L2/L3 support (IST), 4-hour response for P1, monthly health report, security patches and dependency upgrades.",
                    "<b>Change absorption</b>: onboarding of new partner formats / alias updates / rule tuning up to 4 hours per month; new masters loads.",
                    "<b>Continuous improvement</b>: quarterly review with business owner; minor UI/report tweaks included."]),
          PageBreak()]

    s += [P("7. Commercials", "h1"),
          table([["Item", "Description", "Amount (INR)"],
                 ["One-time setup & implementation", "Discovery, KAZO data model & white-labelling, ingestion of BC/POS sales, stock, transfer, item & store master extracts plus up to 6 partner formats, dashboard, Sales matrix, 15 standard reports, the 9 KAZO reports in §3 (Broken/Non-Broken, Buying vs Plan, L2L, Product Review, Sell-Through, Offer ATV/UPT, Buy-2-Get-30, Pujo, Footfall), Ask KAZO agent, Help Center, UAT, go-live, training (2 sessions)", "₹ 1,49,000"],
                 ["Monthly managed service", "Hosting & infrastructure, backups, monitoring, AI layer usage pool, object storage, L2/L3 support, security updates, format-drift absorption (4 h/month), quarterly reviews", "₹ 49,000 / month"]], [42 * mm, 98 * mm, 30 * mm]),
          Spacer(1, 6),
          P("Indicative first-year total: ₹ 1,49,000 + 12 × ₹ 49,000 = <b>₹ 7,37,000</b> (plus GST @ 18 %).", "p"), Spacer(1, 6),
          P("Payment terms", "h3"), *bullets(["One-time fee: 50 % on signing, 50 % on production go-live / UAT sign-off.", "Monthly fee: invoiced in advance on the 1st of each month; payable within 15 days.", "Minimum term 12 months; 60-day notice for termination thereafter; all data exported to KAZO on exit at no cost.", "Prices exclusive of GST and any third-party licences KAZO may choose (e.g. own OpenAI enterprise key, SSO IdP)."]),
          Spacer(1, 6), P("Optional add-ons (quoted separately)", "h3"),
          table([["Add-on", "Indicative"], ["Automated mailbox ingestion (Microsoft Graph / Gmail / IMAP) activation with KAZO mailbox credentials", "₹ 25,000 one-time"], ["Scheduled e-mail / WhatsApp digests & alerts (partner scorecards, missing submissions)", "₹ 35,000 one-time + messaging cost"],
                 ["Additional partner formats beyond 6", "₹ 8,000 per partner"], ["Additional BI tabs / custom dashboards rebuilt natively", "₹ 20,000 per tab"], ["ERP / POS push and BI (Power BI / Tableau) live connector", "₹ 60,000 one-time"], ["SSO (Azure AD / Google Workspace)", "₹ 25,000 one-time"], ["Weekly digest PDF / partner scorecard export", "₹ 15,000 one-time"]], [125 * mm, 45 * mm]),
          PageBreak()]

    s += [P("8. Out of Scope (current engagement)", "h1"),
          *bullets(["Live mailbox ingestion is built but inactive until KAZO provides mailbox credentials (add-on above).", "E-mail / WhatsApp / SMS delivery of notifications (in-app notifications are live).",
                    "Reports beyond the 9 KAZO reports in §3 and the 15 standard reports (add-on per tab).", "Partner formats beyond the first 6 (add-on).", "Write-back to Business Central (e.g. auto-creating transfer orders from IST suggestions) — recommendations are exported for manual posting.",
                    "Primary-sales / ERP (SAP) integration, POS feeds, write-back to partner systems.", "Single sign-on, MFA hardware tokens, on-premise deployment.", "History prior to last financial year unless supplied by KAZO in the standard template.",
                    "Custom mobile apps (the web app is responsive for tablets).", "Changes to partner contracts / margin structures; the platform reflects the margin master supplied by KAZO."]),
          Spacer(1, 10), P("9. Assumptions & Acceptance", "h1"),
          *bullets(["KAZO provides partner files (min. 8 weeks of history per partner), masters and targets in the agreed templates and nominates a business owner for UAT sign-off within 10 working days.",
                    "Partner formats will continue to drift; the recognition engine and alias memory are designed for this and covered under the monthly service.",
                    "Model usage for Ask KAZO routed through the platform key; KAZO may substitute its own OpenAI key at any time.",
                    "Acceptance criteria: all modules in §2 available in production under KAZO branding, Secondary Sales totals reconcile to KAZO's existing partner statements for the same filters, automated regression suite green."]),
          Spacer(1, 10), P("10. Delivery Timeline", "h1"),
          table([["Phase", "Scope", "Status"], ["Week 1–2 — Setup & branding", "KAZO white-label, partner discovery, data model, masters templates", "Planned"], ["Week 3–4 — Data onboarding", "BC/POS sales, stock, transfers, item & store masters, targets, buy plan; up to 6 partner formats; history load", "Planned"], ["Week 4–6 — KAZO report suite", "9 reports of §3 rebuilt as live screens with hero KPIs, slicers, drill-down, export", "Planned"],
                 ["Week 6 — Intelligence", "Sales matrix, Ask KAZO agent, Help Center configured to KAZO measures", "Planned"], ["Week 7 — UAT & go-live", "UAT, training (2 sessions), production go-live", "Planned"], ["Optional", "Mailbox ingestion, scheduled digests, extra tabs, BI connector", "On order"]], [45 * mm, 100 * mm, 25 * mm]),
          Spacer(1, 14), P("Prepared by <b>Fundle</b> for KAZO. We look forward to partnering with KAZO on making shop-in-shop data trusted, fast and self-service.", "p"),
          Spacer(1, 16), table([["For KAZO", "For Fundle"], ["Name / Title:\n\n\nSignature & date:", "Name / Title:\n\n\nSignature & date:"]], [85 * mm, 85 * mm], zebra=False)]
    doc.build(s)
    for out in OUT[1:]:
        out.write_bytes(OUT[0].read_bytes())
    print("written", [str(o) for o in OUT])


if __name__ == "__main__":
    build()
