from tft_meta.collector.rate_limiter import SlidingWindow


def test_window_allows_requests_until_full():
    window = SlidingWindow(max_requests=2, window_seconds=1)
    window.record(0.0)
    assert window.wait_time(0.1) == 0.0
    window.record(0.1)
    assert window.wait_time(0.2) > 0


def test_full_window_waits_until_oldest_request_leaves():
    window = SlidingWindow(max_requests=2, window_seconds=1)
    window.record(0.0)
    window.record(0.5)
    # The request at 0.0 leaves the window at 1.0
    assert window.wait_time(0.6) == 1.0 - 0.6


def test_old_requests_are_forgotten():
    window = SlidingWindow(max_requests=1, window_seconds=120)
    window.record(0.0)
    assert window.wait_time(119.0) == 1.0
    assert window.wait_time(120.0) == 0.0
