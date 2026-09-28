from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.common.exceptions import DomainError


class _RaisesDomainErrorView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raise DomainError(
            "Slot is no longer available.",
            code="slot_unavailable",
            details={"alternatives": []},
            http_status=409,
        )


class _RaisesValidationErrorView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raise ValidationError({"email": ["This field is required."]})


def test_domain_error_produces_standard_envelope():
    request = APIRequestFactory().get("/fake/")
    response = _RaisesDomainErrorView.as_view()(request)

    assert response.status_code == 409
    assert response.data == {
        "error": {
            "code": "slot_unavailable",
            "message": "Slot is no longer available.",
            "details": {"alternatives": []},
        }
    }


def test_drf_validation_error_produces_standard_envelope():
    request = APIRequestFactory().get("/fake/")
    response = _RaisesValidationErrorView.as_view()(request)

    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert response.data["error"]["message"] == "This field is required."
    assert response.data["error"]["details"] == {"email": ["This field is required."]}
