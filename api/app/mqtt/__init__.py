"""MQTT module __init__ for easier imports."""

from __future__ import annotations

from . import notifications, publisher, schemas

# Import publish_demo_message from the legacy module for backward compatibility
try:
    from ..mqtt_legacy import publish_demo_message
except ImportError:
    # Fallback wrapper if legacy module not available
    def publish_demo_message(payload=None):
        """Compatibility wrapper for publish_demo_message."""
        from .publisher import publish

        topic = "posts/new/demo"
        message = payload or {
            "title": "Demo publish",
            "body": "Hello from FastAPI over MQTT!",
        }
        success = publish(topic, message, qos=0, retain=True)
        if not success:
            raise RuntimeError("Failed to publish demo message")
        return topic


__all__ = ["notifications", "publisher", "schemas", "publish_demo_message"]
