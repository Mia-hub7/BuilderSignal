import os
from contextlib import contextmanager
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text,
    ForeignKey, create_engine, text, inspect
)
from sqlalchemy.orm import declarative_base, sessionmaker

import config

if config.DATABASE_URL:
    engine = create_engine(config.DATABASE_URL)
else:
    os.makedirs(os.path.dirname(os.path.abspath(config.DATABASE_PATH)), exist_ok=True)
    engine = create_engine(
        f"sqlite:///{config.DATABASE_PATH}",
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Builder(Base):
    __tablename__ = "builders"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String, nullable=False)
    handle     = Column(String, nullable=True)
    rss_url    = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    bio        = Column(String, nullable=True)
    category   = Column(String, nullable=True)
    is_default = Column(Integer, default=1)
    is_active  = Column(Integer, default=1)
    created_at = Column(DateTime, default=utcnow)


class RawContent(Base):
    __tablename__ = "raw_content"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    builder_id   = Column(Integer, ForeignKey("builders.id"), nullable=True)
    source       = Column(String, nullable=False)
    content_id   = Column(String, unique=True, nullable=False)
    url          = Column(String, nullable=False)
    raw_text     = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    fetched_at   = Column(DateTime, default=utcnow)
    is_processed = Column(Integer, default=0)


class Summary(Base):
    __tablename__ = "summaries"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    raw_content_id = Column(Integer, ForeignKey("raw_content.id"), nullable=True)
    builder_id     = Column(Integer, ForeignKey("builders.id"), nullable=True)
    category_tag   = Column(String, nullable=True)
    summary_zh     = Column(Text, nullable=True)
    summary_en     = Column(Text, nullable=True)
    original_url   = Column(String, nullable=True)
    published_at   = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=utcnow)
    is_visible     = Column(Integer, default=1)


class Config(Base):
    __tablename__ = "config"

    key   = Column(String, primary_key=True)
    value = Column(String, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe migration: add bio column if not exists (works for SQLite and PostgreSQL)
    inspector = inspect(engine)
    if "builders" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("builders")]
        if "bio" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE builders ADD COLUMN bio TEXT"))
                conn.commit()


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {config.DATABASE_PATH}")
