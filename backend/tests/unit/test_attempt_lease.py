from datetime import UTC, datetime, timedelta

from app.services.attempt_lease import should_fail

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def test_startup_fails_a_processing_row_this_process_is_not_running() -> None:
    assert should_fail(NOW + timedelta(seconds=20), NOW, live=False, startup=True)


def test_a_live_task_is_not_failed() -> None:
    assert not should_fail(NOW - timedelta(seconds=1), NOW, live=True, startup=True)
    assert not should_fail(None, NOW, live=True, startup=False)


def test_a_future_lease_survives_until_it_passes() -> None:
    assert not should_fail(NOW + timedelta(seconds=1), NOW, live=False, startup=False)
    assert should_fail(NOW - timedelta(seconds=1), NOW, live=False, startup=False)
    assert should_fail(None, NOW, live=False, startup=False)
