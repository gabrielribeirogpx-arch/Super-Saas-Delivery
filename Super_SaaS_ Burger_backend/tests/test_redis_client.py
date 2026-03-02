import logging

from app.integrations import redis_client


class DummyRedis:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def ping(self):
        if self.should_fail:
            raise RuntimeError("ping failed")
        return True


def test_get_redis_client_returns_none_without_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert redis_client.get_redis_client() is None


def test_validate_redis_connection_success(monkeypatch, caplog):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis_client.redis, "from_url", lambda _: DummyRedis())

    with caplog.at_level(logging.INFO):
        result = redis_client.validate_redis_connection()

    assert result is True
    assert "Redis connected successfully" in caplog.text


def test_validate_redis_connection_error(monkeypatch, caplog):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis_client.redis, "from_url", lambda _: DummyRedis(should_fail=True))

    with caplog.at_level(logging.ERROR):
        result = redis_client.validate_redis_connection()

    assert result is False
    assert "Failed to connect to Redis" in caplog.text
