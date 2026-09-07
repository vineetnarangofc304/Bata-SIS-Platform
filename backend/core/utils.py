import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def new_id() -> str:
    return str(uuid.uuid4())


async def paginate(coll, query, page=1, page_size=25, sort=("created_at", -1), projection=None):
    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    proj = {"_id": 0}
    if projection:
        proj.update(projection)
    total = await coll.count_documents(query)
    items = await coll.find(query, proj).sort(*sort).skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": (total + page_size - 1) // page_size}
