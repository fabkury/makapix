"""GeoIP reader hot-reload + refresh task behavior.

The reader must pick up a database file that appears or changes after process
start (the pre-2026-08-25 load-once latch cached "missing" forever, so
country_code stayed NULL until restart even after installing the file).
"""

from __future__ import annotations

import os

import pytest

import app.geoip as geoip


class FakeReader:
    """Stands in for geoip2.database.Reader; records which path it opened."""

    instances: list["FakeReader"] = []

    def __init__(self, path):
        self.path = path
        self.mtime = os.stat(path).st_mtime
        FakeReader.instances.append(self)

    def close(self):
        pass


@pytest.fixture
def geoip_env(tmp_path, monkeypatch):
    """Point the module at a tmp db path and a fake geoip2 Reader."""
    import sys
    from types import SimpleNamespace

    db_path = tmp_path / "GeoLite2-Country.mmdb"
    monkeypatch.setattr(geoip, "GEOIP_DB_PATH", str(db_path))
    fake_geoip2 = SimpleNamespace(database=SimpleNamespace(Reader=FakeReader))
    monkeypatch.setitem(sys.modules, "geoip2", fake_geoip2)
    monkeypatch.setitem(sys.modules, "geoip2.database", fake_geoip2.database)
    FakeReader.instances = []
    geoip.close_reader()  # reset module state
    yield db_path
    geoip.close_reader()


def test_reader_appears_without_restart(geoip_env):
    db_path = geoip_env
    assert geoip._get_reader() is None  # file missing: no reader, no crash

    db_path.write_bytes(b"fake-mmdb")
    reader = geoip._get_reader()
    assert isinstance(reader, FakeReader)
    assert reader.path == str(db_path)


def test_reader_reloads_on_mtime_change(geoip_env):
    db_path = geoip_env
    db_path.write_bytes(b"v1")
    first = geoip._get_reader()
    assert geoip._get_reader() is first  # unchanged mtime: same instance

    db_path.write_bytes(b"v2")
    os.utime(db_path, (first.mtime + 10, first.mtime + 10))
    second = geoip._get_reader()
    assert second is not first
    assert len(FakeReader.instances) == 2


def test_reader_survives_file_vanishing(geoip_env):
    db_path = geoip_env
    db_path.write_bytes(b"v1")
    first = geoip._get_reader()
    db_path.unlink()
    assert geoip._get_reader() is first  # keep serving the loaded copy


def test_refresh_task_skips_without_license_key(monkeypatch):
    from app.tasks import refresh_geoip_database

    monkeypatch.delenv("MAXMIND_LICENSE_KEY", raising=False)
    result = refresh_geoip_database.apply(kwargs={}).get()
    assert result["status"] == "skipped"


def test_refresh_task_skips_fresh_file(tmp_path, monkeypatch):
    import app.tasks as tasks_mod
    from app.tasks import refresh_geoip_database

    db_path = tmp_path / "GeoLite2-Country.mmdb"
    db_path.write_bytes(b"fresh")
    monkeypatch.setenv("MAXMIND_LICENSE_KEY", "test-key")
    monkeypatch.setattr(geoip, "GEOIP_DB_PATH", str(db_path))
    # Any network attempt would mean the freshness check failed.
    monkeypatch.setattr(
        "requests.get", lambda *a, **k: pytest.fail("must not download")
    )
    result = refresh_geoip_database.apply(kwargs={}).get()
    assert result["status"] == "fresh"
