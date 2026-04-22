import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/buildersignal.db")
DATABASE_URL = os.getenv("DATABASE_URL", "")
TZ = os.getenv("TZ", "Asia/Shanghai")
FEED_FETCH_HOUR = int(os.getenv("FEED_FETCH_HOUR", "15"))
SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY", "")
