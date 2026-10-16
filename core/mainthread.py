import queue
import threading

import bpy

_queue = queue.Queue()
_interval = 0.02
_active = False


class _Job:
    __slots__ = ("func", "event", "result", "error", "cancelled")

    def __init__(self, func):
        self.func = func
        self.event = threading.Event()
        self.result = None
        self.error = None
        self.cancelled = False


def is_main_thread():
    return threading.current_thread() is threading.main_thread()


def pump(budget=0.25):
    import time
    deadline = time.perf_counter() + budget
    while True:
        try:
            job = _queue.get_nowait()
        except queue.Empty:
            break
        if job is None:
            continue
        if not job.cancelled:
            try:
                job.result = job.func()
            except BaseException as exc:
                job.error = exc
        job.event.set()
        if time.perf_counter() > deadline:
            break


def _timer():
    if not _active:
        return None
    pump()
    return _interval


def run(func, timeout=120.0):
    if is_main_thread():
        return func()
    job = _Job(func)
    _queue.put(job)
    if not job.event.wait(timeout):
        job.cancelled = True
        raise TimeoutError("Blender main thread did not respond in time. Is a modal dialog or long render blocking it?")
    if job.error is not None:
        raise job.error
    return job.result


def post(func):
    if is_main_thread():
        try:
            func()
        except Exception as exc:
            print(f"[MCP Pro] {exc}")
        return
    job = _Job(func)
    _queue.put(job)


def start():
    global _active
    _active = True
    if not bpy.app.timers.is_registered(_timer):
        bpy.app.timers.register(_timer, first_interval=_interval, persistent=True)


def stop():
    global _active
    _active = False
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)
    while True:
        try:
            job = _queue.get_nowait()
        except queue.Empty:
            break
        if job is not None:
            job.error = RuntimeError("Add-on was disabled")
            job.event.set()
