from celery import shared_task
from django.utils import timezone

from .services.booking import expire_stale_holds


@shared_task
def expire_stale_holds_task() -> int:
    return expire_stale_holds(timezone.now())
