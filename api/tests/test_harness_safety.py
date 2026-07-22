"""Tests for the test-harness safety guards (appraisal O9/O10).

These guard against the suite reaching live infrastructure: tasks must not be
enqueued to the shared broker (the live worker would run them against the live
DB), and startup must not apply migrations to the live DB.
"""


def test_task_delay_is_neutralised():
    """The autouse _no_live_celery fixture stops .delay from hitting the broker.

    Tests that genuinely need a task run call .apply() (eager), which is
    unaffected — this only neutralises fire-and-forget .delay/.apply_async.
    """
    from app.tasks import send_push_notification

    result = send_push_notification.delay(0, "test")
    assert result.id == "test-noop"


def test_run_migrations_skipped_under_test(monkeypatch):
    """run_migrations must be a no-op when TEST_DATABASE_URL is set, so a
    working-tree migration is never applied to the live DB by the test suite."""
    import os

    assert os.getenv("TEST_DATABASE_URL"), "tests must run with TEST_DATABASE_URL"

    from alembic import command

    def _boom(*a, **k):
        raise AssertionError("command.upgrade must not run under test")

    monkeypatch.setattr(command, "upgrade", _boom)

    from app import main

    main.run_migrations()  # must return early without calling command.upgrade
