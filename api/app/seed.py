from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def ensure_seed_data() -> None:
    """
    Placeholder for seed data initialization.
    
    Currently does nothing - no application users are created during seeding.
    Database users (admin and API worker) are created by the database init scripts.
    """
    logger.info("ensure_seed_data: No seed data to create.")


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    ensure_seed_data()
