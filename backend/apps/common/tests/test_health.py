from unittest.mock import patch

import pytest
import redis
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_endpoint_returns_200_when_healthy(api_client: APIClient):
    response = api_client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "redis": "ok"}


@pytest.mark.django_db
def test_health_endpoint_returns_503_when_redis_down(api_client: APIClient):
    with patch("apps.common.views.redis.Redis.from_url") as from_url:
        from_url.return_value.ping.side_effect = redis.RedisError("down")

        response = api_client.get("/api/v1/health/")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "ok", "redis": "error"}
