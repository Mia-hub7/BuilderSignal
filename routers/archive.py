from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from database import get_session, Summary, Builder, RawContent

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CATEGORIES = ["全部", "深度内容", "观点速览"]


def _source_label(source: str) -> str:
    return {"x": "X", "podcast": "Podcast", "blog": "Blog"}.get(source, source.upper())


def _build_items(summaries, session) -> list[dict]:
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


TZ8 = timezone(timedelta(hours=8))


def _query_by_date(date_str: str, category: str) -> list[dict]:
    try:
        day_bj = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TZ8)
    except ValueError:
        return []
    day_start_utc = day_bj.astimezone(timezone.utc).replace(tzinfo=None)
    day_end_utc = (day_bj + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)

    with get_session() as session:
        q = (
            session.query(Summary)
            .filter(
                Summary.published_at >= day_start_utc,
                Summary.published_at < day_end_utc,
                Summary.is_visible == 1,
            )
        )
        if category and category != "全部":
            q = q.filter(Summary.category_tag == category)
        summaries = q.order_by(Summary.published_at.desc()).all()
        return _build_items(summaries, session)


def _query_by_keyword(keyword: str, category: str) -> list[dict]:
    kw = f"%{keyword}%"
    with get_session() as session:
        from sqlalchemy import or_
        matching_builder_ids = [
            b.id for b in session.query(Builder).filter(Builder.name.ilike(kw)).all()
        ]
        filters = [
            Summary.summary_zh.ilike(kw),
            Summary.summary_en.ilike(kw),
        ]
        if matching_builder_ids:
            filters.append(Summary.builder_id.in_(matching_builder_ids))
        q = (
            session.query(Summary)
            .filter(Summary.is_visible == 1, or_(*filters))
        )
        if category and category != "全部":
            q = q.filter(Summary.category_tag == category)
        summaries = q.order_by(Summary.created_at.desc()).limit(100).all()
        return _build_items(summaries, session)


def _available_dates() -> list[str]:
    """Return distinct dates (YYYY-MM-DD in Beijing time) that have summaries, newest first."""
    with get_session() as session:
        rows = (
            session.query(Summary.published_at)
            .filter(Summary.is_visible == 1)
            .all()
        )
    dates = sorted(
        {r[0].replace(tzinfo=timezone.utc).astimezone(TZ8).strftime("%Y-%m-%d") for r in rows if r[0]},
        reverse=True,
    )
    return dates


@router.get("/archive")
async def archive(request: Request, date: str = "", category: str = "", keyword: str = ""):
    dates = _available_dates()
    active_category = category if category in CATEGORIES else "全部"
    keyword = keyword.strip()

    if keyword:
        items = _query_by_keyword(keyword, active_category)
        active_date = ""
    else:
        active_date = date if date in dates else (dates[0] if dates else "")
        items = _query_by_date(active_date, active_category) if active_date else []

    return templates.TemplateResponse("archive.html", {
        "request": request,
        "dates": dates,
        "active_date": active_date,
        "active_category": active_category,
        "categories": CATEGORIES,
        "items": items,
        "total": len(items),
        "keyword": keyword,
        "active_nav": "archive",
    })
