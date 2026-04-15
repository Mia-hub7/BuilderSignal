from datetime import datetime, timedelta, timezone
import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from database import get_session, Summary, Builder, RawContent

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CATEGORIES = ["全部", "技术洞察", "产品动态", "行业预判", "工具推荐"]


def _today_start_utc() -> datetime:
    """Return today's 00:00 UTC+8 expressed as naive UTC datetime."""
    now_utc8 = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    start_utc8 = now_utc8.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_utc8.astimezone(timezone.utc).replace(tzinfo=None)


def _relative_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    diff = datetime.utcnow() - dt
    minutes = int(diff.total_seconds() / 60)
    if minutes < 1:
        return "刚刚"
    if minutes < 60:
        return f"{minutes}分钟前"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}小时前"
    return f"{hours // 24}天前"


def _source_label(source: str) -> str:
    return {"x": "X", "podcast": "Podcast", "blog": "Blog"}.get(source, source.upper())


def _query_items(category: str) -> list[dict]:
    today_start = _today_start_utc()
    with get_session() as session:
        q = (
            session.query(Summary)
            .filter(Summary.created_at >= today_start, Summary.is_visible == 1)
        )
        if category and category != "全部":
            q = q.filter(Summary.category_tag == category)
        summaries = q.order_by(Summary.published_at.desc()).all()

        items = []
        for sm in summaries:
            builder_name = "Unknown"
            if sm.builder_id:
                b = session.query(Builder).filter_by(id=sm.builder_id).first()
                if b:
                    builder_name = b.name
            source = ""
            if sm.raw_content_id:
                rc = session.query(RawContent).filter_by(id=sm.raw_content_id).first()
                if rc:
                    source = rc.source
            items.append({
                "builder_name": builder_name,
                "source": _source_label(source),
                "category_tag": sm.category_tag or "",
                "rel_time": _relative_time(sm.published_at),
                "summary_en": sm.summary_en or "",
                "summary_zh": sm.summary_zh or "",
                "original_url": sm.original_url or "#",
            })
    return items


@router.get("/")
async def feed(request: Request, category: str = ""):
    active = category if category in CATEGORIES else "全部"
    items = _query_items(active)
    today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    ctx = {
        "request": request,
        "items": items,
        "total": len(items),
        "today_str": today_str,
        "active_category": active,
        "categories": CATEGORIES,
    }

    return templates.TemplateResponse("feed.html", ctx)


@router.get("/api/status")
async def api_status():
    today_start = _today_start_utc()
    with get_session() as session:
        last_rc = (
            session.query(RawContent)
            .order_by(RawContent.fetched_at.desc())
            .first()
        )
        last_fetch_time = (
            last_rc.fetched_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if last_rc and last_rc.fetched_at else None
        )
        total_summaries = session.query(Summary).filter_by(is_visible=1).count()
        today_summaries = (
            session.query(Summary)
            .filter(Summary.created_at >= today_start, Summary.is_visible == 1)
            .count()
        )
    return JSONResponse({
        "last_fetch_time": last_fetch_time,
        "total_summaries": total_summaries,
        "today_summaries": today_summaries,
    })


async def _run_fetch_bg():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _do_fetch)


def _do_fetch():
    from jobs.fetch import run_fetch
    run_fetch()


@router.post("/api/trigger-fetch")
async def api_trigger_fetch():
    asyncio.create_task(_run_fetch_bg())
    return JSONResponse({"status": "started"})
