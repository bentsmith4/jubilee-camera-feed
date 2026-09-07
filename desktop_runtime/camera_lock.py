"""Bounded per-device acquisition serialization shared by both products."""
import functools
import hashlib
import inspect
import socket
import time

def serialized(function):
    signature = inspect.signature(function)
    @functools.wraps(function)
    def acquire(*args, **kwargs):
        device = signature.bind(*args, **kwargs).arguments['device']
        digest = hashlib.sha256(device['name'].encode()).digest()
        port = 20000 + int.from_bytes(digest[:2], 'big') % 20000
        deadline = time.monotonic() + 75
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as lock:
            while True:
                try:
                    lock.bind(('127.0.0.1', port))
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Camera busy; bounded acquisition wait exhausted')
                    time.sleep(0.25)
            return function(*args, **kwargs)
    return acquire
