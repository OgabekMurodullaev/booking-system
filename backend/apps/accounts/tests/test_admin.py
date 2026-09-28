from django.contrib import admin

from apps.accounts.models import User


def test_user_admin_registered():
    assert User in admin.site._registry
