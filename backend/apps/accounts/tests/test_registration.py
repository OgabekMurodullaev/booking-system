import threading
from unittest.mock import patch

import pytest
from django.db import connections
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User

REGISTER_URL = "/api/v1/auth/register/"


def _payload(**overrides):
    payload = {
        "email": "new.customer@example.com",
        "full_name": "New Customer",
        "password": "a-very-strong-pass-123",
        "timezone": "Asia/Tashkent",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_register_creates_customer(api_client: APIClient):
    response = api_client.post(REGISTER_URL, _payload(), format="json")

    assert response.status_code == 201
    assert response.json()["role"] == "customer"
    user = User.objects.get(email="new.customer@example.com")
    assert user.role == User.Role.CUSTOMER
    assert user.check_password("a-very-strong-pass-123")


@pytest.mark.django_db
def test_register_ignores_role_in_request_body(api_client: APIClient):
    response = api_client.post(REGISTER_URL, _payload(role="admin"), format="json")

    assert response.status_code == 201
    user = User.objects.get(email="new.customer@example.com")
    assert user.role == User.Role.CUSTOMER


@pytest.mark.django_db
def test_register_duplicate_email_case_insensitive_rejected(api_client: APIClient):
    User.objects.create_user(
        email="dup@example.com", password="a-very-strong-pass-123", full_name="Existing"
    )

    response = api_client.post(REGISTER_URL, _payload(email="Dup@Example.com"), format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_register_invalid_timezone_rejected_with_standard_envelope(api_client: APIClient):
    response = api_client.post(REGISTER_URL, _payload(timezone="Mars/Phobos"), format="json")

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "timezone" in body["error"]["details"]


@pytest.mark.django_db
def test_register_weak_password_rejected(api_client: APIClient):
    response = api_client.post(REGISTER_URL, _payload(password="12345678"), format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_register_password_similar_to_email_rejected(api_client: APIClient):
    response = api_client.post(
        REGISTER_URL,
        _payload(email="samplevalue@example.com", password="samplevalue123456"),
        format="json",
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "password" in body["error"]["details"]


@pytest.mark.django_db
@patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"auth_register": "2/min"})
def test_register_throttled_after_limit(api_client: APIClient):
    for i in range(2):
        response = api_client.post(
            REGISTER_URL, _payload(email=f"user{i}@example.com"), format="json"
        )
        assert response.status_code == 201

    response = api_client.post(REGISTER_URL, _payload(email="user-over-limit@example.com"))

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_registration_only_one_succeeds():
    barrier = threading.Barrier(2)
    results = []

    def attempt():
        barrier.wait()
        try:
            client = APIClient()
            response = client.post(REGISTER_URL, _payload(email="race@example.com"), format="json")
            results.append(response.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [201, 400]
    assert User.objects.filter(email="race@example.com").count() == 1
