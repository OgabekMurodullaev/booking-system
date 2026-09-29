"""Seed realistic, demoable data: one business, 3 providers, 5 services, 15 customers,
and ~60 bookings spanning the past and next 14 days across every status.

Reuses the real domain services (apps.catalog.services.providers.create_provider,
apps.scheduling.services.working_hours.replace_working_hours, and the booking
hold/submit/confirm/cancel pipeline in apps.bookings.services.booking) for everything a
live user flow could produce — the one exception is historical (past-dated) bookings,
which create_hold's own lead-time validation correctly refuses to create; those are built
directly via the ORM, mirroring exactly what create_hold computes, with matching
BookingStatusLog rows written by hand so their status-log timeline still reads sensibly.
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone as django_timezone
from psycopg.types.range import Range

from apps.accounts.models import User
from apps.bookings.models import Booking, BookingStatusLog
from apps.bookings.services.booking import (
    cancel_booking,
    confirm_booking,
    create_hold,
    submit_booking,
)
from apps.catalog.models import Business, Provider, Service
from apps.catalog.services.providers import create_provider
from apps.scheduling.models import TimeOff, WorkingHours
from apps.scheduling.services.availability import get_available_slots
from apps.scheduling.services.intervals import subtract_intervals
from apps.scheduling.services.working_hours import replace_working_hours

BUSINESS_NAME = "Demo Salon"
BUSINESS_TIMEZONE = "Asia/Tashkent"
EMAIL_DOMAIN = "bookingsystem.test"
DEMO_PASSWORD = "DemoPass123!"

DEMO_CUSTOMER_EMAIL = f"demo.customer@{EMAIL_DOMAIN}"
DEMO_PROVIDER_EMAIL = f"demo.provider@{EMAIL_DOMAIN}"
DEMO_ADMIN_EMAIL = f"demo.admin@{EMAIL_DOMAIN}"

SERVICE_DEFS = [
    {"name": "Haircut", "duration_minutes": 30, "buffer_minutes": 5, "price": Decimal("80000")},
    {"name": "Beard Trim", "duration_minutes": 20, "buffer_minutes": 5, "price": Decimal("40000")},
    {
        "name": "Hair Coloring",
        "duration_minutes": 90,
        "buffer_minutes": 15,
        "price": Decimal("250000"),
    },
    {"name": "Manicure", "duration_minutes": 45, "buffer_minutes": 10, "price": Decimal("100000")},
    {
        "name": "Facial Treatment",
        "duration_minutes": 60,
        "buffer_minutes": 10,
        "price": Decimal("180000"),
    },
]

# (full_name, email, [service names offered])
PROVIDER_DEFS = [
    ("Demo Provider", DEMO_PROVIDER_EMAIL, ["Haircut", "Beard Trim", "Hair Coloring"]),
    ("Nodira Aliyeva", f"provider2@{EMAIL_DOMAIN}", ["Manicure", "Facial Treatment"]),
    ("Sardor Tashkentov", f"provider3@{EMAIL_DOMAIN}", ["Haircut", "Manicure"]),
]

CUSTOMER_FULL_NAMES = [
    "Dilnoza Yusupova",
    "Javlon Rashidov",
    "Malika Ergasheva",
    "Otabek Nazarov",
    "Zarina Tursunova",
    "Farrux Islomov",
    "Kamola Ahmedova",
    "Sherzod Yoldashev",
    "Gulnora Saidova",
    "Jasur Karimov",
    "Nilufar Rahimova",
    "Bekzod Umarov",
    "Sevara Mirzaeva",
    "Rustam Abdullayev",
    "Feruza Xolmatova",
]


class Command(BaseCommand):
    help = "Seed realistic demo data (idempotent; pass --reset to rebuild from scratch)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete existing demo data before seeding."
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()
        elif Business.objects.filter(name=BUSINESS_NAME).exists():
            self.stdout.write(
                self.style.WARNING(f'"{BUSINESS_NAME}" already exists. Use --reset to rebuild.')
            )
            return

        random.seed(1234)  # deterministic demo data across runs

        business = Business.objects.create(
            name=BUSINESS_NAME,
            timezone=BUSINESS_TIMEZONE,
            auto_confirm=False,
            cancellation_window_hours=24,
        )
        User.objects.create_user(
            email=DEMO_ADMIN_EMAIL,
            password=DEMO_PASSWORD,
            full_name="Demo Admin",
            role=User.Role.ADMIN,
            business=business,
            timezone=BUSINESS_TIMEZONE,
        )

        services = self._create_services(business)
        providers = self._create_providers(business, services)
        self._create_working_hours(providers)
        self._create_time_off(providers[1])
        customers = self._create_customers()
        counts = self._create_bookings(business, providers, services, customers)

        self.stdout.write(self.style.SUCCESS("\nSeed complete."))
        self.stdout.write(f"  Business:  {business.name} ({business.timezone})")
        self.stdout.write(
            f"  Providers: {len(providers)}   "
            f"Services: {len(services)}   "
            f"Customers: {len(customers)}"
        )
        self.stdout.write(f"  Bookings:  {sum(counts.values())} - {dict(counts)}")
        self.stdout.write(f"\nDemo accounts (password for all: {DEMO_PASSWORD}):")
        self.stdout.write(f"  customer  {DEMO_CUSTOMER_EMAIL}")
        self.stdout.write(f"  provider  {DEMO_PROVIDER_EMAIL}")
        self.stdout.write(f"  admin     {DEMO_ADMIN_EMAIL}")

    def _reset(self):
        # Staff (admin/providers) are matched by business, not email domain, so this also
        # cleans up a same-named "Demo Salon" left over from anything other than this
        # command (e.g. manual testing) — anything attached to that business is, by
        # definition, disposable demo data. Customers have no business FK, so they're
        # matched by the seed email domain instead.
        business = Business.objects.filter(name=BUSINESS_NAME).first()
        deleted_staff = 0
        if business is not None:
            deleted_staff, _ = User.objects.filter(business=business).delete()
        deleted_customers, _ = User.objects.filter(
            email__iendswith=f"@{EMAIL_DOMAIN}", role=User.Role.CUSTOMER
        ).delete()
        deleted_business, _ = Business.objects.filter(name=BUSINESS_NAME).delete()
        self.stdout.write(
            f"Reset: removed {deleted_staff} staff row(s), {deleted_customers} customer "
            f"row(s), {deleted_business} business row(s)."
        )

    # -- fixtures -----------------------------------------------------------------

    def _create_services(self, business: Business) -> list[Service]:
        return [Service.objects.create(business=business, **defn) for defn in SERVICE_DEFS]

    def _create_providers(self, business: Business, services: list[Service]) -> list[Provider]:
        by_name = {s.name: s for s in services}
        providers = []
        for full_name, email, service_names in PROVIDER_DEFS:
            provider = create_provider(
                business=business,
                email=email,
                full_name=full_name,
                password=DEMO_PASSWORD,
                service_ids=[by_name[name].id for name in service_names],
            )
            provider.user.timezone = BUSINESS_TIMEZONE
            provider.user.save(update_fields=["timezone"])
            providers.append(provider)
        return providers

    def _create_working_hours(self, providers: list[Provider]) -> None:
        # Monday=0 .. Sunday=6 (matches date.weekday(), the convention used throughout
        # apps.scheduling). Open Mon-Sat, closed Sunday, for all three providers.
        weekdays = range(0, 6)

        # Provider 1: lunch break (two intervals/day).
        entries = [
            {"weekday": wd, "start_time": time(9, 0), "end_time": time(13, 0)} for wd in weekdays
        ] + [{"weekday": wd, "start_time": time(14, 0), "end_time": time(18, 0)} for wd in weekdays]
        replace_working_hours(providers[0], entries)

        # Providers 2 and 3: continuous hours.
        entries = [
            {"weekday": wd, "start_time": time(9, 0), "end_time": time(18, 0)} for wd in weekdays
        ]
        replace_working_hours(providers[1], entries)
        replace_working_hours(providers[2], entries)

    def _create_time_off(self, provider: Provider) -> None:
        # Lands inside the next 14 days, demoable on the provider Time Off page.
        now = django_timezone.now()
        start = (now + timedelta(days=5)).replace(hour=9, minute=0, second=0, microsecond=0)
        TimeOff.objects.create(
            provider=provider, start=start, end=start + timedelta(days=2), reason="Personal leave"
        )

    def _create_customers(self) -> list[User]:
        customers = [
            User.objects.create_user(
                email=DEMO_CUSTOMER_EMAIL,
                password=DEMO_PASSWORD,
                full_name="Demo Customer",
                role=User.Role.CUSTOMER,
                timezone=BUSINESS_TIMEZONE,
            )
        ]
        for i, full_name in enumerate(CUSTOMER_FULL_NAMES, start=2):
            customers.append(
                User.objects.create_user(
                    email=f"customer{i}@{EMAIL_DOMAIN}",
                    password=DEMO_PASSWORD,
                    full_name=full_name,
                    role=User.Role.CUSTOMER,
                    timezone=BUSINESS_TIMEZONE,
                )
            )
        return customers

    # -- bookings -------------------------------------------------------------------

    def _create_bookings(
        self,
        business: Business,
        providers: list[Provider],
        services: list[Service],
        customers: list[User],
    ) -> dict[str, int]:
        now = django_timezone.now()
        zone = ZoneInfo(business.timezone)
        counts: dict[str, int] = {"completed": 0, "confirmed": 0, "pending": 0, "cancelled": 0}

        # Plan: 30 past bookings (completed/cancelled, plus a couple left confirmed-but-past
        # to demo the "mark completed" affordance) + 30 future ones (confirmed/pending/cancelled).
        past_plan = ["completed"] * 20 + ["cancelled"] * 8 + ["confirmed"] * 2
        future_plan = ["confirmed"] * 14 + ["pending"] * 10 + ["cancelled"] * 6
        random.shuffle(past_plan)
        random.shuffle(future_plan)

        already_blocked: dict[int, list[tuple[datetime, datetime]]] = {p.id: [] for p in providers}

        for target_status in past_plan:
            local_date = self._random_open_date(now.astimezone(zone).date(), -14, -1)
            if self._seed_past_booking(
                target_status,
                local_date,
                providers,
                services,
                customers,
                zone,
                business,
                already_blocked,
            ):
                counts[target_status] += 1

        # The demo customer is the account reviewers actually click around as, so its "My
        # Bookings" > Upcoming tab shouldn't come up empty by chance — guarantee it a
        # confirmed and a pending booking rather than leaving that to random assignment.
        demo_customer = next(c for c in customers if c.email == DEMO_CUSTOMER_EMAIL)
        forced_customer_for_index = {}
        for status in ("confirmed", "pending"):
            index = next(i for i, s in enumerate(future_plan) if s == status)
            forced_customer_for_index[index] = demo_customer

        for index, target_status in enumerate(future_plan):
            local_date = self._random_open_date(now.astimezone(zone).date(), 0, 13)
            if self._seed_future_booking(
                target_status,
                local_date,
                providers,
                services,
                customers,
                now,
                forced_customer=forced_customer_for_index.get(index),
            ):
                counts[target_status] += 1

        return counts

    def _random_open_date(self, today: date, min_offset: int, max_offset: int) -> date:
        # All providers are closed Sunday (weekday 6) — a date on which nothing has working
        # hours at all would otherwise waste every retry attempt in the caller. Resample
        # instead of retrying provider/service combinations against a dead date.
        for _ in range(25):
            offset = random.randint(min_offset, max_offset)
            candidate = today + timedelta(days=offset)
            if candidate.weekday() != 6:
                return candidate
        return today

    def _provider_and_service_for(
        self, providers: list[Provider], services: list[Service]
    ) -> tuple[Provider, Service]:
        provider = random.choice(providers)
        service = random.choice(list(provider.services.all()))
        return provider, service

    def _grid_starts(self, start_time: time, end_time: time, duration_minutes: int) -> list[time]:
        start_total = start_time.hour * 60 + start_time.minute
        end_total = end_time.hour * 60 + end_time.minute
        starts = []
        total = start_total
        while total + duration_minutes <= end_total:
            starts.append(time(total // 60, total % 60))
            total += 15
        return starts

    def _seed_past_booking(
        self,
        target_status: str,
        local_date: date,
        providers: list[Provider],
        services: list[Service],
        customers: list[User],
        zone: ZoneInfo,
        business: Business,
        already_blocked: dict[int, list[tuple[datetime, datetime]]],
    ) -> bool:
        for _ in range(25):
            provider, service = self._provider_and_service_for(providers, services)
            weekday = local_date.weekday()
            intervals = list(
                WorkingHours.objects.filter(provider=provider, weekday=weekday).order_by(
                    "start_time"
                )
            )
            if not intervals:
                continue
            interval = random.choice(intervals)
            starts = self._grid_starts(
                interval.start_time, interval.end_time, service.duration_minutes
            )
            if not starts:
                continue
            local_start = random.choice(starts)
            start = datetime.combine(local_date, local_start, tzinfo=zone)
            end = start + timedelta(minutes=service.duration_minutes)
            blocked_end = end + timedelta(minutes=service.buffer_minutes)

            time_off_overlap = TimeOff.objects.filter(
                provider=provider, start__lt=blocked_end, end__gt=start
            ).exists()
            if time_off_overlap:
                continue

            free = subtract_intervals([(start, blocked_end)], already_blocked[provider.id])
            if free != [(start, blocked_end)]:
                continue

            customer = random.choice(customers)
            try:
                booking = self._insert_direct_booking(
                    customer, provider, service, start, end, blocked_end, target_status, business
                )
            except IntegrityError:
                continue
            already_blocked[provider.id].append((start, blocked_end))
            self._log_history_for(booking, target_status)
            return True
        return False

    def _insert_direct_booking(
        self,
        customer: User,
        provider: Provider,
        service: Service,
        start: datetime,
        end: datetime,
        blocked_end: datetime,
        target_status: str,
        business: Business,
    ) -> Booking:
        is_late = False
        if target_status == "cancelled" and random.random() < 0.4:
            is_late = True
        return Booking.objects.create(
            customer=customer,
            provider=provider,
            service=service,
            time_range=Range(start, end),
            blocked_range=Range(start, blocked_end),
            status=Booking.Status.CANCELLED if target_status == "cancelled" else target_status,
            price_snapshot=service.price,
            duration_snapshot=service.duration_minutes,
            expires_at=None,
            submitted_at=start - timedelta(days=1),
            is_late_cancellation=is_late,
            cancellation_reason="Schedule conflict" if target_status == "cancelled" else "",
        )

    def _log_history_for(self, booking: Booking, target_status: str) -> None:
        BookingStatusLog.objects.create(
            booking=booking,
            from_status="",
            to_status="pending",
            actor=booking.customer,
            reason="hold_created",
        )
        BookingStatusLog.objects.create(
            booking=booking,
            from_status="pending",
            to_status="pending",
            actor=booking.customer,
            reason="submitted",
        )
        if target_status in ("completed", "confirmed"):
            BookingStatusLog.objects.create(
                booking=booking,
                from_status="pending",
                to_status="confirmed",
                actor=booking.provider.user,
                reason="",
            )
            if target_status == "completed":
                BookingStatusLog.objects.create(
                    booking=booking,
                    from_status="confirmed",
                    to_status="completed",
                    actor=booking.provider.user,
                    reason="",
                )
        elif target_status == "cancelled":
            actor = random.choice([booking.customer, booking.provider.user, None])
            BookingStatusLog.objects.create(
                booking=booking,
                from_status="pending",
                to_status="cancelled",
                actor=actor,
                reason=booking.cancellation_reason,
            )

    def _seed_future_booking(
        self,
        target_status: str,
        local_date: date,
        providers: list[Provider],
        services: list[Service],
        customers: list[User],
        now: datetime,
        forced_customer: User | None = None,
    ) -> bool:
        for _ in range(25):
            provider, service = self._provider_and_service_for(providers, services)
            slots = get_available_slots(
                service=service,
                date_from=local_date,
                date_to=local_date,
                provider=provider,
                now=now,
            )
            if not slots:
                continue
            slot = random.choice(slots)
            customer = forced_customer or random.choice(customers)
            try:
                result = create_hold(
                    customer=customer, service=service, provider=provider, start=slot.start, now=now
                )
            except Exception:
                continue
            if not result.created:
                continue
            booking = result.booking

            try:
                if target_status == "pending":
                    submit_booking(booking, actor=customer, now=now)
                elif target_status == "confirmed":
                    submit_booking(booking, actor=customer, now=now)
                    booking.refresh_from_db()
                    confirm_booking(booking, actor=provider.user, now=now)
                elif target_status == "cancelled":
                    submit_booking(booking, actor=customer, now=now)
                    booking.refresh_from_db()
                    actor = random.choice([customer, provider.user])
                    cancel_booking(booking, actor=actor, reason="Change of plans", now=now)
            except Exception:
                # Leave the hold in place rather than lose the slot silently — still a
                # valid, if unintended, pending booking.
                pass
            return True
        return False
