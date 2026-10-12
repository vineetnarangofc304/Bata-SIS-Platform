"""Bata-facing solution overview (non-commercial): solution design, embedded AI, tech stack, AI model. Run: python3 build_bata_solution.py"""
from pathlib import Path
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, NextPageTemplate, KeepTogether
import build_proposal as bp
from build_proposal import P, bullets, shot, table, st, RED, INK, GREY

D = Path(__file__).parent
OUT = [D / "Bata_SIS_Platform_Solution_Overview_Fundle.pdf", Path("/app/frontend/public/proposal/Bata_SIS_Platform_Solution_Overview_Fundle.pdf")]
W, H = A4
TITLE = "SIS Sales Intelligence Platform · Solution Overview"


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(RED); canvas.rect(0, H - 6, W, 6, fill=1, stroke=0)
    canvas.drawImage(str(D / "bata_logo.png"), 15 * mm, H - 20 * mm, width=22 * mm, height=5 * mm, mask="auto", preserveAspectRatio=True)
    canvas.setFont("Helvetica", 8); canvas.setFillColor(GREY); canvas.drawRightString(W - 15 * mm, H - 16 * mm, TITLE)
    canvas.setFillColor(INK); canvas.rect(0, 0, W, 12 * mm, fill=1, stroke=0)
    canvas.drawImage(str(D / "fundle_logo_white.png"), W - 40 * mm, 3 * mm, width=25 * mm, height=6.5 * mm, mask="auto", preserveAspectRatio=True)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.drawString(15 * mm, 4.5 * mm, f"Prepared for Bata India Limited · {date.today().strftime('%d %b %Y')}")
    canvas.drawRightString(W - 45 * mm, 4.5 * mm, f"Page {doc.page}   ·   Powered by")
    canvas.restoreState()


def on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK); canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(RED); canvas.rect(0, H - 10 * mm, W, 10 * mm, fill=1, stroke=0); canvas.rect(20 * mm, H - 120 * mm, 3 * mm, 40 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white); canvas.roundRect(20 * mm, H - 45 * mm, 60 * mm, 20 * mm, 3 * mm, fill=1, stroke=0)
    canvas.drawImage(str(D / "bata_logo.png"), 26 * mm, H - 41 * mm, width=48 * mm, height=12 * mm, mask="auto", preserveAspectRatio=True)
    canvas.setFillColor(colors.HexColor("#94a3b8")); canvas.setFont("Helvetica", 10); canvas.drawString(20 * mm, 40 * mm, "Powered by")
    canvas.drawImage(str(D / "fundle_logo_white.png"), 20 * mm, 22 * mm, width=55 * mm, height=14.4 * mm, mask="auto", preserveAspectRatio=True)
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(W - 20 * mm, 62 * mm, f"{date.today().strftime('%d %B %Y')}   ·   Version 1.0")
    canvas.drawRightString(W - 20 * mm, 56 * mm, "Prepared for: Bata India Limited — SIS / Secondary Sales")
    canvas.restoreState()


AI_USE_CASES = [["Business question", "How the embedded AI answers it", "Growth lever"],
                ["Which partners / stores are behind Week-32 target and why?", "Ask Bata runs the store-level target drill (EST vs NSV, gap, achievement %) and ranks shortfalls by cluster manager and category", "Focus field effort where the gap is largest; weekly target cadence"],
                ["Where are we losing like-for-like growth?", "LTL G computed on stores trading in both years; agent isolates new vs closed vs LTL stores and the categories driving the decline", "Protect the base business; separate expansion from erosion"],
                ["Which SIS counters need more / fewer panels?", "#PANEL and store productivity per week (PROD/WK) vs partner median; HP MEN weighted; flags under-productive panels", "Re-allocate panels and space to productive counters"],
                ["Is stock in the right place?", "Weeks-of-cover by store × article from Week-32 stock vs sold; agent lists > 20-week cover and out-of-stock best-sellers", "Lower markdown risk, higher availability of best-sellers"],
                ["Is discounting eroding margin?", "Weighted discount %, discount outliers (mean + 2σ), partner margin and Bata net after margin per partner & market", "Tighter promo governance; margin-aware growth"],
                ["What is my best assortment per region / category?", "Ad-hoc aggregation by region × GRPCAT × article; top / bottom articles with pairs and ASP; category mix shifts", "Sharper buying & replenishment by region"],
                ["Are partner files complete and trustworthy?", "Data-quality view: acceptance %, confidence, open exceptions by rule; missing-submission calendar; anomaly alerts", "Decisions on clean data; fewer reconciliation cycles"],
                ["Explain this KPI to a new cluster manager", "Agent quotes the exact formula from the Help Center (same text the dashboards use)", "Faster onboarding; one definition across Bata"]]

STACK = [["Layer", "Technology", "Why"],
         ["Frontend", "React 19, Tailwind CSS, shadcn/ui, Recharts, react-markdown", "Fast enterprise UI, desktop & tablet, role-aware navigation, shareable URL state"],
         ["Backend / API", "Python 3.11, FastAPI (async), Pydantic, Uvicorn", "High-throughput REST under /api, JWT security, server-sent events for streaming AI answers"],
         ["Database", "MongoDB (Motor async driver)", "Flexible schema for drifting partner formats; aggregation pipelines compute every measure live"],
         ["Ingestion engine", "pandas, openpyxl / xlrd, rapidfuzz", "Deterministic parsing, alias dictionary, fuzzy header matching, learned mappings, 12 validation rules"],
         ["AI layer", "OpenAI GPT-5.4 (function calling, streaming) via Emergent Universal Key; emergentintegrations SDK", "Grounded analytics agent; read-only tools over the reporting DB; model is swappable (Azure OpenAI, Claude, Gemini)"],
         ["Storage", "Managed object storage", "Original partner files kept immutable for audit"],
         ["Security", "bcrypt, JWT (12 h), brute-force lockout, encrypted connector secrets, role guards, full audit log", "Enterprise-grade access control and traceability"],
         ["Hosting", "Kubernetes-managed containers (frontend, API, DB), TLS, daily backups", "Scales horizontally; preview + production environments"],
         ["Quality", "pytest engine tests + automated UI/API regression suites (11 iterations)", "Every release verified on critical flows"]]

MODEL = [["Aspect", "Detail"],
         ["Model", "OpenAI GPT-5.4 (latest reasoning-capable GPT family), accessed through the Emergent Universal Key; can be pointed at Bata's own Azure OpenAI / OpenAI enterprise key at any time"],
         ["Pattern", "Agentic function-calling: the model never sees raw tables up-front; it decides which of 16 governed tools to call (reports, ad-hoc aggregation, SIS measures, targets, stock, margins, batches, exceptions, data quality, insights, help), receives the results and composes the answer"],
         ["Grounding", "System brief = Bata business context + the exact formula definitions from the Help Center + live data coverage (dates, weeks, partners). Rule #1: never invent or extrapolate a number"],
         ["Transparency", "Every executed query is shown under the answer with its parameters and a data preview; conversations are saved per user; all questions are written to the audit log"],
         ["Safety & scope", "Read-only — the agent cannot upload, change mappings, masters or exceptions. The ingestion pipeline is 100 % rules-based; no AI touches partner data on the way in"],
         ["Data residency", "Only the tool results needed for an answer (aggregates, max 60 rows) are sent to the model; raw files and masters never leave the platform database"],
         ["Streaming & UX", "Answers stream token-by-token over SSE; available as a full page (/ask) and as a drawer on every screen; suggested questions for each role"],
         ["Roadmap", "Scheduled questions (Monday digest), answer → Excel export, proactive narrative insights on the dashboard, WhatsApp/e-mail delivery, optional Claude / Gemini models"]]


def build():
    for o in OUT:
        o.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT[0]), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=25 * mm, bottomMargin=18 * mm, title="Bata SIS Sales Intelligence Platform — Solution Overview", author="Fundle")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="cover", frames=[Frame(20 * mm, 60 * mm, W - 40 * mm, H - 190 * mm, id="c")], onPage=on_cover), PageTemplate(id="body", frames=[frame], onPage=on_page)])
    s = [Spacer(1, 30 * mm), P("SIS Sales Intelligence Platform", "cover_t"), Spacer(1, 4), P("Solution Overview for Bata", "cover_t"), Spacer(1, 10),
         P("How Bata's Shop-in-Shop partner data becomes one trusted, AI-assisted view — automated ingestion, validation and reporting, with an embedded analytics agent that turns questions into decisions.", "cover_s"),
         NextPageTemplate("body"), PageBreak()]

    s += [P("1. The challenge and the solution", "h1"),
          P("Bata's SIS channel receives weekly sales files from ten retail partners (Shoppers Stop, Lifestyle, Centro, Reliance Trends, Reliance Central, Lulu, Spencer's, KORA, INC 5, ZUUP). Every partner uses a different layout, naming and article coding, and formats drift. Consolidation has lived in spreadsheets and a Power BI model rebuilt by hand whenever a file changes — slow, fragile and hard to trust."),
          Spacer(1, 4),
          P("The <b>SIS Sales Intelligence Platform</b> replaces that with a governed pipeline: <b>ingest → recognise → validate → publish</b>. Files arrive by upload or mailbox, a deterministic rules engine recognises partner and columns with a confidence score, twelve validation rules check every row against Bata masters, people resolve only the exceptions, and the result is published to one reporting layer that powers the dashboard, the native rebuild of the <b>SIS Secondary Sales (Power BI Sales tab)</b>, fifteen standard reports, and <b>Ask Bata</b> — an AI analytics agent that answers plain-English questions from live data."),
          Spacer(1, 6),
          table([["Design principle", "What it means for Bata"],
                 ["Rules in, AI on top", "No AI touches partner data on the way in — ingestion is deterministic and auditable. AI is used where it adds value: analysis, explanation and insight"],
                 ["One definition of every number", "Every KPI and report formula is documented in the Help Center and the same text grounds the AI, so the dashboard, the report and the agent always agree"],
                 ["Trust and lineage", "Every aggregate drills to the source row and the originating file; financial values are never auto-corrected; complete audit log"],
                 ["Format drift absorbed", "Alias dictionary, fuzzy matching and learned mappings — a changed partner header becomes a 30-second review, not a rebuild"],
                 ["Self-service", "Cluster managers and management ask questions and get answers with the queries shown — no analyst queue"]], [45 * mm, 125 * mm]),
          PageBreak()]

    s += [P("2. Solution design — modules", "h1"), P("All screens below are live today, populated with Bata's actual SIS data (10 partners, 551 stores, ~4k articles, 2025 + 2026 weekly history, Q2 targets, Week-32 stock, partner margins).", "p"), Spacer(1, 6),
          P("2.1 Executive Dashboard", "h2"), P("Month-to-date SIS sales as of the latest data, Week-32 target achievement, accepted-record ratio, pending actions; weekly Bata-week trend, sales by partner, category mix, top articles, data quality by partner. Every card has a “?” that opens its exact formula."), shot("shot_dashboard.jpeg", "Dashboard — KPIs and charts computed live from the reporting layer."),
          PageBreak(), P("2.2 SIS Secondary Sales (Power BI Sales tab, native)", "h2"), P("218k rows of secondary sales rebuilt as a live matrix: hero KPIs (NSV-26, NSV G, LTL G, EST & EST G, #STR, #PANEL, PROD/WK, QTY/ASP), five-level dynamic hierarchy, thirteen cascading slicers, Till-Date / Latest-Month / Latest-Week toggles, sortable paginated grid, Sales / Finance column sets, drill-down and Excel export. Every DAX measure reproduced and documented."), shot("shot_sis_sales.jpeg", "SIS Secondary Sales — hierarchy, slicers, hero KPIs and measure grid."),
          PageBreak(), P("2.3 Ingestion, validation and exception workbench", "h2"), P("Upload or mailbox → parse (xlsx/xls/csv, header detection) → recognition (partner, header row, column mapping with confidence) → auto-accept or review → twelve validation rules → published. Duplicates and restatements handled; originals preserved. Exceptions are worked by people: accept, correct (versioned), map to master, add to master, ignore, reject, assign, comment — individually or in bulk."), shot("shot_batches.jpeg", "Ingestion batches — status, row counts, confidence, original file.", 150 * mm), shot("shot_review.jpeg", "Review queue — mapping approvals and exception workbench.", 150 * mm),
          PageBreak(), P("2.4 Standard reports, masters and governance", "h2"), P("Fifteen reports (daily, monthly, partner, store, region, category, SKU, top/bottom, discount, data-quality trend, missing submissions, exception summary, target vs actual, stock position, partner margin) with filters, sorting, export and drill-down to source rows. Versioned masters (stores, articles, aliases, rules), partner configuration, confidence thresholds, users & roles, audit log and in-app notifications."), shot("shot_reports.jpeg", "Sales Reports — Target vs Actual with drill-down."),
          P("2.5 Help Center", "h2"), P("Twelve sections, 100+ topics: every KPI, report, formula (including all SIS measures with their DAX equivalents), validation rule, exception action and role — searchable and deep-linked from every “?” in the product."), shot("shot_help.jpeg", "Help Center — formulas exactly as computed.", 150 * mm), PageBreak()]

    s += [P("3. AI embedded in the platform — how it helps the business grow", "h1"),
          P("<b>Ask Bata</b> is a conversational analytics agent built into every screen. It understands Bata's SIS business (partners, GRPCATs, Bata weeks, targets, panels, margins), knows every formula in the Help Center, and answers questions by running live queries on the same reporting data the dashboards use — never by guessing. Each answer shows the queries it ran, the resulting table and 2–4 analyst-style insights with suggested actions."),
          shot("shot_ask_answer.jpeg", "Ask Bata — question, executed query, tabular answer and analyst commentary."),
          P("3.1 Business questions it answers today", "h2"), table(AI_USE_CASES, [48 * mm, 74 * mm, 48 * mm]), Spacer(1, 8),
          P("3.2 Rule-based insights engine (always on)", "h2"),
          *bullets(["Sales spike / drop per partner (z-score > 2 or Δ > 40 % vs 14-day mean).", "Under-performing stores (< 50 % of partner store median).", "Missing submissions vs expected frequency; row-count anomalies; high rejection rates.", "Discount outliers (mean + 2σ) — each insight links to the records behind it."]),
          Spacer(1, 6), P("3.3 From insight to growth", "h2"),
          *bullets(["<b>Weekly target cadence</b>: cluster managers start Monday with the exact store gaps and the categories causing them.", "<b>Panel & space productivity</b>: move panels to counters that earn more per week; justify new SIS openings with LTL evidence.",
                    "<b>Availability of best-sellers</b>: stock cover by store × article stops lost sales on top articles and reduces markdowns on slow ones.", "<b>Margin-aware promotions</b>: see discount leakage and Bata net after partner margin before approving the next offer.",
                    "<b>Faster, consistent decisions</b>: one definition of every number, explained on demand — fewer reconciliation meetings, more selling time."]),
          PageBreak()]

    s += [P("4. Technology stack", "h1"), table(STACK, [30 * mm, 65 * mm, 75 * mm]), Spacer(1, 8),
          P("Data model (reporting layer)", "h3"), P("raw_files → raw_rows (as received) → std_rows (standardised, versioned, originals preserved) → <b>sales</b> (partner weekly files with batch lineage) and <b>sis_sales</b> (218,447 secondary-sales rows with pre-computed finance components) · exceptions · masters (partners, stores, articles, aliases, mappings, rules, targets, stock, margins) · audit_logs · notifications · chat_sessions."),
          Spacer(1, 10), P("5. AI model and governance", "h1"), table(MODEL, [35 * mm, 135 * mm]),
          Spacer(1, 12), P("Prepared by <b>Fundle</b> for Bata India Limited.", "p")]
    doc.build(s)
    for o in OUT[1:]:
        o.write_bytes(OUT[0].read_bytes())
    print("written", [str(o) for o in OUT])


if __name__ == "__main__":
    build()
