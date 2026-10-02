import threading

from chassis.consumer.lane import run_consumer_lane


class NoWaitEvent(threading.Event):
    """Skips the backoff sleep so the retry path runs instantly."""

    def wait(self, timeout=None):
        return self.is_set()


class RecordingStop(threading.Event):
    def __init__(self):
        super().__init__()
        self.waits = []

    def wait(self, timeout=None):
        self.waits.append(timeout)
        return self.is_set()


class _Loop:
    def __init__(self, runs):
        self._runs = runs

    def run(self, stop):
        self._runs.append(1)


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_a_consumer_lane_builds_a_new_consumer_after_each_failure_until_one_runs():
    ready, stop = threading.Event(), NoWaitEvent()
    ready.set()
    runs, builds = [], []

    def build():
        builds.append(1)
        if len(builds) <= 2:
            raise RuntimeError("cannot subscribe")
        stop.set()
        return _Loop(runs)

    run_consumer_lane("g", build, ready, stop)

    assert len(builds) == 3
    assert runs == [1]


def test_a_consumer_lane_survives_a_loop_that_dies_while_running():
    ready, stop = threading.Event(), NoWaitEvent()
    ready.set()
    builds = []

    class _FatalThenFine:
        def __init__(self, fail):
            self._fail = fail

        def run(self, stop):
            if self._fail:
                raise RuntimeError("fatal kafka error")
            stop.set()

    def build():
        builds.append(1)
        return _FatalThenFine(fail=len(builds) == 1)

    run_consumer_lane("g", build, ready, stop)

    assert len(builds) == 2


def test_a_stop_during_the_backoff_ends_the_lane_promptly():
    ready, stop = threading.Event(), threading.Event()
    ready.set()
    started = threading.Event()

    def build():
        started.set()
        raise RuntimeError("broker down")

    lane = threading.Thread(target=run_consumer_lane, args=("g", build, ready, stop))
    lane.start()
    assert started.wait(2)
    stop.set()
    lane.join(timeout=2)

    assert not lane.is_alive()


def test_a_stop_before_the_topics_are_ready_ends_the_lane_without_building():
    ready, stop = threading.Event(), threading.Event()
    stop.set()
    builds = []

    run_consumer_lane("g", lambda: builds.append(1), ready, stop)

    assert builds == []


def test_consecutive_failures_double_the_delay_up_to_the_cap():
    ready, stop, clock = threading.Event(), RecordingStop(), _Clock()
    ready.set()
    builds = []

    def build():
        builds.append(1)
        if len(builds) == 8:
            stop.set()
        raise RuntimeError("down")

    run_consumer_lane("g", build, ready, stop, max_backoff_seconds=10.0, clock=clock)

    assert stop.waits == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0, 10.0, 10.0]


def test_a_failure_after_a_long_run_resets_the_delay_to_one_second():
    ready, stop, clock = threading.Event(), RecordingStop(), _Clock()
    ready.set()
    builds = []

    def build():
        builds.append(1)
        # The third consumer ran for longer than the cap before failing.
        clock.now += 31.0 if len(builds) == 3 else 0.0
        if len(builds) == 4:
            stop.set()
        raise RuntimeError("down")

    run_consumer_lane("g", build, ready, stop, clock=clock)

    assert stop.waits == [1.0, 2.0, 1.0, 2.0]
