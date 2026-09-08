"""Onboards the real Bata SIS templates (masters, 2025 history, targets, stock, margins) and ingests Week-32 partner files through the live pipeline."""
import logging
import os
import re
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from core.db import db
from core.auth import hash_password
from core.utils import now_iso, new_id
from core.audit import log_audit
from services.recognition import normalize
from services.validation import DEFAULT_RULES
from services import pipeline
from seed import GLOBAL_ALIASES

logger = logging.getLogger("seed_real")
DATA = Path(os.environ.get("SIS_DATA_DIR", "/app/data/sis/Stadnard Templates"))

PARTNERS = {  # CM name -> (code, filename keywords, week-32 file, pre-approved mapping (header prefix -> field) or None)
    "CENTRO": ("CENTRO", ["centro"], "Week 32 CENTRO.xlsx", {"Day of Billing": "sale_date", "Site": "store_code", "STORE NAME": "store_name", "SECTION": "category", "Style": "sku", "Brand Name": "brand", "COLOUR": "color", "SIZE": "size", "MRP": "mrp", "Total Discount": "discount", "POS Billing Quantity": "quantity", "POS Net Sales": "net_amount"}),
    "INC 5": ("INC5", ["inc5", "inc 5"], "Week 32 INC5.xlsx", {"Bill Date": "sale_date", "Branch Name": "store_code", "Style": "sku", "Brand": "brand", "Category": "category", "Color": "color", "Size": "size", "MRP": "mrp", "RSP": "unit_price", "Bill No": "invoice_no", "Bill Qty": "quantity", "ITEM DISCOUNT AMOUNT": "discount", "Tax Amount": "tax", "Bill Net Value": "net_amount"}),
    "KORA": ("KORA", ["kora"], "Week 32 KORA.xlsx", {"BILL DATE": "sale_date", "BRANCH NAME": "store_code", "BILL NO.": "invoice_no", "ITEM NAME": "sku", "CATEGORY": "category", "COMPANY NAME": "brand", "PACK / SIZE": "size", "NET QTY": "quantity", "NET AMOUNT": "net_amount"}),
    "LIFESTYLE": ("LIFESTYLE", ["lifestyle"], "Week 32 LIFESTYLE.csv", {"SALEDATE": "sale_date", "LOC_NUM": "store_code", "LOCATION_NAME": "store_name", "SHORT_DESC": "sku", "BRAND_DESC": "brand", "DEPT_NAME": "category", "COLOR_DESC": "color", "SIZE_DESC": "size", "QTY": "quantity", "SALMRP": "mrp", "TAX": "tax", "SALNOT": "net_amount"}),
    "LULU": ("LULU", ["lulu"], "Week 32 LULU.xlsx", {"Date": "sale_date", "Site": "store_code", "Brand": "brand", "MC Descriptiion": "category", "Article": "sku", "MRP": "mrp", "Sales at retail": "net_amount", "Tax Amount": "tax", "Sal Qty": "quantity", "Discount": "discount", "Bill. Doc.": "invoice_no"}),
    "R. CENTRAL": ("RCENTRAL", ["r central", "r_central", "central"], "Week 32 R_CENTRAL.xlsx", {"Billing Date": "sale_date", "Site": "store_code", "Site Name": "store_name", "Option Code": "sku", "Brand": "brand", "MH Segment": "category", "Size": "size", "Colour": "color", "POS Billing Quantity": "quantity", "POS Discount Amount": "discount", "POS Net Sales WOT": "net_amount", "POS Tax Amount": "tax"}),
    "R. TRENDS": ("RTRENDS", ["r trends", "r_trends", "trends"], "Week 32 R_TRENDS.xlsx", {"DAYCALANDER": "sale_date", "Site": "store_code", "Style Code": "sku", "Brand": "brand", "MH Segment": "category", "Size": "size", "Colour": "color", "MRP Tableau": "mrp", "NSQ": "quantity", "NOT": "net_amount", "POS Tax Amount": "tax", "POS Total Discount": "discount", "CITY": "city", "REGION": "region"}),
    "SHOPPERS": ("SHOPPERS", ["ssl", "shoppers"], "Week 32 SSL.xlsx", {"Selling Date": "sale_date", "Store No.": "store_code", "Location": "store_name", "Style Code": "sku", "Brand Name": "brand", "Sub Category": "category", "Colour Desc": "color", "Size Desc": "size", "Qty Sold": "quantity", "MRP Per Unit": "mrp", "Disc Amt": "discount", "Net Retail Value": "net_amount"}),
    "SPENCER": ("SPENCER", ["spencer", "srl"], None, None),
    "ZUUP": ("ZUUP", ["zuup"], "Week 32 ZUUP.xlsx", {"BILL DATE": "sale_date", "SHOW ROOM": "store_code", "ARTICLE  NAME": "sku", "BRAND": "brand", "CATEGORY": "category", "SHADE NAME": "color", "SIZE": "size", "SALE QTY": "quantity", "M.R.P.": "mrp", "RATE": "unit_price", "DISCOUNT VALUE": "discount", "NET SALE VALUE": "net_amount", "BILL NO.": "invoice_no"}),
}
CM2CODE = {k: v[0] for k, v in PARTNERS.items()}
MARGIN_NAME = {"INC5": "INC5"}


def _digits7(s):
    m = re.search(r"\b(\d{7})\b", str(s or ""))
    return m.group(1) if m else None


def _gender(code):
    d = str(code)[:1]
    return {"8": "Men", "5": "Women", "6": "Women", "7": "Women", "9": "Accessories"}.get(d, "Kids")


def _grpcat(brand, gender):
    b = (brand or "").upper()
    if "HUSH" in b or b == "HP":
        return "HP MEN" if gender == "Men" else "HP WOMEN" if gender == "Women" else "KIDS"
    if "FLOATZ" in b:
        return "FLOATZ"
    if gender == "Kids":
        return "KIDS"
    return "BATA MEN" if gender == "Men" else "BATA WOMEN" if gender == "Women" else "NFT"


def week_start(year, week):
    jan1 = date(year, 1, 1)
    return jan1 if week <= 1 else jan1 + timedelta(days=(7 - jan1.weekday()) + (week - 2) * 7)


async def seed():
    if await db.partners.count_documents({}) > 0:
        return
    if not DATA.exists():
        logger.error(f"SIS data dir {DATA} missing")
        return
    logger.info("Onboarding real Bata SIS templates...")
    now = now_iso()
    users = [("admin", os.environ.get("ADMIN_EMAIL", "admin@bata.com"), "Vineet Narang", "admin", os.environ.get("ADMIN_PASSWORD", "Admin@123")),
             ("ops", "ops@bata.com", "Priya Sharma", "ops", "Ops@123"), ("mgmt", "mgmt@bata.com", "Rahul Mehta", "management", "Mgmt@123")]
    for u, e, n, r, p in users:
        if not await db.users.find_one({"username": u}):
            await db.users.insert_one({"id": new_id(), "username": u, "email": e, "name": n, "role": r, "active": True, "password_hash": hash_password(p), "created_at": now, "created_by": "seed"})
    await db.settings.update_one({"key": "global"}, {"$set": {"key": "global", "thresholds": {"high": 90, "medium": 70}, "medium_behavior": "review", "currency": "INR", "restatement_mode": "review_then_supersede", "max_file_mb": 50,
                                                             "retention": "never_delete", "features": {}, "notification_channels": {"in_app": True, "email": False, "whatsapp": False}, "updated_at": now}}, upsert=True)
    for r in DEFAULT_RULES:
        await db.validation_rules.insert_one({**r, "id": new_id(), "enabled": True, "version": 1, "created_at": now, "created_by": "seed"})
    for field, arr in GLOBAL_ALIASES.items():
        for a in arr + (["show room", "showroom", "site", "site code", "loc num", "branch"] if field == "store_code" else []):
            await db.aliases.insert_one({"id": new_id(), "field": field, "alias": a, "alias_norm": normalize(a), "partner_code": None, "source": "system", "active": True, "created_at": now})
    # Partners + margins
    margins = pd.read_excel(DATA / "Margin Partner Level.xlsx")
    for cm_name, (code, kws, wfile, mapping) in PARTNERS.items():
        mg = {r["MARKET"]: float(r["MARGIN"]) for _, r in margins.iterrows() if str(r["Partner"]).upper().replace(" ", "") == cm_name.upper().replace(" ", "").replace("INC5", "INC5")}
        await db.partners.insert_one({"id": new_id(), "code": code, "name": cm_name, "active": True, "keywords": kws, "sender_domains": [], "sender_emails": [], "subject_patterns": [f"{cm_name} SIS Sales"],
                                      "partial_ingestion": True, "expected_frequency": "weekly", "date_format_hint": "", "expected_columns": list(mapping.keys()) if mapping else [], "store_code_prefix": "",
                                      "margins": mg, "source_template": wfile, "contact": {}, "notes": "Onboarded from SIS Automation Templates (Cluster Manager Mapping / Margin Partner Level)", "version": 1, "created_at": now, "created_by": "seed"})
        await db.margins.insert_many([{"id": new_id(), "partner_code": code, "partner_name": cm_name, "market": k, "margin": v, "created_at": now} for k, v in mg.items()] or [{"id": new_id(), "partner_code": code, "partner_name": cm_name, "market": "BATA", "margin": None, "created_at": now}])
    # Stores from Cluster Manager Mapping
    cm = pd.read_excel(DATA / "Cluster Manager Mapping.xlsx", dtype=str).fillna("")
    stores = []
    for _, r in cm.iterrows():
        code = CM2CODE.get(r["PARTNER"].strip())
        if not code:
            continue
        sc = r["STORE CODE"].strip()
        name = r["STORE NAME"].strip()
        aliases = [name] if code == "INC5" else []
        if code == "INC5" and " - " in name:
            aliases.append(name.split(" - ", 1)[1])
        stores.append({"id": new_id(), "partner_code": code, "code": sc, "name": name, "city": r["CITY"].strip().title(), "state": r["STATE"].strip().title(), "region": r["REGION"].strip().title(),
                       "cluster_manager": r["CLUSTER MANAGER"].strip().title(), "active": True, "aliases": aliases, "version": 1, "created_at": now, "created_by": "seed"})
    await db.stores.insert_many(stores)
    for city, region, state in {(s["city"], s["region"], s["state"]) for s in stores}:
        await db.geo_mapping.insert_one({"id": new_id(), "city": city, "region": region, "state": state, "active": True, "version": 1, "created_at": now})
    # 2025 history -> sales (weekly aggregated), one import batch per partner
    s25 = pd.read_excel(DATA / "2025_SALE_SIS.xlsx", dtype=str).fillna("")
    art_attr = {}
    store_by = {(s["partner_code"], s["code"]): s for s in stores}
    docs, batches = [], {}
    for _, r in s25.iterrows():
        code = CM2CODE.get(r["PARTNER"].strip())
        if not code:
            continue
        yr, wk = int(float(r["YEAR"])), int(float(r["WEEK"]))
        art = r["ART"].strip()
        qty = float(r["QTY"] or 0)
        nsv = float(r["NSV"] or 0)
        art_attr.setdefault(art, {"brand": None, "category": None})
        b = batches.get(code)
        if not b:
            bid = new_id()
            b = batches[code] = {"id": bid, "file_name": f"2025_SALE_SIS.xlsx [{r['PARTNER'].strip()}]", "file_size": int(os.path.getsize(DATA / "2025_SALE_SIS.xlsx")), "file_hash": f"import-2025-{code}", "source": "import", "uploaded_by": "admin",
                                 "partner_code": code, "partner_name": r["PARTNER"].strip(), "partner_selected": code, "status": "Successfully Processed", "status_history": [{"status": "Received", "at": now, "by": "admin"}, {"status": "Successfully Processed", "at": now, "by": "system"}],
                                 "counts": {"total": 0, "accepted": 0, "warning": 0, "rejected": 0, "duplicate": 0}, "confidence": 100, "confidence_level": "high", "notes": "Historical 2025 weekly SIS sales (Bata standard template) — bulk import", "created_at": now, "updated_at": now,
                                 "storage_path": None, "storage_backend": None, "reprocessed": False, "period": {"from": "2025-01-01", "to": "2025-12-31"}, "mapping_approved_by": "system (standard template)"}
        st = store_by.get((code, r["STORE CODE"].strip()), {})
        d = week_start(yr, wk).isoformat()
        docs.append({"id": new_id(), "batch_id": b["id"], "partner_code": code, "partner_name": r["PARTNER"].strip(), "store_code": r["STORE CODE"].strip(), "store_name": st.get("name") or r["STORE NAME"].strip(), "city": st.get("city"), "region": st.get("region"),
                     "cluster_manager": st.get("cluster_manager"), "sale_date": d, "month": d[:7], "year": yr, "week": wk, "sku": art, "article_name": art, "category": _grpcat(None, _gender(art)), "brand": "Bata", "size": r["SIZE"].strip(),
                     "quantity": qty, "mrp": None, "unit_price": round(nsv / qty, 2) if qty else None, "gross_amount": nsv, "discount": 0, "discount_pct": 0, "tax": 0, "net_amount": nsv, "invoice_no": None, "data_quality": "accepted",
                     "business_key": f"{code}|{r['STORE CODE']}|{d}|{art}|{r['SIZE']}|{qty}|{nsv}", "row_version": 1, "granularity": "weekly", "created_at": now})
        b["counts"]["total"] += 1
        b["counts"]["accepted"] += 1
    for b in batches.values():
        b["loaded_rows"] = b["counts"]["total"]
    await db.batches.insert_many(list(batches.values()))
    for i in range(0, len(docs), 5000):
        await db.sales.insert_many(docs[i:i + 5000])
    logger.info(f"2025 history loaded: {len(docs)} rows")
    # Stock + targets
    stock = pd.read_excel(DATA / "Stock Update.xlsx", dtype=str).fillna("")
    sdocs = []
    for _, r in stock.iterrows():
        code = CM2CODE.get(r["PARTNER"].strip())
        if not code:
            continue
        art = r["ART NO"].strip()
        art_attr.setdefault(art, {"brand": None, "category": None})
        st = store_by.get((code, r["STORE CODE"].strip()), {})
        sdocs.append({"id": new_id(), "partner_code": code, "partner_name": r["PARTNER"].strip(), "store_code": r["STORE CODE"].strip(), "store_name": st.get("name") or r["STORE NAME"].strip(), "region": st.get("region"), "sku": art, "size": r["ART_SIZE"].strip(),
                      "quantity": float(r["QTY"] or 0), "year": int(float(r["YEAR"])), "week": int(float(r["WEEK"])), "category": _grpcat(None, _gender(art)), "created_at": now})
    for i in range(0, len(sdocs), 5000):
        await db.stock.insert_many(sdocs[i:i + 5000])
    tg = pd.read_excel(DATA / "Targets Q2.xlsx", dtype=str).fillna("")
    tdocs = []
    for _, r in tg.iterrows():
        code = CM2CODE.get(r["PARTNER"].strip().upper().replace("LIFESTYLE", "LIFESTYLE"))
        if not code:
            continue
        st = store_by.get((code, r["STORE CODE"].strip()), {})
        tdocs.append({"id": new_id(), "partner_code": code, "partner_name": r["PARTNER"].strip().upper(), "store_code": r["STORE CODE"].strip(), "store_name": st.get("name") or r["STORE NAME"].strip(), "region": st.get("region"), "cluster_manager": r["CLUSTER MANAGER"].strip().title(),
                      "month": r["MONTH"].strip(), "week": int(float(r["WEEK"])), "year": 2026, "grpcat": r["GRPCAT"].strip(), "target": float(r["OVERALL TARGET"] or 0), "created_at": now})
    for i in range(0, len(tdocs), 5000):
        await db.targets.insert_many(tdocs[i:i + 5000])
    # Article master: enrich from week-32 files
    for cm_name, (code, kws, wfile, mapping) in PARTNERS.items():
        if not wfile or not mapping:
            continue
        try:
            sheets = pipeline.parse_file(wfile, (DATA / wfile).read_bytes())
        except Exception as e:
            logger.warning(f"could not pre-read {wfile}: {e}")
            continue
        from services.parser import detect_header_row, extract_rows
        rows_all = sheets[0]["rows"]
        hidx, _ = detect_header_row(rows_all, {normalize(k) for k in mapping}, normalize)
        headers, rows, _ = extract_rows(rows_all, hidx)
        col = {f: next((h for h in headers if normalize(h).startswith(normalize(p))), None) for p, f in mapping.items()}
        for r in rows:
            art = _digits7(r.get(col.get("sku")))
            if art:
                a = art_attr.setdefault(art, {"brand": None, "category": None})
                a["brand"] = a["brand"] or (str(r.get(col.get("brand"))).strip() if col.get("brand") and r.get(col.get("brand")) else None)
                a["category"] = a["category"] or (str(r.get(col.get("category"))).strip() if col.get("category") and r.get(col.get("category")) else None)
    skus = []
    for art, a in art_attr.items():
        g = _gender(art)
        brand = (a["brand"] or "Bata").title().replace("Hush Puppies", "Hush Puppies")
        skus.append({"id": new_id(), "code": art, "name": f"{brand} {a['category'].title() if a['category'] else g + ' footwear'} {art}", "category": _grpcat(brand, g), "sub_category": (a["category"] or "").title() or None, "brand": brand, "gender": g,
                     "mrp": None, "active": True, "aliases": [], "version": 1, "created_at": now, "created_by": "seed", "origin": "2025 sales / stock / week-32 files"})
    for i in range(0, len(skus), 5000):
        await db.skus.insert_many(skus[i:i + 5000])
    for cat in sorted({s["category"] for s in skus}):
        await db.product_hierarchy.insert_one({"id": new_id(), "code": cat.replace(" ", "_"), "division": "Footwear", "category": cat, "brands": sorted({s["brand"] for s in skus if s["category"] == cat}), "active": True, "version": 1, "created_at": now})
    # Pre-approved partner mappings (versioned) from the template study
    for cm_name, (code, kws, wfile, mapping) in PARTNERS.items():
        if not wfile or not mapping:
            continue
        sheets = pipeline.parse_file(wfile, (DATA / wfile).read_bytes())
        from services.parser import detect_header_row, extract_rows
        hidx, _ = detect_header_row(sheets[0]["rows"], {normalize(k) for k in mapping}, normalize)
        headers, _, _ = extract_rows(sheets[0]["rows"], hidx)
        actual = {}
        for p, f in mapping.items():
            h = next((h for h in headers if normalize(h) == normalize(p)), None) or next((h for h in headers if normalize(h).startswith(normalize(p))), None)
            if h:
                actual[h] = f
        await db.partner_mappings.insert_one({"id": new_id(), "partner_code": code, "version": 1, "active": True, "mapping": actual, "ignored_columns": [h for h in headers if h not in actual], "created_by": "admin", "source_batch_id": None, "created_at": now, "note": "Onboarding mapping derived from partner template"})
        for h, f in actual.items():
            await db.aliases.insert_one({"id": new_id(), "field": f, "alias": h, "alias_norm": normalize(h), "partner_code": code, "source": "learned", "active": True, "created_at": now})
    await log_audit("seed", "system.onboarded", "system", None, {"partners": len(PARTNERS), "stores": len(stores), "skus": len(skus), "history_rows": len(docs), "stock_rows": len(sdocs), "targets": len(tdocs)}, category="system")
    # Ingest Week 32 files through the live pipeline
    ops = await db.users.find_one({"username": "ops"}, {"_id": 0, "password_hash": 0})
    for cm_name, (code, kws, wfile, mapping) in PARTNERS.items():
        if not wfile:
            continue
        try:
            await pipeline.create_batch((DATA / wfile).read_bytes(), wfile, ops, None, "upload", "Week 32 submission", run_async=False)
        except Exception as e:
            logger.exception(f"ingest {wfile} failed: {e}")
    logger.info("Real-data onboarding complete")
