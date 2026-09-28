import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"

PASSWORD = "a-very-strong-pass-123"


def _register_and_login(api_client: APIClient, email="flow@example.com"):
    api_client.post(
        REGISTER_URL,
        {
            "email": email,
            "full_name": "Flow User",
            "password": PASSWORD,
            "timezone": "Asia/Tashkent",
        },
        format="json",
    )
    response = api_client.post(LOGIN_URL, {"email": email, "password": PASSWORD}, format="json")
    return response.json()


@pytest.mark.django_db
def test_full_auth_lifecycle(api_client: APIClient):
    tokens = _register_and_login(api_client)
    assert "access" in tokens
    assert "refresh" in tokens
    assert tokens["user"]["email"] == "flow@example.com"
    assert tokens["user"]["role"] == "customer"

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    me_response = api_client.get(ME_URL)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "flow@example.com"

    refresh_response = api_client.post(REFRESH_URL, {"refresh": tokens["refresh"]}, format="json")
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    assert "access" in new_tokens
    assert "refresh" in new_tokens

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_tokens['access']}")
    logout_response = api_client.post(LOGOUT_URL, {"refresh": new_tokens["refresh"]}, format="json")
    assert logout_response.status_code == 205

    reuse_response = api_client.post(REFRESH_URL, {"refresh": new_tokens["refresh"]}, format="json")
    assert reuse_response.status_code == 401


@pytest.mark.django_db
def test_login_wrong_password_returns_401(api_client: APIClient):
    User.objects.create_user(email="wrongpass@example.com", password=PASSWORD, full_name="X")

    response = api_client.post(
        LOGIN_URL, {"email": "wrongpass@example.com", "password": "wrong"}, format="json"
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_me_get_requires_authentication(api_client: APIClient):
    response = api_client.get(ME_URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_me_patch_updates_full_name_and_timezone_only(api_client: APIClient):
    tokens = _register_and_login(api_client, email="patch@example.com")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    response = api_client.patch(
        ME_URL, {"full_name": "Updated Name", "timezone": "Europe/Berlin"}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"
    assert response.json()["timezone"] == "Europe/Berlin"


@pytest.mark.django_db
def test_me_patch_cannot_change_role_or_email(api_client: APIClient):
    tokens = _register_and_login(api_client, email="noescalate@example.com")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    response = api_client.patch(
        ME_URL,
        {"role": "admin", "email": "new@example.com", "full_name": "Still Me"},
        format="json",
    )

    assert response.status_code == 200
    user = User.objects.get(email="noescalate@example.com")
    assert user.role == User.Role.CUSTOMER
    assert user.full_name == "Still Me"


@pytest.mark.django_db
def test_refresh_with_invalid_token_returns_401(api_client: APIClient):
    response = api_client.post(REFRESH_URL, {"refresh": "not-a-real-token"}, format="json")

    assert response.status_code == 401


@pytest.mark.django_db
def test_logout_requires_authentication(api_client: APIClient):
    response = api_client.post(LOGOUT_URL, {"refresh": "irrelevant"}, format="json")

    assert response.status_code == 401


@pytest.mark.django_db
def test_logout_with_missing_refresh_field_returns_400(api_client: APIClient):
    tokens = _register_and_login(api_client, email="missingrefresh@example.com")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    response = api_client.post(LOGOUT_URL, {}, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
