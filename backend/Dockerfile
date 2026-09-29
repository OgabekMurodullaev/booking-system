# ---- base: shared OS deps, non-root user ----
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app
WORKDIR /app

# ---- builder: install Python deps into --user site-packages ----
FROM base AS builder
COPY requirements/ requirements/
RUN pip install --no-cache-dir --user -r requirements/dev.txt

# ---- dev: bind-mounted code, runserver, used by web/worker/beat in docker-compose ----
FROM base AS dev
COPY --from=builder /root/.local /app/.local
ENV PATH=/app/.local/bin:$PATH
COPY . .
RUN chown -R app:app /app
USER app
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---- prod-builder: install only production deps ----
FROM base AS prod-builder
COPY requirements/ requirements/
RUN pip install --no-cache-dir --user -r requirements/prod.txt

# ---- prod: minimal image, no dev/test deps, code baked in, gunicorn ----
FROM base AS prod
COPY --from=prod-builder /root/.local /app/.local
ENV PATH=/app/.local/bin:$PATH
COPY . .
# STATIC_ROOT must exist (and be owned by app) before docker-compose.prod.yml's
# staticfiles volume mounts here — an empty named volume takes the ownership of
# whatever's already at its mount point in the image, and Docker otherwise creates a
# fresh, root-owned empty directory there, which the non-root app user then can't
# write collectstatic's output into.
RUN mkdir -p /app/staticfiles && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
