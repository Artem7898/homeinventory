# HomeInventory

HomeInventory helps households, workshops and small groups keep track of possessions, storage locations and loans. It uses Django 5.2 LTS and Python 3.14.

The shared model consists of private workspaces, members, locations, containers and items. Owner, editor and viewer roles control access. Public sharing is explicit and exposes a separate title and description; it does not make the private inventory public.

The application includes item forms, photos, search, QR labels, movement history, loans and workspace export/import. It is not an accounting system or an insurance valuation service. AI, complete offline synchronisation and automated notifications remain conditional roadmap items.

## Development

```bash
git clone https://github.com/Artem7898/homeinventory.git
cd homeinventory
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt
cp .env.example .env
```

Set `DEBUG=True` for local development. Configure `PUBLIC_BASE_URL` to the actual address reachable by devices scanning labels; a phone's `localhost` is the phone itself. Camera access on a phone generally requires HTTPS.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver 127.0.0.1:8000
```

Sign in and create a workspace. There is no public signup. The administrator creates accounts; workspace owners assign membership roles. PostgreSQL installation requires its client development libraries. SQLite is available for a local personal installation.

```bash
python manage.py test --settings=config.test_settings
python manage.py makemigrations --check --dry-run --settings=config.test_settings
```

Back up the database and media before updating. Legacy data is migrated into a private workspace initially accessible only to superusers; assigning an owner is an explicit operation. Production needs a strong secret key, exact hosts/origins, HTTPS and persistent private media storage. Never serve media directly around application authorisation.

See the [deployment guide](docs/DEPLOYMENT.md), [audit response](docs/AUDIT-RESPONSE.md), [roadmap](docs/ROADMAP.md) and [contribution guide](CONTRIBUTING.md). The detailed operational documentation is currently in Russian.

No project licence has been chosen by the owner yet. The previous MIT badge did not grant an MIT licence. Third-party components retain their own licences.
