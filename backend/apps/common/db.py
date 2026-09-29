from django.db import OperationalError


def is_deadlock(exc: OperationalError) -> bool:
    """True if `exc` is a genuine Postgres deadlock (SQLSTATE 40P01), not some other
    operational failure that should keep propagating.

    Two concurrent INSERTs racing the same unique index (or exclusion constraint) can
    occasionally deadlock rather than raise a clean IntegrityError — a documented Postgres
    behavior, not a bug in the schema. The deadlock victim's transaction is already rolled
    back automatically; treating it the same as a lost race (retry, or fail with the same
    clean error a straightforward constraint violation would produce) is correct and avoids
    leaking a raw 500 to the client.
    """
    cause = exc.__cause__
    return getattr(cause, "sqlstate", None) == "40P01"
