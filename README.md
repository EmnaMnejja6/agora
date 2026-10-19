# Agora

A tiny, cheerful Flask voting app, built as the shared application for the two-site infrastructure demo.

## App layout

- `app/backend/` — Flask application and environment example
- `app/frontend/templates/` — Jinja2 pages
- `app/frontend/static/` — plain CSS
- `app/database/` — MySQL schema and sample data

## Run locally

Use Python 3.10+ and MySQL 8+. Create a database and a database user, then set `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`, and optionally `SITE_NAME` in your environment. `app/backend/.env.example` lists the expected variables; the application reads environment variables directly and does not automatically load a `.env` file.

From the repository root, install the dependencies and initialize the database:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
mysql -h "$DB_HOST" -u "$DB_USER" -p "$DB_NAME" < app/database/schema.sql
mysql -h "$DB_HOST" -u "$DB_USER" -p "$DB_NAME" < app/database/seed.sql
```

Set a secure `SECRET_KEY` before launch, for example with `export SECRET_KEY="$(openssl rand -hex 32)"`. Then run:

```sh
python app/backend/app.py
```

Visit `http://127.0.0.1:5000`. The sample admin account is `admin` / `AgoraDemo2026!`; change its password before using the demo beyond a local environment. The home page and `/health` (`ok`) are public. Only an admin can create or close polls, and registered users can vote once per poll while it is open.

## Infrastructure demo

The app is deployed on two sites connected by an IPsec tunnel (OPNsense): `site_a/` is 10.0.2.0/24 and `site_b/` is 10.15.15.0/24. To provision a site, for example site B:

```sh
cd site_b
vagrant up
cd ansible && ansible-playbook site.yml
```
