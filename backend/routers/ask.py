import os
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, ToolCallStart, ToolCallReady, StreamDone
from core.db import db
from core.auth import get_current_user
from core.utils import now_iso, new_id
from core.audit import log_audit
from services.agent_tools import TOOLS, dispatch, get_data_coverage
from services.help_content import help_text_for_agent, build_help

router = APIRouter(prefix="/ask")
logger = logging.getLogger("ask")
MODEL = ("openai", "gpt-5.4")
HISTORY_TURNS = 16

BRIEF = """You are **Ask Bata**, the analytics agent inside the Bata SIS Sales Intelligence Platform (India). Bata sells footwear through Shop-in-Shop (SIS) counters inside partner department stores. This platform ingests each partner's weekly sales files, standardizes them into one Bata data model, validates them and reports on them. You know every dashboard, report, formula, rule and screen, and you can query the live reporting database with tools.

Partners (code → name): CENTRO, INC5 → INC 5, KORA, LIFESTYLE, LULU, RCENTRAL → R. CENTRAL, RTRENDS → R. TRENDS, SHOPPERS → Shoppers Stop, SPENCER, ZUUP. Regions: North, South, East, West. Categories (GRPCAT): BATA MEN, BATA WOMEN, HP MEN, HP WOMEN (HP = Hush Puppies), KIDS, FLOATZ, NFT. Currency INR only (format ₹12,34,567 Indian style; use ₹ L / ₹ Cr for lakhs/crores when large). Pairs = quantity.

RULES
1. Never invent, estimate or extrapolate numbers. Every figure you state must come from a tool result in this conversation. If a tool returns nothing, say so.
2. Prefer run_report for questions matching a standard report (so numbers match the Reports page); use aggregate_sales for anything else; get_targets_vs_actual for targets (store-level allowed); get_stock, get_margins, get_batches, get_exceptions, get_data_quality, get_insights for operations questions; search_help / your knowledge below for "how is X computed".
3. When a question is ambiguous about period, use the data's latest available period and say which period you used. Call get_data_coverage when unsure what exists. Weekly history is dated on the week's Monday, so "daily" questions on 2025 data are really weekly.
4. Answer like a sharp retail analyst: lead with the answer, then a compact markdown table (max ~15 rows) and 2–4 bullet insights (drivers, outliers, gaps vs target, next action). State filters/period used. Keep it tight; no fluff, no disclaimers about being an AI.
5. Explain formulas exactly as defined below when asked; do not improvise definitions. Point users to the Help Center (/help) for details.
6. You are read-only. You cannot upload, change mappings, masters, or fix exceptions — tell users which screen to use (Upload Data, Review Queue, Masters, Partner Configuration, Settings).
7. Use markdown: headings sparingly, bold key numbers, tables for comparisons.
"""


def _sys():
    return BRIEF + "\n" + help_text_for_agent()


@router.get("/help")
async def help_center(user=Depends(get_current_user)):
    return build_help()


@router.get("/sessions")
async def sessions(user=Depends(get_current_user)):
    return await db.chat_sessions.find({"owner": user["username"]}, {"_id": 0}).sort("updated_at", -1).limit(50).to_list(50)


@router.post("/sessions")
async def create_session(user=Depends(get_current_user)):
    doc = {"id": new_id(), "owner": user["username"], "title": "New conversation", "created_at": now_iso(), "updated_at": now_iso(), "message_count": 0}
    await db.chat_sessions.insert_one(dict(doc))
    return doc


@router.get("/sessions/{sid}")
async def get_session(sid: str, user=Depends(get_current_user)):
    s = await db.chat_sessions.find_one({"id": sid, "owner": user["username"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    s["messages"] = await db.chat_messages.find({"session_id": sid}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return s


@router.delete("/sessions/{sid}")
async def delete_session(sid: str, user=Depends(get_current_user)):
    await db.chat_sessions.delete_one({"id": sid, "owner": user["username"]})
    await db.chat_messages.delete_many({"session_id": sid})
    return {"ok": True}


@router.get("/suggestions")
async def suggestions(user=Depends(get_current_user)):
    return ["Which partners are behind their Week 32 target, and by how much?", "Top 10 stores by net sales in the latest week — and the bottom 5", "Show category mix for Lifestyle vs Shoppers Stop this year",
            "Which stores have more than 20 weeks of stock cover?", "How is Achievement % calculated?", "Which partners have open exceptions and what rules are firing?", "Compare 2026 YTD net sales by region with 2025 same weeks",
            "What is Bata's net after partner margin for each partner?"]


def _sse(obj):
    return f"data: {json.dumps(obj, default=str)}\n\n"


def _preview(name, result):
    """Trim a tool result for the UI: first table-like list found, max 15 rows."""
    if not isinstance(result, dict):
        return {"name": name}
    rows = next((v for k, v in result.items() if isinstance(v, list) and v and isinstance(v[0], dict)), None)
    return {"name": name, "row_count": result.get("row_count", result.get("group_count", len(rows) if rows else None)), "rows": (rows or [])[:15], "error": result.get("error")}


@router.post("/sessions/{sid}/messages")
async def send(sid: str, body: dict, user=Depends(get_current_user)):
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")
    s = await db.chat_sessions.find_one({"id": sid, "owner": user["username"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="EMERGENT_LLM_KEY not configured")
    history = await db.chat_messages.find({"session_id": sid}, {"_id": 0, "role": 1, "content": 1}).sort("created_at", 1).to_list(500)
    history = [{"role": m["role"], "content": m["content"]} for m in history if m.get("content")][-HISTORY_TURNS:]
    user_mid = new_id()
    await db.chat_messages.insert_one({"id": user_mid, "session_id": sid, "role": "user", "content": text, "created_at": now_iso()})
    if s["message_count"] == 0:
        await db.chat_sessions.update_one({"id": sid}, {"$set": {"title": text[:60]}})
    cov = await get_data_coverage()
    sys_msg = _sys() + f"\n## Live data coverage (now)\nSales rows {cov['sales'].get('rows')}, dates {cov['sales'].get('min')} → {cov['sales'].get('max')}, latest weeks {cov['latest_weeks']}, targets weeks {cov['targets']['weeks']}, open exceptions {cov['open_exceptions']}. Today is {datetime.now(timezone.utc).date()}."
    chat = LlmChat(api_key=key, session_id=sid, system_message=sys_msg, initial_messages=[{"role": "system", "content": sys_msg}] + history).with_model(*MODEL).with_tools(TOOLS, tool_choice="auto")

    async def gen():
        full, tools_used, user_msg, hops = [], [], UserMessage(text=text), 0
        try:
            while True:
                pending = []
                async for ev in chat.stream_message(user_msg):
                    if isinstance(ev, TextDelta):
                        full.append(ev.content)
                        yield _sse({"type": "delta", "content": ev.content})
                    elif isinstance(ev, ToolCallStart):
                        yield _sse({"type": "tool_start", "name": ev.name})
                    elif isinstance(ev, ToolCallReady):
                        pending.append(ev.tool_call)
                    elif isinstance(ev, StreamDone):
                        break
                if not pending or hops >= 8:
                    break
                hops += 1
                for tc in pending:
                    yield _sse({"type": "tool_call", "name": tc.name, "args": tc.arguments})
                    result = await dispatch(tc.name, tc.arguments)
                    prev = _preview(tc.name, result)
                    tools_used.append({"name": tc.name, "args": tc.arguments, **prev})
                    yield _sse({"type": "tool_result", **prev, "args": tc.arguments})
                    chat.add_tool_result(tc.id, json.dumps(result, default=str)[:60000])
                user_msg = None
        except Exception as e:
            logger.exception("ask stream failed")
            msg = str(e)
            if "Budget has been exceeded" in msg or "RateLimitError" in msg:
                msg = "The Universal LLM Key balance is exhausted. Top up under Profile → Manage plan → Universal Key → Add Balance (or enable auto top-up), then ask again."
            yield _sse({"type": "error", "message": msg[:300]})
        content = "".join(full)
        mid = new_id()
        if content or tools_used:
            await db.chat_messages.insert_one({"id": mid, "session_id": sid, "role": "assistant", "content": content, "tools": tools_used, "created_at": now_iso()})
            await db.chat_sessions.update_one({"id": sid}, {"$set": {"updated_at": now_iso()}, "$inc": {"message_count": 2}})
        else:
            await db.chat_messages.delete_one({"id": user_mid})
            if s["message_count"] == 0:
                await db.chat_sessions.update_one({"id": sid}, {"$set": {"title": "New conversation"}})
        await log_audit(user["username"], "ask.query", "chat_session", sid, {"question": text[:200], "tools": [t["name"] for t in tools_used]}, category="analytics")
        yield _sse({"type": "done", "message_id": mid})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
