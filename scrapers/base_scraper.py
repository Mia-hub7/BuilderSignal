import hashlib
from database import RawContent


def generate_content_id(unique_str: str) -> str:
    return hashlib.sha256(unique_str.encode("utf-8")).hexdigest()


def is_duplicate(content_id: str, session) -> bool:
    exists = session.query(RawContent).filter_by(content_id=content_id).first()
    return exists is not None
