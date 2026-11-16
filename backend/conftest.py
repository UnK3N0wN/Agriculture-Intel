import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Start and end every test with an empty cache so throttles/lockouts don't leak between tests."""
    cache.clear()
    yield
    cache.clear()