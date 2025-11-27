"""
Sitewide statistics aggregation service.

Provides on-demand computation of sitewide statistics with Redis caching.
Aggregates data from raw site events (7 days) and daily rollups (8-30 days).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5 minutes)
STATS_CACHE_TTL = 300


@dataclass
class DailyCount:
    """Daily count data."""
    date: str  # ISO format date string
    count: int


@dataclass
class HourlyCount:
    """Hourly count data."""
    hour: str  # ISO format datetime of hour start
    count: int


@dataclass
class SitewideStats:
    """Complete sitewide statistics."""
    # Summary metrics (30 days)
    total_page_views_30d: int
    unique_visitors_30d: int
    new_signups_30d: int
    new_posts_30d: int
    total_api_calls_30d: int
    total_errors_30d: int
    
    # Trends (30 days)
    daily_views: list[DailyCount]
    daily_signups: list[DailyCount]
    daily_posts: list[DailyCount]
    
    # Granular data (last 24h from events)
    hourly_views: list[HourlyCount]
    
    # Breakdowns
    views_by_page: dict[str, int]
    views_by_country: dict[str, int]
    views_by_device: dict[str, int]
    top_referrers: dict[str, int]
    
    # Error tracking
    errors_by_type: dict[str, int]
    
    computed_at: str  # ISO format datetime
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_page_views_30d": self.total_page_views_30d,
            "unique_visitors_30d": self.unique_visitors_30d,
            "new_signups_30d": self.new_signups_30d,
            "new_posts_30d": self.new_posts_30d,
            "total_api_calls_30d": self.total_api_calls_30d,
            "total_errors_30d": self.total_errors_30d,
            "daily_views": [{"date": d.date, "count": d.count} for d in self.daily_views],
            "daily_signups": [{"date": d.date, "count": d.count} for d in self.daily_signups],
            "daily_posts": [{"date": d.date, "count": d.count} for d in self.daily_posts],
            "hourly_views": [{"hour": h.hour, "count": h.count} for h in self.hourly_views],
            "views_by_page": self.views_by_page,
            "views_by_country": self.views_by_country,
            "views_by_device": self.views_by_device,
            "top_referrers": self.top_referrers,
            "errors_by_type": self.errors_by_type,
            "computed_at": self.computed_at,
        }


class SiteStatsService:
    """
    Service for computing and caching sitewide statistics.
    
    Statistics are computed on-demand and cached in Redis for 5 minutes.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_sitewide_stats(self) -> SitewideStats | None:
        """
        Get sitewide statistics.
        
        Checks Redis cache first, then computes if cache miss.
        
        Returns:
            SitewideStats object
        """
        from ..cache import cache_get, cache_set
        from .. import models
        
        # Check Redis cache
        cache_key = "sitewide_stats"
        cached_data = cache_get(cache_key)
        if cached_data:
            logger.debug("Sitewide stats cache hit")
            return self._dict_to_stats(cached_data)
        
        # Compute fresh stats
        logger.debug("Sitewide stats cache miss, computing...")
        stats = self._compute_stats()
        
        # Cache the result
        cache_set(cache_key, stats.to_dict(), ttl=STATS_CACHE_TTL)
        
        return stats
    
    def invalidate_cache(self) -> None:
        """Invalidate the sitewide stats cache."""
        from ..cache import cache_delete
        
        cache_key = "sitewide_stats"
        cache_delete(cache_key)
    
    def _compute_stats(self) -> SitewideStats:
        """
        Compute sitewide statistics from the database.
        
        Aggregates data from:
        - site_events table (last 7 days of raw events)
        - site_stats_daily table (older aggregated data, 8-30 days)
        """
        from .. import models
        
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        # ===== GET RAW EVENTS (last 7 days) =====
        
        recent_events = self.db.query(models.SiteEvent).filter(
            models.SiteEvent.created_at >= seven_days_ago
        ).all()
        
        # ===== GET DAILY AGGREGATES (8-30 days ago) =====
        
        daily_stats = self.db.query(models.SiteStatsDaily).filter(
            models.SiteStatsDaily.date >= thirty_days_ago.date(),
            models.SiteStatsDaily.date < seven_days_ago.date()
        ).all()
        
        # ===== AGGREGATE SUMMARY METRICS (30 days) =====
        
        # From recent events
        page_views_from_events = sum(1 for e in recent_events if e.event_type == "page_view")
        signups_from_events = sum(1 for e in recent_events if e.event_type == "signup")
        posts_from_events = sum(1 for e in recent_events if e.event_type == "upload")
        api_calls_from_events = sum(1 for e in recent_events if e.event_type == "api_call")
        errors_from_events = sum(1 for e in recent_events if e.event_type == "error")
        
        unique_visitors_from_events = len(set(
            e.visitor_ip_hash for e in recent_events if e.event_type == "page_view"
        ))
        
        # From daily aggregates
        total_page_views_30d = page_views_from_events + sum(ds.total_page_views for ds in daily_stats)
        unique_visitors_30d = unique_visitors_from_events + sum(ds.unique_visitors for ds in daily_stats)
        new_signups_30d = signups_from_events + sum(ds.new_signups for ds in daily_stats)
        new_posts_30d = posts_from_events + sum(ds.new_posts for ds in daily_stats)
        total_api_calls_30d = api_calls_from_events + sum(ds.total_api_calls for ds in daily_stats)
        total_errors_30d = errors_from_events + sum(ds.total_errors for ds in daily_stats)
        
        # ===== DAILY TRENDS (30 days) =====
        
        # Initialize all 30 days with zeros
        daily_views: list[DailyCount] = []
        daily_signups: list[DailyCount] = []
        daily_posts: list[DailyCount] = []
        
        for i in range(30):
            day = (now - timedelta(days=i)).date()
            day_str = day.isoformat()
            daily_views.append(DailyCount(date=day_str, count=0))
            daily_signups.append(DailyCount(date=day_str, count=0))
            daily_posts.append(DailyCount(date=day_str, count=0))
        
        # Create lookup dicts
        daily_views_lookup = {d.date: d for d in daily_views}
        daily_signups_lookup = {d.date: d for d in daily_signups}
        daily_posts_lookup = {d.date: d for d in daily_posts}
        
        # Fill in data from recent events (last 7 days)
        for event in recent_events:
            day_str = event.created_at.date().isoformat()
            if day_str in daily_views_lookup:
                if event.event_type == "page_view":
                    daily_views_lookup[day_str].count += 1
                elif event.event_type == "signup":
                    daily_signups_lookup[day_str].count += 1
                elif event.event_type == "upload":
                    daily_posts_lookup[day_str].count += 1
        
        # Fill in data from daily aggregates (older than 7 days)
        for ds in daily_stats:
            day_str = ds.date.isoformat()
            if day_str in daily_views_lookup:
                daily_views_lookup[day_str].count = ds.total_page_views
                daily_signups_lookup[day_str].count = ds.new_signups
                daily_posts_lookup[day_str].count = ds.new_posts
        
        # Sort by date ascending (oldest first)
        daily_views.sort(key=lambda x: x.date)
        daily_signups.sort(key=lambda x: x.date)
        daily_posts.sort(key=lambda x: x.date)
        
        # ===== HOURLY BREAKDOWN (last 24h from events) =====
        
        hourly_views: list[HourlyCount] = []
        
        # Get events from last 24 hours
        recent_24h_events = [e for e in recent_events if e.created_at >= twenty_four_hours_ago and e.event_type == "page_view"]
        
        # Group by hour
        views_by_hour: dict[str, int] = {}
        for event in recent_24h_events:
            # Round down to hour
            hour_start = event.created_at.replace(minute=0, second=0, microsecond=0)
            hour_str = hour_start.isoformat()
            views_by_hour[hour_str] = views_by_hour.get(hour_str, 0) + 1
        
        # Initialize all 24 hours with zeros
        for i in range(24):
            hour_start = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
            hour_str = hour_start.isoformat()
            hourly_views.append(HourlyCount(
                hour=hour_str,
                count=views_by_hour.get(hour_str, 0)
            ))
        
        # Sort by hour ascending (oldest first)
        hourly_views.sort(key=lambda x: x.hour)
        
        # ===== BREAKDOWNS =====
        
        # Views by page (from recent events + daily aggregates)
        views_by_page: dict[str, int] = {}
        for event in recent_events:
            if event.event_type == "page_view" and event.page_path:
                views_by_page[event.page_path] = views_by_page.get(event.page_path, 0) + 1
        for ds in daily_stats:
            for page, count in (ds.views_by_page or {}).items():
                views_by_page[page] = views_by_page.get(page, 0) + count
        
        # Sort and keep top 20
        views_by_page = dict(sorted(views_by_page.items(), key=lambda x: -x[1])[:20])
        
        # Views by country (from recent events + daily aggregates)
        views_by_country: dict[str, int] = {}
        for event in recent_events:
            if event.event_type == "page_view" and event.country_code:
                views_by_country[event.country_code] = views_by_country.get(event.country_code, 0) + 1
        for ds in daily_stats:
            for country, count in (ds.views_by_country or {}).items():
                views_by_country[country] = views_by_country.get(country, 0) + count
        
        # Sort and keep top 10
        views_by_country = dict(sorted(views_by_country.items(), key=lambda x: -x[1])[:10])
        
        # Views by device (from recent events + daily aggregates)
        views_by_device: dict[str, int] = {}
        for event in recent_events:
            if event.event_type == "page_view":
                views_by_device[event.device_type] = views_by_device.get(event.device_type, 0) + 1
        for ds in daily_stats:
            for device, count in (ds.views_by_device or {}).items():
                views_by_device[device] = views_by_device.get(device, 0) + count
        
        # Top referrers (from recent events + daily aggregates)
        top_referrers: dict[str, int] = {}
        for event in recent_events:
            if event.event_type == "page_view" and event.referrer_domain:
                top_referrers[event.referrer_domain] = top_referrers.get(event.referrer_domain, 0) + 1
        for ds in daily_stats:
            for referrer, count in (ds.top_referrers or {}).items():
                top_referrers[referrer] = top_referrers.get(referrer, 0) + count
        
        # Sort and keep top 10
        top_referrers = dict(sorted(top_referrers.items(), key=lambda x: -x[1])[:10])
        
        # Errors by type (from recent events + daily aggregates)
        errors_by_type: dict[str, int] = {}
        for event in recent_events:
            if event.event_type == "error" and event.event_data and "error_type" in event.event_data:
                error_type = str(event.event_data["error_type"])
                errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
        for ds in daily_stats:
            for error_type, count in (ds.errors_by_type or {}).items():
                errors_by_type[error_type] = errors_by_type.get(error_type, 0) + count
        
        # ===== BUILD RESULT =====
        
        return SitewideStats(
            total_page_views_30d=total_page_views_30d,
            unique_visitors_30d=unique_visitors_30d,
            new_signups_30d=new_signups_30d,
            new_posts_30d=new_posts_30d,
            total_api_calls_30d=total_api_calls_30d,
            total_errors_30d=total_errors_30d,
            daily_views=daily_views,
            daily_signups=daily_signups,
            daily_posts=daily_posts,
            hourly_views=hourly_views,
            views_by_page=views_by_page,
            views_by_country=views_by_country,
            views_by_device=views_by_device,
            top_referrers=top_referrers,
            errors_by_type=errors_by_type,
            computed_at=now.isoformat(),
        )
    
    def _dict_to_stats(self, data: dict) -> SitewideStats:
        """Convert dictionary back to SitewideStats object."""
        return SitewideStats(
            total_page_views_30d=data["total_page_views_30d"],
            unique_visitors_30d=data["unique_visitors_30d"],
            new_signups_30d=data["new_signups_30d"],
            new_posts_30d=data["new_posts_30d"],
            total_api_calls_30d=data["total_api_calls_30d"],
            total_errors_30d=data["total_errors_30d"],
            daily_views=[DailyCount(**d) for d in data["daily_views"]],
            daily_signups=[DailyCount(**d) for d in data["daily_signups"]],
            daily_posts=[DailyCount(**d) for d in data["daily_posts"]],
            hourly_views=[HourlyCount(**h) for h in data["hourly_views"]],
            views_by_page=data["views_by_page"],
            views_by_country=data["views_by_country"],
            views_by_device=data["views_by_device"],
            top_referrers=data["top_referrers"],
            errors_by_type=data["errors_by_type"],
            computed_at=data["computed_at"],
        )


def get_sitewide_stats(db: Session) -> SitewideStats:
    """
    Convenience function to get sitewide statistics.
    
    Args:
        db: Database session
        
    Returns:
        SitewideStats object
    """
    service = SiteStatsService(db)
    return service.get_sitewide_stats()

