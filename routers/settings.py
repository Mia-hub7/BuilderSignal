from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_session, Builder

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CATEGORIES = ["lab", "founder", "builder", "observer", "podcast", "blog"]


MSG_MAP = {
    "added":     ("success", "Builder 已添加成功"),
    "duplicate": ("error",   "该 Builder 已存在"),
    "deleted":   ("success", "Builder 已删除"),
    "nodelete":  ("error",   "默认 Builder 不可删除"),
    "enabled":   ("success", "Builder 已启用"),
    "disabled":  ("success", "Builder 已禁用"),
    "error":     ("error",   "操作失败，请重试"),
}


@router.get("/settings")
async def settings(request: Request, msg: str = ""):
    with get_session() as session:
        builders = session.query(Builder).order_by(Builder.category, Builder.name).all()
        builder_list = [
            {
                "id": b.id,
                "name": b.name,
                "handle": b.handle or "",
                "category": b.category or "",
                "bio": b.bio or "",
                "is_active": b.is_active,
            }
            for b in builders
        ]
    msg_type, msg_text = MSG_MAP.get(msg, ("", ""))
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "builders": builder_list,
        "total": len(builder_list),
        "categories": CATEGORIES,
        "active_nav": "settings",
        "msg_type": msg_type,
        "msg_text": msg_text,
    })


@router.post("/settings/builder/toggle")
async def toggle_builder(builder_id: int = Form(...)):
    with get_session() as session:
        b = session.query(Builder).filter_by(id=builder_id).first()
        if b:
            b.is_active = 0 if b.is_active else 1
            msg = "disabled" if not b.is_active else "enabled"
        else:
            msg = "error"
    return RedirectResponse(url=f"/settings?msg={msg}", status_code=303)


@router.post("/settings/builder/add")
async def add_builder(
    name: str = Form(...),
    handle: str = Form(""),
    category: str = Form(...),
    bio: str = Form(""),
    rss_url: str = Form(""),
):
    name = name.strip()
    handle = handle.strip()
    bio = bio.strip()
    rss_url = rss_url.strip()

    if not name:
        return RedirectResponse(url="/settings", status_code=303)

    with get_session() as session:
        exists = session.query(Builder).filter_by(name=name, category=category).first()
        if exists:
            return RedirectResponse(url="/settings?msg=duplicate", status_code=303)
        session.add(Builder(
            name=name,
            handle=handle or None,
            bio=bio or None,
            rss_url=rss_url or None,
            category=category,
            is_default=0,
            is_active=1,
        ))
    return RedirectResponse(url="/settings?msg=added", status_code=303)


@router.post("/settings/builder/delete")
async def delete_builder(builder_id: int = Form(...)):
    with get_session() as session:
        b = session.query(Builder).filter_by(id=builder_id, is_default=0).first()
        if b:
            session.delete(b)
            msg = "deleted"
        else:
            msg = "nodelete"
    return RedirectResponse(url=f"/settings?msg={msg}", status_code=303)
