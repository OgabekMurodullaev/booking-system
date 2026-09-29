# Deploying to a Hetzner VPS

Target: Ubuntu on a Hetzner VPS, Docker installed, a domain pointed at the server (or
`<server-ip>.sslip.io` if you don't have one yet). Everything runs behind Caddy, which gets
its own HTTPS certificate automatically via Let's Encrypt.

## 1. Server hardening (do this once, before anything else)

- **Non-root deploy user.** Don't deploy or SSH in as `root`.
  ```bash
  adduser deploy
  usermod -aG sudo,docker deploy
  ```
- **SSH keys only, no password auth.** In `/etc/ssh/sshd_config`:
  ```
  PasswordAuthentication no
  PermitRootLogin no
  ```
  then `systemctl restart sshd`. Copy your public key to `~deploy/.ssh/authorized_keys` first,
  and confirm you can log in with it, *before* disabling password auth.
- **Firewall (`ufw`).** Only SSH, HTTP, HTTPS:
  ```bash
  ufw default deny incoming
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw enable
  ```
- **`fail2ban`** for SSH brute-force protection: `apt install fail2ban` (default jail config
  covers `sshd` out of the box).
- **`unattended-upgrades`** for security patches: `apt install unattended-upgrades` and enable
  it (`dpkg-reconfigure -plow unattended-upgrades`).
- **Swap**, if the VPS has less than ~2GB RAM (Postgres + Redis + gunicorn + Celery all
  running at once will otherwise OOM under load):
  ```bash
  fallocate -l 2G /swapfile && chmod 600 /swapfile
  mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ```

## 2. First deploy — exact checklist

Run each step in order; don't move to the next one until the expected result actually
happens. This is written so a failure at any step tells you exactly where to look, rather than
discovering something's wrong three steps later.

1. **Install Docker** (if not already): follow Docker's official install script for Ubuntu,
   then confirm:
   ```bash
   docker compose version
   ```
   → expect a version string, no error.

2. **Clone the repo** to `/opt/booking-system` (the path every script and workflow in this
   project assumes):
   ```bash
   git clone <your-repo-url> /opt/booking-system
   cd /opt/booking-system
   ```

3. **Create `backend/.env`** from `backend/.env.example`, filled in for production:
   - `DJANGO_SECRET_KEY` — generate a real one, don't reuse the example:
     ```bash
     python3 -c "import secrets; print(secrets.token_urlsafe(50))"
     ```
   - `DEBUG=False` (harmless either way — `config.settings.prod` hardcodes `DEBUG = False`
     regardless of this value, but keep it accurate).
   - `DJANGO_ALLOWED_HOSTS=your-domain.com` (no scheme, no port).
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.com` (full origin, with scheme).
   - `DATABASE_URL=postgres://booking:<the same password as deploy/.env>@db:5432/booking`
   - `REDIS_URL=redis://redis:6379/0`, `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` the same.
   - Real SMTP creds for `EMAIL_*` (or leave the console backend if you're fine with
     notifications only showing up in `docker compose logs web`).

4. **Create `deploy/.env`** from `deploy/.env.example`:
   - `DOMAIN=your-domain.com` (or `<server-ip>.sslip.io`).
   - `ACME_CA` — **leave this set to Let's Encrypt's staging directory for your first attempt**
     (`https://acme-staging-v02.api.letsencrypt.org/directory`), so a misconfiguration doesn't
     burn against Let's Encrypt's production rate limits. Switch it to blank (production) only
     once step 8 below succeeds against staging.
   - `POSTGRES_PASSWORD` — generate a real one, and use the *same* value in `backend/.env`'s
     `DATABASE_URL`.

5. **DNS**: point an A record for your domain at the server's IP (skip if using
   `<ip>.sslip.io`, which already resolves that way). Confirm before continuing:
   ```bash
   dig +short your-domain.com
   ```
   → expect your server's IP.

6. **Bring the stack up:**
   ```bash
   docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d --build
   ```
   → expect all 6 services (`db`, `redis`, `web`, `worker`, `beat`, `caddy`) to show `Up` in
   `docker compose -f deploy/docker-compose.prod.yml ps`.

7. **Check the web service actually came up healthy** (it waits for the DB, runs migrations
   and `collectstatic` before gunicorn starts — give it ~30-60s on first boot):
   ```bash
   docker compose -f deploy/docker-compose.prod.yml logs web --tail 50
   ```
   → expect to see `"Database is up."`, then Django migration output, then gunicorn's "Booting
   worker" lines, no tracebacks.

8. **Smoke-check locally on the server**, before trusting DNS/TLS:
   ```bash
   curl -f http://localhost/api/v1/health/
   ```
   → expect HTTP 200 and a JSON body reporting both Postgres and Redis OK. If this fails, the
   problem is in the app/compose stack, not TLS/DNS — fix it here before going further.

9. **Check HTTPS from outside** (from your own machine, not the server):
   ```bash
   curl -fI https://your-domain.com/api/v1/health/
   ```
   → expect `HTTP/2 200`. The first request may take a few seconds while Caddy obtains its
   certificate. If you're on `ACME_CA` staging, your browser will show a certificate warning —
   that's expected on staging certs; it means TLS issuance itself is working.

10. **Check a deep link survives a refresh** (proves the SPA fallback in the Caddyfile works):
    open `https://your-domain.com/login` directly in a browser (not by clicking through from
    `/`) → expect the login page to render, not a 404.

11. **Switch off staging** once 9 and 10 both pass: set `ACME_CA=` (blank) in `deploy/.env`,
    then:
    ```bash
    docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d caddy
    ```
    → re-run step 9; the certificate warning should be gone.

12. **Set up the backup cron job:**
    ```bash
    crontab -e
    ```
    add:
    ```
    0 3 * * * /opt/booking-system/deploy/backup.sh >> /var/log/booking-backup.log 2>&1
    ```
    then confirm it works once by hand: `/opt/booking-system/deploy/backup.sh` → expect a new
    `.sql.gz` file under `/opt/booking-system/backups/`.

13. **GitHub Actions secrets**, for `deploy.yml` (which is manual-trigger only right now — see
    below): under the repo's Settings → Secrets and variables → Actions, add `DEPLOY_HOST`,
    `DEPLOY_USER` (e.g. `deploy`), `DEPLOY_SSH_KEY` (a private key whose public half is in that
    user's `authorized_keys`), and `DEPLOY_DOMAIN`. Run the workflow once by hand (Actions tab
    → Deploy → Run workflow) and confirm it goes green before ever wiring it to run
    automatically.

## 3. Enabling automatic deploys

`deploy.yml` currently only runs via manual `workflow_dispatch` on purpose — this project has
never deployed to a real server before, so auto-deploy-on-merge stays off until a manual run
has actually succeeded end to end (step 13 above). Once it has, edit
`.github/workflows/deploy.yml`: replace the `on: workflow_dispatch: {}` block with the
commented-out `workflow_run` block already in the file, and add
`if: github.event.workflow_run.conclusion == 'success'` to the `deploy` job.

## 4. Environment variable reference

### `backend/.env` (Django/Celery — see `backend/.env.example`)

| Variable | Used in prod for |
|---|---|
| `DJANGO_SECRET_KEY` | Django's cryptographic signing — generate a real random value |
| `DEBUG` | Ignored in prod (`config.settings.prod` hardcodes `DEBUG = False`) |
| `DJANGO_ALLOWED_HOSTS` | Your domain, no scheme |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Your domain, **with** scheme (`https://...`) |
| `SECURE_SSL_REDIRECT` | Defaults `True` — redirects any stray plain-HTTP request to HTTPS |
| `SECURE_HSTS_SECONDS` | Defaults to 1 week; raise once the deploy is confirmed stable |
| `DATABASE_URL` | Points at the `db` service, must match `deploy/.env`'s Postgres creds |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Point at the `redis` service |
| `EMAIL_*` | Real SMTP creds, or leave the console backend if that's acceptable for now |

### `deploy/.env` (Docker Compose — see `deploy/.env.example`)

| Variable | Purpose |
|---|---|
| `DOMAIN` | Site address Caddy serves; also drives automatic HTTPS |
| `ACME_CA` | Leave blank for real certs; set to LE staging while testing |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Must match `backend/.env`'s `DATABASE_URL` |

### GitHub Actions secrets (for `deploy.yml`)

| Secret | Purpose |
|---|---|
| `DEPLOY_HOST` | Server IP or hostname |
| `DEPLOY_USER` | SSH user (e.g. `deploy`) |
| `DEPLOY_SSH_KEY` | Private key matching that user's `authorized_keys` |
| `DEPLOY_DOMAIN` | Used for the post-deploy `curl` smoke check |

## 5. Assumptions I could not verify locally

This section was built and reviewed carefully, but the following were **not** actually
exercised end to end — flagging them rather than claiming a false "verified":

- **`docker compose -f deploy/docker-compose.prod.yml up --build` was never run.** Docker
  Desktop's daemon isn't running in the dev environment this was built in (confirmed:
  `docker ps` fails to reach the daemon). What *was* verified: `docker compose ... config`
  (client-side YAML parsing + `${VAR}` interpolation) succeeded cleanly and resolved all six
  services, build contexts, volumes, and the env-file/environment merge exactly as designed.
  The actual image builds, container startup, health checks, and the Caddy→web→Postgres
  request path have not been run.
- **`entrypoint.sh` and `backup.sh`** were checked with `bash -n` (syntax only) — no
  `shellcheck` binary was available to lint them, and neither has actually executed inside a
  container.
- **The Caddyfile** was checked by careful reading against Caddy's documented syntax (global
  options block, `acme_ca` with a placeholder default, `handle`/`file_server`/`try_files`) —
  no local `caddy` binary was available to run `caddy validate` against it.
- **`deploy.yml` has never run.** No real VPS, DNS record, or GitHub Actions secrets exist yet
  for this project — the workflow is manual-trigger-only specifically so the first real run is
  a deliberate, watched action per the checklist above, not an assumption that it works.
- **`python manage.py check --deploy` was run against `config.settings.prod`** with dummy env
  vars and came back clean except for two expected warnings: a weak dummy `SECRET_KEY` (real
  deploys must generate a proper one — see step 3) and `SECURE_HSTS_PRELOAD` being off (a
  deliberate choice, not an oversight — see the comment in `prod.py`).
