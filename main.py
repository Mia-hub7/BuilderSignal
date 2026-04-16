from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from database import init_db
from jobs.seed import seed as run_seed
from routers.feed import router as feed_router
from routers.archive import router as archive_router
from routers.settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    run_seed()
    yield


app = FastAPI(title="BuilderSignal", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(feed_router)
app.include_router(archive_router)
app.include_router(settings_router)
