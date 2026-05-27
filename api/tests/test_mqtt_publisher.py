"""Tests for the MQTT publisher client lifecycle.

Regression coverage for the incident where a broker restart permanently wedged
the response publisher: ``on_disconnect`` used paho's v1 (3-4 arg) signature
under ``CallbackAPIVersion.VERSION2``, and ``_ensure_connected`` rebuilt the
client on every failed publish, leaking orphan loop threads.
"""

from __future__ import annotations

import paho.mqtt.client as mqtt_client
import pytest

import app.mqtt.publisher as publisher


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Stub out all socket / loop-thread activity and reset the singleton."""
    monkeypatch.setattr(mqtt_client.Client, "connect_async", lambda *a, **k: None)
    monkeypatch.setattr(mqtt_client.Client, "loop_start", lambda *a, **k: None)
    monkeypatch.setattr(mqtt_client.Client, "loop_stop", lambda *a, **k: None)
    monkeypatch.setattr(mqtt_client.Client, "disconnect", lambda *a, **k: None)
    publisher._client_instance = None
    yield
    publisher._client_instance = None


def test_callbacks_accept_paho_v2_signatures():
    """The callbacks must accept paho VERSION2's five positional arguments.

    Previously ``on_disconnect`` took 3-4 args, so paho raised ``TypeError`` in
    the loop thread on every disconnect and the publisher never reconnected
    after a broker restart.
    """
    client = publisher._make_client()

    # paho 2.x invokes both callbacks with exactly five positional arguments.
    client.on_connect(client, None, {}, mqtt_client.MQTT_ERR_SUCCESS, None)
    client.on_disconnect(client, None, None, mqtt_client.MQTT_ERR_SUCCESS, None)
    # Reaching here without TypeError is the assertion.


def test_ensure_connected_reuses_single_client(monkeypatch):
    """The publisher is created once and never rebuilt per failed publish.

    Even in the worst case (the client never reports "connected"), repeated
    calls must hand back the same instance rather than spawning orphan clients.
    """
    monkeypatch.setattr(mqtt_client.Client, "is_connected", lambda self: False)
    # Skip the connect wait so the test doesn't block.
    monkeypatch.setattr(publisher, "_CONNECT_WAIT_SECONDS", 0)

    first = publisher._ensure_connected()
    second = publisher._ensure_connected()

    assert first is second


def test_publish_returns_false_when_never_confirmed(monkeypatch):
    """publish() returns False (never raises) when the broker never confirms."""

    class _FakeInfo:
        rc = mqtt_client.MQTT_ERR_NO_CONN

        def wait_for_publish(self, timeout=None):
            return None

    monkeypatch.setattr(mqtt_client.Client, "is_connected", lambda self: True)
    monkeypatch.setattr(mqtt_client.Client, "publish", lambda *a, **k: _FakeInfo())
    monkeypatch.setattr(publisher.time, "sleep", lambda *_: None)  # no backoff delay

    result = publisher.publish("makapix/test", {"x": 1}, qos=1, max_retries=2)

    assert result is False


def test_publish_succeeds_on_ack(monkeypatch):
    """publish() returns True when the broker confirms the message."""

    class _FakeInfo:
        rc = mqtt_client.MQTT_ERR_SUCCESS

        def wait_for_publish(self, timeout=None):
            return None

    monkeypatch.setattr(mqtt_client.Client, "is_connected", lambda self: True)
    monkeypatch.setattr(mqtt_client.Client, "publish", lambda *a, **k: _FakeInfo())

    result = publisher.publish("makapix/test", {"x": 1}, qos=1)

    assert result is True


def test_stop_publisher_clears_singleton(monkeypatch):
    """stop_publisher() tears down the loop and resets the shared instance."""
    monkeypatch.setattr(mqtt_client.Client, "is_connected", lambda self: True)

    publisher._ensure_connected()
    assert publisher._client_instance is not None

    publisher.stop_publisher()

    assert publisher._client_instance is None
