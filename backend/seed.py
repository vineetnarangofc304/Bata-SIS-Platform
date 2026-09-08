import io
import logging
import os
import random
from datetime import datetime, timezone, timedelta
from openpyxl import Workbook
from core.db import db
from core.auth import hash_password
from core.utils import now_iso, new_id
from core.audit import log_audit
from services.recognition import normalize, CANONICAL_FIELDS
from services.validation import DEFAULT_RULES
from services import pipeline

logger = logging.getLogger("seed")
R = random.Random(42)

PARTNERS = [
    ("SS", "Shoppers Stop", ["shoppers", "shoppersstop", "sstop"], "shoppersstop.com", {"sale_date": "Bill Date", "store_code": "Store Code", "store_name": "Store Name", "sku": "Article Code", "article_name": "Article Description", "quantity": "Qty", "mrp": "MRP", "unit_price": "Selling Price", "discount": "Discount", "tax": "GST Amount", "net_amount": "Net Amount", "invoice_no": "Bill No"}),
    ("LS", "Lifestyle", ["lifestyle", "landmark"], "landmarkgroup.com", {"sale_date": "Transaction Date", "store_code": "Location Code", "store_name": "Location", "sku": "Vendor Article No", "article_name": "Item Description", "quantity": "Sold Qty", "mrp": "MRP", "unit_price": "Unit Price", "discount": "Promo Discount", "tax": "Tax Amt", "net_amount": "Net Sales Value", "invoice_no": "Receipt No"}),
    ("CN", "Central", ["central", "future retail"], "futureretail.in", {"sale_date": "Dt", "store_code": "Outlet", "sku": "Item Ref", "quantity": "Nos", "unit_price": "Rate", "discount": "Less", "tax": "GST", "net_amount": "Amt", "invoice_no": "Doc"}),
    ("PN", "Pantaloons", ["pantaloons", "abfrl"], "abfrl.adityabirla.com", {"sale_date": "Sales Date", "store_code": "Store ID", "store_name": "Store", "sku": "EAN / Article", "article_name": "Description", "quantity": "Quantity", "mrp": "MRP", "unit_price": "Price", "discount": "Discount Value", "tax": "Tax", "net_amount": "Net Value", "invoice_no": "Invoice Number"}),
    ("RT", "Reliance Trends", ["reliance", "trends", "rtl"], "ril.com", {"sale_date": "Date of Sale", "store_code": "Site Code", "store_name": "Site Name", "sku": "Article No", "article_name": "Article Desc", "quantity": "Sale Qty", "mrp": "MRP", "unit_price": "Sale Price", "discount": "Disc Amt", "tax": "Tax Amount", "net_amount": "Net Sales", "invoice_no": "Bill Number"}),
    ("WS", "Westside", ["westside", "trent"], "trent-tata.com", {"sale_date": "Txn Date", "store_code": "Branch Code", "store_name": "Branch", "sku": "Style Code", "article_name": "Style Name", "quantity": "Units Sold", "mrp": "MRP", "unit_price": "Selling Price", "discount": "Markdown", "tax": "GST", "net_amount": "Net Amount", "invoice_no": "Bill No"}),
    ("MX", "Max Fashion", ["max", "maxfashion"], "maxfashion.in", {"sale_date": "Date", "store_code": "Store Code", "store_name": "Store Name", "sku": "Article Code", "article_name": "Article Name", "quantity": "Qty", "mrp": "MRP", "unit_price": "Unit Price", "discount": "Discount Amount", "tax": "Tax Amount", "net_amount": "Net Amount", "invoice_no": "Invoice No"}),
    ("BF", "Brand Factory", ["brand factory", "brandfactory"], "brandfactoryonline.com", {"sale_date": "Bill Date", "store_code": "Store Code", "store_name": "Store Name", "sku": "Article Code", "article_name": "Article Description", "quantity": "Qty", "mrp": "MRP", "unit_price": "Selling Price", "discount": "Discount", "tax": "GST Amount", "net_amount": "Net Amount", "invoice_no": "Bill No"}),
    ("VM", "Vishal Mega Mart", ["vishal", "vmm"], "vishalmegamart.com", {"sale_date": "Day", "store_code": "Br Code", "sku": "Prod Id", "quantity": "Units", "unit_price": "Price", "discount": "Off", "net_amount": "Value", "invoice_no": "Slip"}),
]
CITIES = [("Mumbai", "West", "Maharashtra"), ("Delhi", "North", "Delhi"), ("Bengaluru", "South", "Karnataka"), ("Kolkata", "East", "West Bengal"), ("Chennai", "South", "Tamil Nadu"),
          ("Hyderabad", "South", "Telangana"), ("Pune", "West", "Maharashtra"), ("Ahmedabad", "West", "Gujarat"), ("Lucknow", "North", "Uttar Pradesh"), ("Jaipur", "North", "Rajasthan")]
SKUS = [("Men's Formal", "Bata", "Bata Ambassador Derby", 2499), ("Men's Formal", "Bata", "Bata Boss-Grip Loafer", 1999), ("Men's Casual", "Bata", "Bata Comfit Slip-on", 1799),
        ("Men's Casual", "North Star", "North Star Canvas Sneaker", 1299), ("Men's Casual", "Weinbrenner", "Weinbrenner Trail Boot", 3499), ("Women's Sandals", "Bata", "Bata Sunshine Flat Sandal", 999),
        ("Women's Sandals", "Marie Claire", "Marie Claire Strappy Sandal", 1499), ("Women's Heels", "Marie Claire", "Marie Claire Block Heel", 1999), ("Women's Casual", "Bata", "Bata Red Label Ballerina", 1299),
        ("Women's Casual", "Bata", "Bata Comfit Wedge", 1699), ("Sports", "Power", "Power Glide Runner", 2299), ("Sports", "Power", "Power Xorise Trainer", 2799),
        ("Sports", "Power", "Power Walkers Pro", 1999), ("Kids School", "Bubblegummers", "Bubblegummers School Shoe", 899), ("Kids Casual", "Bubblegummers", "Bubblegummers Velcro Sneaker", 799),
        ("Kids School", "Bata", "Bata Naughty Boy School", 999), ("Premium", "Hush Puppies", "Hush Puppies Bounce Oxford", 4999), ("Premium", "Hush Puppies", "Hush Puppies Zero-G Slip-on", 5499),
        ("Wellness", "Scholl", "Scholl Comfort Slider", 1599), ("Accessories", "Bata", "Bata Shoe Care Kit", 349), ("Accessories", "Bata", "Bata Leather Belt", 699),
        ("Men's Casual", "Bata", "Bata Chappal Classic", 499), ("Women's Sandals", "Bata", "Bata Kolhapuri Flat", 799), ("Sports", "North Star", "North Star Sport Sandal", 1099)]
GLOBAL_ALIASES = {
    "sale_date": ["bill date", "transaction date", "txn date", "sales date", "date of sale", "invoice date", "date", "trans date", "sale dt", "billing date", "billing day", "day of billing", "day of billing date"],
    "store_code": ["store code", "location code", "store id", "site code", "branch code", "outlet code", "shop code", "sis code", "store no", "loc code"],
    "store_name": ["store name", "location", "location name", "store", "site name", "branch", "branch name", "outlet name", "shop name"],
    "sku": ["article code", "vendor article no", "ean / article", "article no", "style code", "item code", "sku code", "sku", "article", "product code", "ean", "art no", "vendor sku", "item no"],
    "article_name": ["article description", "item description", "description", "article desc", "style name", "article name", "product name", "item name", "product description"],
    "category": ["category", "product category", "dept", "department", "class"],
    "size": ["size", "shoe size", "sz"],
    "quantity": ["qty", "sold qty", "quantity", "sale qty", "units sold", "qty sold", "sales qty", "units", "pcs", "no of units", "quantity sold"],
    "mrp": ["mrp", "list price", "max retail price", "mrp value"],
    "unit_price": ["selling price", "unit price", "price", "sale price", "sp", "rate per unit", "asp", "unit rate", "selling rate"],
    "discount": ["discount", "promo discount", "discount value", "disc amt", "markdown", "discount amount", "disc", "promo", "discount amt", "less amount"],
    "tax": ["gst amount", "tax amt", "tax", "tax amount", "gst", "cgst sgst", "igst", "total tax"],
    "net_amount": ["net amount", "net sales value", "net value", "net sales", "net amt", "total amount", "net", "invoice value", "sales value", "net sale amount"],
    "invoice_no": ["bill no", "receipt no", "invoice number", "bill number", "invoice no", "bill", "receipt", "transaction no", "doc no", "invoice"],
    "transaction_id": ["transaction id", "txn id", "trans id", "pos txn id"],
    "city": ["city", "town"], "region": ["region", "zone", "area"],
}


def _today():
    return datetime.now(timezone.utc).date()


def _row(partner_code, store, sku, d, rng, inv):
    q = rng.choice([1, 1, 1, 2, 2, 3])
    pct = rng.choice([0, 0, 0, 10, 10, 20, 25, 30, 40])
    price = sku["mrp"]
    gross = q * price
    disc = round(gross * pct / 100, 2)
    tax = round((gross - disc) * 0.12, 2)
    return {"sale_date": d.strftime("%Y-%m-%d"), "store_code": store["code"], "store_name": store["name"], "sku": sku["code"], "article_name": sku["name"],
            "quantity": q, "mrp": price, "unit_price": price, "discount": disc, "tax": tax, "net_amount": round(gross - disc + tax, 2), "invoice_no": f"{partner_code}{d.strftime('%y%m%d')}{inv:04d}"}


def to_xlsx(headers_map, rows, intro=None, totals=True, order=None, date_fmt=None, sheet_name="Sales"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    for line in intro or []:
        ws.append(line)
    keys = order or list(headers_map.keys())
    ws.append([headers_map[k] for k in keys])
    for r in rows:
        out = []
        for k in keys:
            v = r.get(k)
            if k == "sale_date" and date_fmt and v and len(str(v)) == 10 and str(v)[4] == "-":
                v = datetime.strptime(v, "%Y-%m-%d").strftime(date_fmt)
            out.append(v)
        ws.append(out)
    if totals:
        ws.append([])
        ws.append(["Grand Total"] + [None] * (len(keys) - 3) + [sum(r.get("quantity") or 0 for r in rows if isinstance(r.get("quantity"), (int, float))), None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_csv(headers_map, rows, order=None):
    keys = order or list(headers_map.keys())
    lines = [",".join(headers_map[k] for k in keys)]
    for r in rows:
        lines.append(",".join("" if r.get(k) is None else f'"{r[k]}"' if "," in str(r[k]) else str(r[k]) for k in keys))
    return "\n".join(lines).encode("utf-8")


async def seed():
    if await db.partners.count_documents({}) > 0:
        return
    logger.info("Seeding Bata SIS synthetic data...")
    now = now_iso()
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@bata.com")
    admin_pw = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    users = [("admin", admin_email, "Vineet Narang", "admin", admin_pw), ("ops", "ops@bata.com", "Priya Sharma", "ops", "Ops@123"), ("mgmt", "mgmt@bata.com", "Rahul Mehta", "management", "Mgmt@123")]
    for u, e, n, r, p in users:
        if not await db.users.find_one({"username": u}):
            await db.users.insert_one({"id": new_id(), "username": u, "email": e, "name": n, "role": r, "active": True, "password_hash": hash_password(p), "created_at": now, "created_by": "seed"})
    await db.settings.update_one({"key": "global"}, {"$set": {"key": "global", "thresholds": {"high": 90, "medium": 70}, "medium_behavior": "review", "currency": "INR",
                                                             "restatement_mode": "review_then_supersede", "max_file_mb": 50, "retention": "never_delete",
                                                             "features": {"email_ingestion": False, "scheduled_reports": False, "whatsapp": False, "erp_pos": False, "bi": False, "llm_insights": False},
                                                             "notification_channels": {"in_app": True, "email": False, "whatsapp": False}, "updated_at": now}}, upsert=True)
    for r in DEFAULT_RULES:
        await db.validation_rules.insert_one({**r, "id": new_id(), "enabled": True, "version": 1, "created_at": now, "created_by": "seed"})
    for field, arr in GLOBAL_ALIASES.items():
        for a in arr:
            await db.aliases.insert_one({"id": new_id(), "field": field, "alias": a, "alias_norm": normalize(a), "partner_code": None, "source": "system", "active": True, "created_at": now})
    skus = []
    for i, (cat, brand, name, mrp) in enumerate(SKUS):
        code = f"{8210000 + i * 37 + 101}"
        gender = "Men" if "Men" in cat else "Women" if "Women" in cat else "Kids" if "Kids" in cat else "Unisex"
        doc = {"id": new_id(), "code": code, "name": name, "category": cat, "sub_category": name.split()[-1], "brand": brand, "gender": gender, "mrp": mrp, "active": True, "aliases": [], "version": 1, "created_at": now, "created_by": "seed"}
        skus.append(doc)
    await db.skus.insert_many([dict(s) for s in skus])
    hier = {}
    for s in skus:
        hier.setdefault(s["category"], set()).add(s["brand"])
    for cat, brands in hier.items():
        await db.product_hierarchy.insert_one({"id": new_id(), "code": normalize(cat).replace(" ", "_").upper(), "division": "Footwear" if cat != "Accessories" else "Accessories", "category": cat, "brands": sorted(brands), "active": True, "version": 1, "created_at": now})
    for city, region, state in CITIES:
        await db.geo_mapping.insert_one({"id": new_id(), "city": city, "region": region, "state": state, "active": True, "version": 1, "created_at": now})
    partners, stores_by = [], {}
    for code, name, kws, domain, headers in PARTNERS:
        p = {"id": new_id(), "code": code, "name": name, "active": True, "keywords": kws, "sender_domains": [domain], "sender_emails": [f"sis.reports@{domain}"], "subject_patterns": [f"{name} SIS Sales"],
             "partial_ingestion": code != "RT", "expected_frequency": "daily", "date_format_hint": "dd/mm/yyyy", "expected_columns": list(headers.values()), "store_code_prefix": code,
             "contact": {"name": f"{name} SIS Desk", "email": f"sis.reports@{domain}"}, "notes": "Placeholder configuration - edit when real format is supplied", "version": 1, "created_at": now, "created_by": "seed"}
        partners.append(p)
        await db.partners.insert_one(dict(p))
        await db.sender_rules.insert_one({"id": new_id(), "partner_code": code, "pattern": f"*@{domain}", "match_type": "sender_domain", "priority": 10, "active": True, "version": 1, "created_at": now})
        await db.sender_rules.insert_one({"id": new_id(), "partner_code": code, "pattern": f"{name} SIS Sales*", "match_type": "subject", "priority": 20, "active": True, "version": 1, "created_at": now})
        sts = []
        for i in range(5):
            city, region, state = CITIES[(i * 2 + len(code)) % len(CITIES)]
            st = {"id": new_id(), "partner_code": code, "code": f"{code}{i + 1:03d}", "name": f"{name} {city} {'Mall' if i % 2 else 'Highstreet'}", "city": city, "region": region, "state": state,
                  "active": True, "aliases": [], "sis_area_sqft": R.choice([250, 300, 400, 500]), "version": 1, "created_at": now, "created_by": "seed"}
            sts.append(st)
            await db.stores.insert_one(dict(st))
        stores_by[code] = sts
    today = _today()
    hist_from, hist_to = today - timedelta(days=62), today - timedelta(days=4)
    for p in partners:
        headers = next(h for c, _, _, _, h in PARTNERS if c == p["code"])
        d = hist_from
        while d <= hist_to:
            wk_end = min(d + timedelta(days=6), hist_to)
            rows, dd, inv = [], d, 1
            weight = {"SS": 1.4, "LS": 1.3, "RT": 1.2, "WS": 1.0, "PN": 1.0, "MX": 0.9, "CN": 0.8, "BF": 0.6, "VM": 0.5}[p["code"]]
            while dd <= wk_end:
                n = max(1, int(R.gauss(3 * weight * (1.3 if dd.weekday() >= 5 else 1), 1)))
                for st in stores_by[p["code"]]:
                    for _ in range(n):
                        rows.append(_row(p["code"], st, R.choice(skus), dd, R, inv))
                        inv += 1
                dd += timedelta(days=1)
            bid = new_id()
            created = datetime.combine(wk_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=R.randint(6, 11))
            batch = {"id": bid, "file_name": f"{p['code'].lower()}_sis_sales_{d.strftime('%Y%m%d')}_{wk_end.strftime('%Y%m%d')}.xlsx", "file_size": 20000 + len(rows) * 90, "file_hash": new_id().replace("-", "") * 2,
                     "source": "upload", "uploaded_by": "ops", "partner_code": p["code"], "partner_name": p["name"], "partner_selected": p["code"], "status": "Successfully Processed",
                     "status_history": [{"status": s, "at": (created + timedelta(seconds=i * 20)).isoformat(), "by": "ops" if i == 0 else "system"} for i, s in enumerate(["Received", "Analysing", "Validating", "Successfully Processed"])],
                     "counts": {"total": len(rows), "accepted": len(rows), "warning": 0, "rejected": 0, "duplicate": 0}, "confidence": R.randint(92, 100), "confidence_level": "high",
                     "period": {"from": d.strftime("%Y-%m-%d"), "to": wk_end.strftime("%Y-%m-%d")}, "selected_sheet": "Sales", "header_row": 0, "headers": list(headers.values()),
                     "column_mappings": [{"index": i, "source_column": h, "proposed_field": f, "confidence": 100, "reason": "Known alias", "action": "map", "sample_values": []} for i, (f, h) in enumerate(headers.items())],
                     "created_at": created.isoformat(), "updated_at": created.isoformat(), "processed_at": created.isoformat(), "loaded_rows": len(rows), "reprocessed": False,
                     "mapping_approved_by": "system (auto-accept)", "storage_path": None, "storage_backend": None, "notes": "Historical seed batch (synthetic)"}
            await db.batches.insert_one(batch)
            docs = []
            for r in rows:
                st = next(s for s in stores_by[p["code"]] if s["code"] == r["store_code"])
                sk = next(s for s in skus if s["code"] == r["sku"])
                std = {"id": new_id(), "raw_row_id": new_id(), "values": r, "status": "accepted", "version": 1, "resolved_store": st, "resolved_sku": sk, "business_key": f"{p['code']}|{r['store_code']}|{r['sale_date']}|{r['sku']}|{r['invoice_no']}|{r['quantity']}|{r['net_amount']}"}
                docs.append(pipeline.sales_doc(std, batch, p))
            for i in range(0, len(docs), 2000):
                await db.sales.insert_many(docs[i:i + 2000])
            d = wk_end + timedelta(days=1)
    await log_audit("seed", "system.seeded", "system", None, {"partners": len(partners), "skus": len(skus)}, category="system")
    await seed_demo_scenarios(partners, stores_by, skus)
    logger.info("Seed complete")


async def seed_demo_scenarios(partners, stores_by, skus):
    today = _today()
    d1, d2 = today - timedelta(days=2), today - timedelta(days=1)
    ops = await db.users.find_one({"username": "ops"}, {"_id": 0, "password_hash": 0})
    H = {c: h for c, _, _, _, h in PARTNERS}
    rng = random.Random(7)

    def rows_for(code, d, n, mutate=None):
        out, inv = [], 1
        for i in range(n):
            r = _row(code, rng.choice(stores_by[code]), rng.choice(skus), d, rng, inv)
            inv += 1
            if mutate:
                mutate(i, r)
            out.append(r)
        return out

    async def ingest(name, data, partner=None):
        b = await pipeline.create_batch(data, name, ops, partner, "upload", None, run_async=False)
        return await db.batches.find_one({"id": b["id"]}, {"_id": 0, "id": 1, "status": 1})

    # 1. Correct Shoppers Stop file: intro rows, blank line, totals row
    ss_rows = rows_for("SS", d1, 24)
    ss_bytes = to_xlsx(H["SS"], ss_rows, intro=[["Shoppers Stop - SIS Sales Report"], [f"Vendor: Bata India Ltd  |  Period: {d1}"], []], date_fmt="%d/%m/%Y")
    await ingest(f"ShoppersStop_SIS_Sales_{d1.strftime('%d%m%Y')}.xlsx", ss_bytes)
    # 2. Lifestyle with reordered columns
    ls_rows = rows_for("LS", d1, 20)
    order = ["invoice_no", "net_amount", "sale_date", "sku", "article_name", "quantity", "store_code", "store_name", "unit_price", "mrp", "discount", "tax"]
    await ingest(f"Lifestyle_SIS_{d1}.xlsx", to_xlsx(H["LS"], ls_rows, order=order, date_fmt="%d-%b-%Y"))
    # 3. Lifestyle renamed columns (CSV, numbers as text with commas)
    renamed = {**H["LS"], "quantity": "Qty Sold", "net_amount": "Net Sale Amount", "sku": "Art No", "sale_date": "Trans Date"}
    ls2 = rows_for("LS", d2, 19, lambda i, r: r.update({"net_amount": f"{r['net_amount']:,.2f}", "unit_price": f"₹{r['unit_price']:,}"}))
    await ingest(f"lifestyle_daily_{d2}.csv", to_csv(renamed, ls2))
    # 4. Westside with unknown SKUs
    def bad_sku(i, r):
        if i in (3, 11):
            r["sku"], r["article_name"] = "9990001", "Unlisted Promo Sandal"
        if i == 17:
            r["sku"] = f"{r['sku'][:3]}-{r['sku'][3:]}"
    await ingest(f"Westside_Bata_SIS_{d1}.xlsx", to_xlsx(H["WS"], rows_for("WS", d1, 18, bad_sku), date_fmt="%d.%m.%Y"))
    # 5. Pantaloons unknown store (different code format)
    def bad_store(i, r):
        if i in (2, 9, 15):
            r["store_code"], r["store_name"] = "PNT-MUM-01", "Pantaloons Mumbai Highstreet"
    await ingest(f"Pantaloons_SIS_Sales_{d1}.xlsx", to_xlsx(H["PN"], rows_for("PN", d1, 18, bad_store), date_fmt="%Y-%m-%d"))
    # 6. Duplicate of the Shoppers Stop file
    await ingest(f"ShoppersStop_SIS_Sales_{d1.strftime('%d%m%Y')}_resend.xlsx", ss_bytes)
    # 7. Reliance Trends with invalid dates (strict partner: partial ingestion OFF -> Failed)
    def bad_date(i, r):
        if i == 4:
            r["sale_date"] = "31/02/2026"
        if i == 12:
            r["sale_date"] = "N/A"
        if i == 20:
            r["sale_date"] = (today + timedelta(days=20)).strftime("%d/%m/%Y")
    await ingest(f"Reliance_Trends_SIS_{d1}.xlsx", to_xlsx(H["RT"], rows_for("RT", d1, 22, bad_date), date_fmt="%d/%m/%Y"))
    # 8. Max Fashion mixed valid / invalid rows
    def mixed(i, r):
        if i == 1:
            r["quantity"] = -2
        if i == 6:
            r["discount"] = round(r["quantity"] * r["unit_price"] * 0.85, 2)
        if i == 10:
            r["net_amount"] = round(r["net_amount"] + 250, 2)
        if i == 14:
            r["unit_price"] = 0
        if i == 22:
            r["store_code"] = None
    await ingest(f"MaxFashion_SIS_{d1}.xlsx", to_xlsx(H["MX"], rows_for("MX", d1, 24, mixed), date_fmt="%d-%m-%Y"))
    # 9. Central low-confidence headers -> Awaiting Review -> ops approves with remember
    cn_rows = rows_for("CN", d1, 14)
    b9 = await ingest(f"Central_SIS_Sales_{d1}.xlsx", to_xlsx(H["CN"], cn_rows, date_fmt="%d/%m/%Y"))
    if b9["status"] == "Awaiting Review":
        mappings = [{"source_column": h, "field": f, "action": "map"} for f, h in H["CN"].items()]
        await pipeline.approve_mapping(b9["id"], mappings, True, ops)
    # 10. Central next day: same odd headers -> recognised via learned mapping
    await ingest(f"Central_SIS_Sales_{d2}.xlsx", to_xlsx(H["CN"], rows_for("CN", d2, 15), date_fmt="%d/%m/%Y"))
    # 11. Vishal Mega Mart unknown headers -> stays in review queue
    await ingest(f"VMM_Bata_{d2.strftime('%d%m%y')}.xlsx", to_xlsx(H["VM"], rows_for("VM", d2, 10), date_fmt="%d/%m/%Y"))
    # 12. Shoppers Stop next day, high confidence, straight through
    await ingest(f"ShoppersStop_SIS_Sales_{d2.strftime('%d%m%Y')}.xlsx", to_xlsx(H["SS"], rows_for("SS", d2, 25), intro=[["Shoppers Stop - SIS Sales Report"], []], date_fmt="%d/%m/%Y"))
