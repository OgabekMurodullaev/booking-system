import redis
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Health check",
        description="Returns the status of the database and Redis connections.",
        responses={200: dict, 503: dict},
    )
    def get(self, request):
        db_ok = self._check_db()
        redis_ok = self._check_redis()
        ok = db_ok and redis_ok
        return Response(
            {
                "status": "ok" if ok else "error",
                "db": "ok" if db_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
            status=200 if ok else 503,
        )

    @staticmethod
    def _check_db() -> bool:
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except OperationalError:
            return False

    @staticmethod
    def _check_redis() -> bool:
        try:
            client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            return bool(client.ping())
        except redis.RedisError:
            return False
