"""Tests for Ask Bata + Help Center feature (iteration 7)."""
import os
import json
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback to reading frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin", "Admin@123")


@pytest.fixture(scope="module")
def ops_token():
    return _login("ops", "Ops@123")


@pytest.fixture(scope="module")
def mgmt_token():
    return _login("mgmt", "Mgmt@123")


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# ---- Help endpoint ----
def test_help_requires_auth():
    r = requests.get(f"{API}/ask/help", timeout=15)
    assert r.status_code == 401


def test_help_sections(admin_token):
    r = requests.get(f"{API}/ask/help", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "sections" in data
    ids = [s.get("id") for s in data["sections"]]
    for expected in ["overview", "dashboard", "reports", "formulas", "pipeline", "validation",
                     "exceptions", "insights", "roles", "ask", "glossary"]:
        assert expected in ids, f"missing section {expected}: got {ids}"
    assert len(data["sections"]) == 11
    # validation has 12 items
    val = next(s for s in data["sections"] if s["id"] == "validation")
    assert len(val.get("items", [])) == 12


# ---- Suggestions ----
def test_suggestions(admin_token):
    r = requests.get(f"{API}/ask/suggestions", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d, list) and len(d) == 8
    assert all(isinstance(x, str) for x in d)


# ---- Sessions CRUD + ownership isolation ----
def test_sessions_crud_and_isolation(admin_token, ops_token):
    # create as admin
    r = requests.post(f"{API}/ask/sessions", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    s = r.json()
    assert s["title"] == "New conversation"
    assert s["message_count"] == 0
    assert s["owner"] == "admin"
    sid = s["id"]

    # list as admin — includes sid
    r = requests.get(f"{API}/ask/sessions", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert sid in ids

    # list as ops — does NOT include sid
    r = requests.get(f"{API}/ask/sessions", headers=_h(ops_token), timeout=15)
    assert r.status_code == 200
    ops_ids = [x["id"] for x in r.json()]
    assert sid not in ops_ids

    # get admin's session as ops -> 404
    r = requests.get(f"{API}/ask/sessions/{sid}", headers=_h(ops_token), timeout=15)
    assert r.status_code == 404

    # get admin's session as admin -> messages array empty
    r = requests.get(f"{API}/ask/sessions/{sid}", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "messages" in body and body["messages"] == []

    # delete
    r = requests.delete(f"{API}/ask/sessions/{sid}", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    # verify gone
    r = requests.get(f"{API}/ask/sessions/{sid}", headers=_h(admin_token), timeout=15)
    assert r.status_code == 404


# ---- SSE with exhausted key ----
def test_send_message_sse_exhausted_key(admin_token):
    # create session
    r = requests.post(f"{API}/ask/sessions", headers=_h(admin_token), timeout=15)
    sid = r.json()["id"]
    try:
        # empty text -> 400
        r = requests.post(f"{API}/ask/sessions/{sid}/messages", headers=_h(admin_token), json={"text": "   "}, timeout=15)
        assert r.status_code == 400

        # real send with stream
        r = requests.post(f"{API}/ask/sessions/{sid}/messages", headers=_h(admin_token),
                          json={"text": "What is achievement %?"}, stream=True, timeout=60)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        events = []
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except Exception:
                    pass
            if events and events[-1].get("type") == "done":
                break
        r.close()
        types = [e.get("type") for e in events]
        assert "done" in types
        if "error" in types:
            err = next(e for e in events if e["type"] == "error")
            assert "Universal LLM Key balance is exhausted" in err.get("message", ""), f"unexpected error msg: {err}"
            # user message NOT persisted
            g = requests.get(f"{API}/ask/sessions/{sid}", headers=_h(admin_token), timeout=15)
            assert g.status_code == 200
            body = g.json()
            assert body["messages"] == []
            assert body["title"] == "New conversation"
        else:
            # If key works, ensure assistant message persisted
            g = requests.get(f"{API}/ask/sessions/{sid}", headers=_h(admin_token), timeout=15)
            body = g.json()
            assert len(body["messages"]) >= 2
    finally:
        requests.delete(f"{API}/ask/sessions/{sid}", headers=_h(admin_token), timeout=15)


# ---- Pre-existing successful session ----
def test_existing_partners_behind_session(admin_token):
    r = requests.get(f"{API}/ask/sessions", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    sessions = r.json()
    match = [s for s in sessions if s.get("title", "").startswith("Which partners are behind")]
    assert match, f"expected a session titled starting 'Which partners are behind', got titles: {[s.get('title') for s in sessions]}"
    s = match[0]
    assert s["message_count"] >= 2
    r = requests.get(f"{API}/ask/sessions/{s['id']}", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    body = r.json()
    msgs = body["messages"]
    assert len(msgs) >= 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1].get("content")
    tools = msgs[1].get("tools") or []
    assert tools and tools[0].get("name") == "run_report", f"expected tools[0].name==run_report got {tools}"


# ---- Insights nl_query active ----
def test_insights_nl_query_active(admin_token):
    r = requests.get(f"{API}/insights", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("nl_query", {}).get("status") == "active", d.get("nl_query")


# ---- Regression: dashboard/reports ----
def test_regression_dashboard(admin_token):
    r = requests.get(f"{API}/dashboard", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200


def test_regression_reports(admin_token):
    r = requests.get(f"{API}/reports", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200


def test_regression_target_vs_actual(admin_token):
    r = requests.get(f"{API}/reports/target_vs_actual", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
