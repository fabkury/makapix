from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from .db import get_session


def get_db() -> Generator[Session, None, None]:
    yield from get_session()
