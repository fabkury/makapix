"""Playset generation service for player commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from .. import models


@dataclass
class PlaysetChannel:
    """Single channel in a playset."""

    type: Literal["named", "user", "hashtag", "sdcard"]
    identifier: str | None = None  # sqid for user, tag for hashtag
    name: str | None = None  # "all" or "promoted" for named type
    display_name: str | None = None  # e.g., "@handle" or "#tag"
    weight: int | None = None  # for manual exposure mode

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result: dict = {"type": self.type}
        if self.name is not None:
            result["name"] = self.name
        if self.identifier is not None:
            result["identifier"] = self.identifier
        if self.display_name is not None:
            result["display_name"] = self.display_name
        if self.weight is not None:
            result["weight"] = self.weight
        return result


@dataclass
class Playset:
    """Playset configuration."""

    name: str
    channels: list[PlaysetChannel] = field(default_factory=list)
    exposure_mode: Literal["equal", "manual", "proportional"] = "equal"
    pick_mode: Literal["recency", "random"] = "recency"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "playset_name": self.name,
            "channels": [ch.to_dict() for ch in self.channels],
            "exposure_mode": self.exposure_mode,
            "pick_mode": self.pick_mode,
        }


class PlaysetService:
    """Service for generating playset configurations."""

    # Known dynamic playset names
    FOLLOWED_ARTISTS = "followed_artists"

    @staticmethod
    def get_playset(
        db: Session,
        owner: models.User,
        playset_name: str,
    ) -> Playset | None:
        """
        Get a playset by name for a given user.

        Args:
            db: Database session
            owner: The user requesting the playset (player owner)
            playset_name: Name of the playset to retrieve

        Returns:
            Playset configuration or None if not found
        """
        if playset_name == PlaysetService.FOLLOWED_ARTISTS:
            return PlaysetService._generate_followed_artists_playset(db, owner)

        # Unknown playset name
        return None

    @staticmethod
    def _generate_followed_artists_playset(
        db: Session,
        owner: models.User,
    ) -> Playset:
        """
        Generate a playset containing all artists the owner follows.

        Includes only verified, active users (not banned/deactivated).
        Returns playset with empty channels list if owner follows no one.

        Args:
            db: Database session
            owner: The user whose followed artists to include

        Returns:
            Playset with user channels for each followed artist
        """
        # Query all users that the owner follows
        # Join Follow table with User to get followed user details
        followed_users = (
            db.query(models.User)
            .join(models.Follow, models.Follow.following_id == models.User.id)
            .filter(
                models.Follow.follower_id == owner.id,
                # Only include verified users
                models.User.email_verified.is_(True),
                # Exclude deactivated users
                models.User.deactivated.is_(False),
                # Exclude banned users (banned_until is NULL or in the past)
                models.User.banned_until.is_(None),
            )
            .order_by(models.Follow.created_at.desc())
            .all()
        )

        # Build channel list
        channels = []
        for user in followed_users:
            channels.append(
                PlaysetChannel(
                    type="user",
                    identifier=user.public_sqid,
                    display_name=f"@{user.handle}",
                )
            )

        return Playset(
            name=PlaysetService.FOLLOWED_ARTISTS,
            channels=channels,
            exposure_mode="equal",
            pick_mode="random",
        )
