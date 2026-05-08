# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup
```bash
uv sync                          # Install Python dependencies
uv run pre-commit install        # Install git hooks
cd static && npm install         # Install frontend assets
cp example.env .env              # Create local config
```

### Development
```bash
alembic upgrade head             # Run DB migrations
flask dummy-data                 # Load development data
python3 server.py                # Run web app (port 7777)
python email_handler.py          # Run email forwarding service
python job_runner.py             # Run background job processor
python cron.py                   # Run scheduled tasks
```

### Testing
```bash
uv run pytest -c pytest.ci.ini              # Run full test suite
uv run pytest tests/test_email_utils.py    # Run a single test file
uv run pytest tests/test_alias.py -k foo   # Run a specific test
```
Tests require Redis on port 6379. Set `NOT_SEND_EMAIL=true` in `.env` to suppress email during tests.

### Linting & Formatting
```bash
uv run ruff format .                        # Format Python
uv run ruff check .                         # Lint Python
uv run flake8                               # Additional lint checks
uv run djlint --check templates             # Lint HTML templates
uv run djlint --reformat templates          # Format HTML templates
```

### Database
```bash
sh scripts/new-migration.sh                 # Generate new Alembic migration
sh scripts/reset_local_db.sh               # Reset dev DB
sh scripts/reset_test_db.sh                # Reset test DB
```

## Architecture

SimpleLogin is an email alias/privacy service. Three independent processes handle distinct concerns:

1. **Web app** (`server.py` / `wsgi.py`): Flask app serving the UI and REST API
2. **Email handler** (`email_handler.py`): aiosmtpd-based SMTP server that receives and forwards emails (~2500 LOC)
3. **Background jobs** (`job_runner.py`, `cron.py`): Async tasks and scheduled jobs

### Flask App Structure (`app/`)

- **`models.py`** (~4200 LOC): All SQLAlchemy models. Key entities: `User`, `Alias`, `Mailbox`, `Contact`, `EmailLog`, `CustomDomain`, `SLDomain`, `Client` (OAuth apps)
- **`api/`**: REST API — alias management, OAuth endpoints, user settings. Auth via `@require_api_auth` / `@require_api_sudo` decorators
- **`dashboard/`**: Web UI for alias management
- **`auth/`**: Login, signup, 2FA, social OAuth (GitHub/Google/Facebook), WebAuthn
- **`oauth/`**: SimpleLogin as an OAuth/OIDC provider for third-party apps
- **`payments/`**: Stripe, Paddle, Coinbase, Apple subscription handling
- **`proton/`**: Proton Mail partnership integration
- **`admin/`**: Flask-Admin panel
- **`email/`** + **`handler/`**: Email utilities — DKIM, SPF/DMARC, unsubscribe, reply tracking

### Key Utility Modules
- `alias_utils.py`: Alias creation/deletion logic
- `email_utils.py` (~56KB): Core email parsing and formatting
- `custom_domain_utils.py`: Custom domain DNS verification
- `mailbox_utils.py`: Mailbox management
- `pgp_utils.py`: PGP encryption support

### Email Flow
Inbound email → `email_handler.py` → lookup alias → forward to user's mailbox (or block/bounce). Replies from user go back through the handler, rewritten to appear from the alias.

### Configuration
`app/config.py` loads all settings from environment variables (see `example.env`). Key variables: `DB_URI` (PostgreSQL), `EMAIL_DOMAIN`, `POSTFIX_SERVER`, `FLASK_SECRET`, `DKIM_PRIVATE_KEY_PATH`.

### Database Migrations
Uses Alembic. Always run `alembic upgrade head` after pulling changes with new migrations. Migration files live in `migrations/versions/`.
