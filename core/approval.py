import threading
import uuid

pending = {}
lock = threading.Lock()


def request(name, arguments, cancelled):
    key = uuid.uuid4().hex
    event = threading.Event()
    item = {"name": name, "arguments": arguments, "event": event, "allowed": False}
    with lock:
        pending[key] = item
    try:
        while not event.wait(0.2):
            if cancelled.is_set():
                return False
        return item["allowed"]
    finally:
        with lock:
            pending.pop(key, None)


def decide(key, allowed):
    with lock:
        item = pending.get(key)
        if item:
            item["allowed"] = allowed
            item["event"].set()


def reject_all():
    with lock:
        for item in pending.values():
            item["allowed"] = False
            item["event"].set()
