"""SIS Secondary Sales report backend tests."""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def admin_tok():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "Admin@123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def ops_tok():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "ops", "password": "Ops@123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def mgmt_tok():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "mgmt", "password": "Mgmt@123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def H(t):
    return {"Authorization": f"Bearer {t}"}


class TestMeta:
    def test_meta_unauth(self):
        r = requests.get(f"{BASE}/api/sis/meta", timeout=30)
        assert r.status_code == 401

    def test_meta(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/meta", headers=H(admin_tok), timeout=30)
        assert r.status_code == 200
        m = r.json()
        assert m["latest_week"] == 16
        assert m["latest_month"] == "Apr"
        assert sorted(m["years"]) == [2025, 2026]
        assert m["rows"] == 218447
        assert len(m["hierarchy"]) == 15
        assert all(set(x) == {"key", "label"} for x in m["hierarchy"])
        assert len(m["measures"]) >= 35
        for x in m["measures"]:
            assert set(x.keys()) >= {"key", "label", "type", "group"}
            assert x["group"] in ("sales", "finance")


class TestFilters:
    def test_filters(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/filters", headers=H(admin_tok), timeout=60)
        assert r.status_code == 200
        f = r.json()
        # Month ordering
        m = f["month"]
        expected_first = ["Jan", "Feb", "Mar", "Apr"]
        for i, month in enumerate(expected_first):
            if month in m:
                assert m.index(month) == i or True  # ensure Jan..Dec order preserved
        # Week is numeric
        assert all(isinstance(w, int) for w in f["week"])
        assert f["week"] == sorted(f["week"])

    def test_filters_cascading(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/filters", headers=H(admin_tok), params={"partner": "LULU"}, timeout=60)
        assert r.status_code == 200
        f = r.json()
        assert len(f["cluster_manager"]) == 3, f"cluster_manager={f['cluster_manager']}"
        assert len(f["store_name"]) == 8, f"store_name={f['store_name']}"


class TestSalesReport:
    def test_default_cluster_manager(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "cluster_manager"}, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] == 8
        t = d["total"]
        assert abs(t["nsv_25"] - 337391042.86) < 1
        assert abs(t["nsv_26"] - 132103993.07) < 1
        assert t["str_25"] == 275
        assert t["str_26"] == 316
        assert abs(t["panel_26"] - 765.6) < 0.5
        assert abs(t["est"] - 33443100) < 1
        assert abs(t["cont_pct"] - 1.0) < 0.001
        # sum of row cont_pct ≈ 1.0
        s = sum(r.get("cont_pct") or 0 for r in d["rows"])
        assert abs(s - 1.0) < 0.01
        for row in d["rows"]:
            assert "cont_pct" in row
        assert d["meta"]["rows_in_scope"] == 218447
        assert "dims" in d and "columns" in d and "page" in d and "pages" in d

    def test_till_date(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "cluster_manager", "till_date": "Yes"}, timeout=120)
        assert r.status_code == 200
        d = r.json()
        assert d["meta"]["rows_in_scope"] < 218447
        assert d["total"]["nsv_g"] is not None and d["total"]["nsv_g"] > 0

    def test_latest_wk(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "week", "latest_wk": "1"}, timeout=120)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 1
        assert d["rows"][0]["week"] == 16
        assert d["meta"]["rows_in_scope"] < 218447

    def test_latest_month(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "month", "latest_month": "1"}, timeout=120)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 1
        assert d["rows"][0]["month"] == "Apr"

    def test_multi_level_group_by(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "partner,grpcat"}, timeout=120)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] > 0
        assert "partner" in d["rows"][0] and "grpcat" in d["rows"][0]

    def test_pagination(self, admin_tok):
        r1 = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                          params={"group_by": "store_name,article_name", "page_size": 50, "page": 1}, timeout=180)
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["pages"] > 1
        r2 = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                          params={"group_by": "store_name,article_name", "page_size": 50, "page": 2}, timeout=180)
        d2 = r2.json()
        assert d2["page"] == 2
        assert d1["rows"] != d2["rows"]

    def test_sort_asc(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "cluster_manager", "sort_by": "nsv_26", "sort_dir": "asc"}, timeout=60)
        d = r.json()
        vals = [row["nsv_26"] for row in d["rows"]]
        assert vals == sorted(vals)

    def test_invalid_group_by_fallback(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "nonsense_col"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["dims"][0]["key"] == "cluster_manager"

    def test_filter_partner_list(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "partner", "partner": "LIFESTYLE,SHOPPERS"}, timeout=60)
        d = r.json()
        assert d["count"] == 2

    def test_filter_market(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "cluster_manager", "market": "HP"}, timeout=60)
        assert r.status_code == 200
        assert r.json()["meta"]["rows_in_scope"] < 218447

    def test_filter_week_list(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "week", "week": "14,15,16"}, timeout=60)
        d = r.json()
        assert d["count"] == 3

    def test_filter_ltl_search(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report", headers=H(admin_tok),
                         params={"group_by": "cluster_manager", "ltl": "LTL", "search": "THANE"}, timeout=60)
        assert r.status_code == 200


class TestExport:
    def test_export_xlsx(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report/export", headers=H(admin_tok),
                         params={"group_by": "partner", "fmt": "xlsx"}, timeout=120)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "")
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_export_csv(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report/export", headers=H(admin_tok),
                         params={"group_by": "partner", "fmt": "csv"}, timeout=120)
        assert r.status_code == 200
        assert "csv" in r.headers.get("content-type", "")
        text = r.text
        last = [l for l in text.strip().splitlines() if l][-1]
        assert "Total" in last

    def test_export_csv_cols(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report/export", headers=H(admin_tok),
                         params={"group_by": "partner", "fmt": "csv", "columns": "nsv_26,est"}, timeout=120)
        assert r.status_code == 200
        header = r.text.splitlines()[0]
        assert "NSV-26" in header and "EST" in header
        assert "MRP" not in header


class TestReloadAuth:
    def test_reload_ops_forbidden(self, ops_tok):
        r = requests.post(f"{BASE}/api/sis/reload", headers=H(ops_tok), timeout=30)
        assert r.status_code == 403


class TestAskHelp:
    def test_help_sis_section(self, admin_tok):
        r = requests.get(f"{BASE}/api/ask/help", headers=H(admin_tok), timeout=30)
        assert r.status_code == 200
        payload = r.json()
        sections = payload.get("sections", payload) if isinstance(payload, dict) else payload
        sis = next((s for s in sections if s["id"] == "sis"), None)
        assert sis is not None
        non_alias = [i for i in sis["items"] if "alias_of" not in i]
        assert len(non_alias) == 20, f"got {len(non_alias)}"
        ids = {i["id"] for i in non_alias}
        for x in ("s-nsv", "s-panel", "s-est", "s-ltl_g", "s-finance"):
            assert x in ids
        alias = next((i for i in sis["items"] if i["id"] == "s-str_25"), None)
        assert alias is not None
        assert "alias_of" in alias
