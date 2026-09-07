"""End-to-end API tests for Bata SIS platform - hits the public backend URL."""
import io
import os
import time
import hashlib
from datetime import datetime, timedelta

import pytest
import requests
import openpyxl

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://partner-sync-38.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=30)
    return r


@pytest.fixture(scope="session")
def admin_token():
    r = _login("admin", "Admin@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def ops_token():
    r = _login("ops", "Ops@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def mgmt_token():
    r = _login("mgmt", "Mgmt@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------------------- AUTH ----------------------
class TestAuth:
    def test_login_invalid(self):
        r = _login("admin", "wrong")
        assert r.status_code == 401

    def test_login_valid_roles(self, admin_token, ops_token, mgmt_token):
        assert admin_token and ops_token and mgmt_token

    def test_me(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=h(admin_token))
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_mgmt_forbidden_uploads(self, mgmt_token):
        # Attempting upload endpoint should be forbidden
        files = {"file": ("t.txt", b"abc", "text/plain")}
        r = requests.post(f"{API}/uploads", headers=h(mgmt_token), files=files, data={"partner_code": ""})
        assert r.status_code in (400, 403), r.text

    def test_ops_forbidden_masters_create(self, ops_token):
        r = requests.post(f"{API}/masters/stores", headers=h(ops_token), json={"code": "TS999", "name": "x", "partner_code": "SS"})
        assert r.status_code == 403


# ---------------------- DASHBOARD / REPORTS ----------------------
class TestDashboard:
    def test_dashboard(self, admin_token):
        r = requests.get(f"{API}/dashboard", headers=h(admin_token))
        assert r.status_code == 200
        d = r.json()
        assert "kpis" in d
        for k in ("mtd_sales", "active_partners", "acceptance_pct"):
            assert k in d["kpis"]

    def test_reports_list_has_12(self, admin_token):
        r = requests.get(f"{API}/reports", headers=h(admin_token))
        assert r.status_code == 200
        keys = [x["key"] for x in r.json()]
        expected = ["daily_sales", "monthly_sales", "partner_performance", "store_performance",
                    "region_performance", "category_performance", "sku_performance", "top_bottom",
                    "discount_analysis", "data_quality_trend", "missing_submissions", "exception_summary"]
        for e in expected:
            assert e in keys, f"missing {e}"

    @pytest.mark.parametrize("key", ["daily_sales", "monthly_sales", "partner_performance", "store_performance",
                                     "region_performance", "category_performance", "sku_performance", "top_bottom",
                                     "discount_analysis", "data_quality_trend", "missing_submissions", "exception_summary"])
    def test_each_report(self, admin_token, key):
        r = requests.get(f"{API}/reports/{key}", headers=h(admin_token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "columns" in data and "rows" in data

    def test_report_export_csv(self, admin_token):
        r = requests.get(f"{API}/reports/daily_sales/export?fmt=csv", headers=h(admin_token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower() or r.content

    def test_report_export_xlsx(self, admin_token):
        r = requests.get(f"{API}/reports/daily_sales/export?fmt=xlsx", headers=h(admin_token))
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_report_records_paginate(self, admin_token):
        r = requests.get(f"{API}/reports/records?limit=5&offset=0", headers=h(admin_token))
        assert r.status_code == 200
        assert "items" in r.json() or "rows" in r.json()


# ---------------------- BATCHES / INSIGHTS / AUDIT ----------------------
class TestListings:
    def test_batches_list(self, admin_token):
        r = requests.get(f"{API}/batches?limit=20", headers=h(admin_token))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_insights(self, admin_token):
        r = requests.get(f"{API}/insights", headers=h(admin_token))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_audit(self, admin_token):
        r = requests.get(f"{API}/audit-logs?page_size=20", headers=h(admin_token))
        assert r.status_code == 200

    def test_notifications(self, admin_token):
        r = requests.get(f"{API}/notifications", headers=h(admin_token))
        assert r.status_code == 200

    def test_partners(self, admin_token):
        r = requests.get(f"{API}/partners", headers=h(admin_token))
        assert r.status_code == 200
        assert len(r.json()) == 9

    def test_fields(self, admin_token):
        r = requests.get(f"{API}/fields", headers=h(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 5


# ---------------------- MASTERS ----------------------
class TestMasters:
    @pytest.mark.parametrize("tab", ["stores", "skus", "hierarchy", "geo", "aliases", "rules", "sender_rules"])
    def test_masters_lists(self, admin_token, tab):
        r = requests.get(f"{API}/masters/{tab}?limit=5", headers=h(admin_token))
        assert r.status_code == 200, f"{tab}: {r.text}"

    def test_store_create_duplicate(self, admin_token):
        payload = {"code": "TEST_STORE_A", "name": "Test Store A", "partner_code": "SS", "city": "Mumbai", "state": "MH", "region": "West"}
        r = requests.post(f"{API}/masters/stores", headers=h(admin_token), json=payload)
        # accept 200/201 first time or 409 if exists
        assert r.status_code in (200, 201, 409), r.text
        r2 = requests.post(f"{API}/masters/stores", headers=h(admin_token), json=payload)
        assert r2.status_code == 409


# ---------------------- UPLOAD FLOW ----------------------
def _make_shoppers_stop_xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Shoppers Stop", "SIS Report"])
    ws.append([])
    ws.append(["Bill Date", "Store Code", "Store Name", "Article Code", "Article Description",
               "Qty", "MRP", "Selling Price", "Discount", "GST Amount", "Net Amount", "Bill No"])
    yday = (datetime.utcnow() - timedelta(days=1)).strftime("%d/%m/%Y")
    # Grab a couple SKU codes
    return wb, ws, yday


class TestUploadFlow:
    def _skus(self, tok):
        r = requests.get(f"{API}/masters/skus?limit=5", headers=h(tok))
        return [s["code"] for s in r.json()["items"]]

    def test_upload_txt_rejected(self, ops_token):
        files = {"file": ("bad.txt", b"hello", "text/plain")}
        r = requests.post(f"{API}/uploads", headers=h(ops_token), files=files)
        assert r.status_code == 400

    def test_upload_shoppers_stop_success_and_duplicate(self, ops_token):
        skus = self._skus(ops_token)
        assert skus, "Need SKUs"
        wb, ws, yday = _make_shoppers_stop_xlsx()
        for i in range(5):
            ws.append([yday, f"SS00{(i%5)+1}", "Store", skus[i % len(skus)], "desc",
                       2, 1000, 800, 200, 40, 800 * 2, f"B{i:04d}"])
        ws.append(["Grand Total", "", "", "", "", 10, "", "", "", "", 8000, ""])
        buf = io.BytesIO()
        wb.save(buf)
        content = buf.getvalue()

        files = {"file": ("ShoppersStop_test.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/uploads", headers=h(ops_token), files=files)
        assert r.status_code in (200, 201), r.text
        batch_id = r.json().get("id") or r.json().get("batch_id")
        assert batch_id

        # Poll status
        final = None
        for _ in range(20):
            time.sleep(1)
            b = requests.get(f"{API}/batches/{batch_id}", headers=h(ops_token)).json()
            final = b.get("status")
            if final and final not in ("Analysing", "Validating", "Queued", "Uploaded"):
                break
        assert final in ("Successfully Processed", "Partially Processed", "Awaiting Review"), f"Got {final}"

        # Duplicate upload
        files2 = {"file": ("ShoppersStop_test.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r2 = requests.post(f"{API}/uploads", headers=h(ops_token), files=files2)
        assert r2.status_code in (200, 201, 409), r2.text
        if r2.status_code in (200, 201):
            b2id = r2.json().get("id") or r2.json().get("batch_id")
            time.sleep(2)
            b2 = requests.get(f"{API}/batches/{b2id}", headers=h(ops_token)).json()
            assert b2.get("status") == "Rejected" or b2.get("duplicate_of"), f"Expected duplicate rejection, got {b2.get('status')}"

    def test_upload_preview(self, ops_token):
        skus = self._skus(ops_token)
        wb, ws, yday = _make_shoppers_stop_xlsx()
        ws.append([yday, "SS001", "Store", skus[0], "desc", 1, 100, 90, 10, 5, 90, "B1"])
        buf = io.BytesIO(); wb.save(buf)
        files = {"file": ("preview.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/uploads/preview", headers=h(ops_token), files=files)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "sheets" in data


# ---------------------- SETTINGS ----------------------
class TestSettings:
    def test_get_settings(self, admin_token):
        r = requests.get(f"{API}/settings", headers=h(admin_token))
        assert r.status_code == 200

    def test_put_settings(self, admin_token):
        # Get then put back
        cur = requests.get(f"{API}/settings", headers=h(admin_token)).json()
        r = requests.put(f"{API}/settings", headers=h(admin_token), json=cur)
        assert r.status_code in (200, 204)


# ---------------------- USERS ----------------------
class TestUsers:
    def test_list_users_admin(self, admin_token):
        r = requests.get(f"{API}/users", headers=h(admin_token))
        assert r.status_code == 200

    def test_users_forbidden_ops(self, ops_token):
        r = requests.get(f"{API}/users", headers=h(ops_token))
        assert r.status_code == 403

    def test_short_password_rejected(self, admin_token):
        r = requests.post(f"{API}/users", headers=h(admin_token),
                          json={"username": "TEST_shortpw", "password": "abc", "email": "t@t.com", "name": "t", "role": "ops"})
        assert r.status_code == 400
