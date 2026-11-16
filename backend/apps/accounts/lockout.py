import hashlib
import math
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle


@dataclass(frozen=True)
class LockStatus:
    locked: bool
    retry_after_seconds: int = 0


def get_client_ip(request):
    """Same IP logic DRF uses for throttling (honours NUM_PROXIES in production)."""
    return BaseThrottle().get_ident(request)


def _digest(username, ip):
    raw = f"{username.strip().lower()}|{ip}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _fail_key(digest):
    return f"login:fail:{digest}"


def _lock_key(digest):
    return f"login:lock:{digest}"


def check_locked(username, ip):
    digest = _digest(username, ip)
    until = cache.get(_lock_key(digest))
    if until is None:
        return LockStatus(False)
    remaining = math.ceil(float(until) - time.time())
    if remaining <= 0:
        cache.delete(_lock_key(digest))
        return LockStatus(False)
    return LockStatus(True, remaining)


def register_failure(username, ip):
    """Count one wrong attempt. Returns (LockStatus, attempts_remaining)."""
    digest = _digest(username, ip)
    max_attempts = settings.LOGIN_MAX_ATTEMPTS
    window = settings.LOGIN_LOCKOUT_SECONDS
    fail_key = _fail_key(digest)

    cache.add(fail_key, 0, timeout=window)  # creates the counter only if missing
    try:
        count = cache.incr(fail_key)  # atomic increment
    except ValueError:  # counter expired between the two calls
        cache.set(fail_key, 1, timeout=window)
        count = 1

    if count >= max_attempts:
        cache.set(_lock_key(digest), time.time() + window, timeout=window)
        cache.delete(fail_key)
        return LockStatus(True, window), 0
    return LockStatus(False), max_attempts - count


def reset(username, ip):
    digest = _digest(username, ip)
    cache.delete_many([_fail_key(digest), _lock_key(digest)])