from datetime import datetime, timedelta, timezone
import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from database import get_session, Summary, Builder, RawContent

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CATEGORIES = ["全部", "技术洞察", "产品动态", "行业预判", "工具推荐"]


TZ8 = timezone(timedelta(hours=8))


def _day_range_utc(beijing_date: datetime) -> tuple[datetime, datetime]:
    """Return (day_start, day_end) in naive UTC for a given Beijing date."""
    start = beijing_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _resolve_display_date() -> tuple[datetime, str]:
    """Return (beijing_date, date_str) for the most recent day that has content.
    Tries today first, falls back to yesterday, then the latest available day."""
    now_utc8 = datetime.now(TZ8)
    with get_session() as session:
        for delta in [0, 1]:
            candidate = now_utc8 - timedelta(days=delta)
            start, end = _day_range_utc(candidate)
            count = (
                session.query(Summary)
                .filter(Summary.created_at >= start, Summary.created_at < end, Summary.is_visible == 1)
                .count()
            )
            if count > 0:
                return candidate, candidate.strftime("%Y-%m-%d")
        # fallback: most recent available day
        latest = (
            session.query(Summary.created_at)
            .filter(Summary.is_visible == 1)
            .order_by(Summary.created_at.desc())
            .first()
        )
        if latest:
            dt_utc8 = latest[0].replace(tzinfo=timezone.utc).astimezone(TZ8)
            return dt_utc8, dt_utc8.strftime("%Y-%m-%d")
    return now_utc8, now_utc8.strftime("%Y-%m-%d")


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


def _query_items(category: str, beijing_date: datetime) -> list[dict]:
    start, end = _day_range_utc(beijing_date)
    with get_session() as session:
        q = (
            session.query(Summary)
            .filter(Summary.created_at >= start, Summary.created_at < end, Summary.is_visible == 1)
        )
        if category and category != "全部":
            q = q.filter(Summary.category_tag == category)
        summaries = q.order_by(Summary.published_at.desc()).all()

        items = []
        for sm in summaries:
            builder_name = "Unknown"
            builder_bio = ""
            if sm.builder_id:
                b = session.query(Builder).filter_by(id=sm.builder_id).first()
                if b:
                    builder_name = b.name
                    builder_bio = b.bio or ""
            source = ""
            if sm.raw_content_id:
                rc = session.query(RawContent).filter_by(id=sm.raw_content_id).first()
                if rc:
                    source = rc.source
            pub = sm.published_at
            published_time = pub.strftime("%m-%d %H:%M") if pub else ""
            items.append({
                "builder_name": builder_name,
                "builder_bio": builder_bio,
                "source": _source_label(source),
                "category_tag": sm.category_tag or "",
                "published_time": published_time,
                "summary_en": sm.summary_en or "",
                "summary_zh": sm.summary_zh or "",
                "original_url": sm.original_url or "#",
            })
    return items


@router.get("/")
async def feed(request: Request, category: str = ""):
    active = category if category in CATEGORIES else "全部"
    beijing_date, _ = _resolve_display_date()
    items = _query_items(active, beijing_date)
    today_str = datetime.now(TZ8).strftime("%Y-%m-%d")

    ctx = {
        "request": request,
        "items": items,
        "total": len(items),
        "today_str": today_str,
        "active_category": active,
        "categories": CATEGORIES,
        "active_nav": "feed",
    }

    return templates.TemplateResponse("feed.html", ctx)


@router.get("/api/status")
async def api_status():
    now_utc8 = datetime.now(TZ8)
    today_start, today_end = _day_range_utc(now_utc8)
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
            .filter(Summary.created_at >= today_start, Summary.created_at < today_end, Summary.is_visible == 1)
            .count()
        )
        latest = (
            session.query(Summary.created_at)
            .filter(Summary.is_visible == 1)
            .order_by(Summary.created_at.desc())
            .first()
        )
        latest_created = latest[0].strftime("%Y-%m-%d %H:%M:%S UTC") if latest else None
    return JSONResponse({
        "last_fetch_time": last_fetch_time,
        "total_summaries": total_summaries,
        "today_summaries": today_summaries,
        "latest_summary_created_at": latest_created,
        "now_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "now_beijing": now_utc8.strftime("%Y-%m-%d %H:%M:%S +08"),
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
