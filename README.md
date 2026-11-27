# AgriIntel

A web app for farmers with two features:

1. **Crop recommender**: ranks crops for a location and month using crop requirements and long-term climate averages.
2. **Leaf disease scanner**: upload a leaf photo and get a likely diagnosis with organic and chemical treatment options and prevention tips.

> **Status:** working in development. A production deployment guide (Docker, Nginx, HTTPS) is in progress.
> **Not agronomic advice.** Crop scores and AI diagnoses are estimates. Check with a local agricultural extension officer before acting. Chemical products and rules vary by country.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2, Django REST Framework, SimpleJWT (rotating refresh tokens with blacklist) |
| Background jobs | Celery + Redis (AI analysis runs off the web request) |
| Database | PostgreSQL |
| Frontend | React 18 + Vite, React Router, Axios, Motion (`motion/react`) for animation |
| AI | Provider adapters: `mock` (free testing), `openai` (vision, also works with OpenAI-compatible services), `plantid` |
| Production | Docker Compose, Nginx, Gunicorn |

## How it works

```
Browser (React)
   │  /api/...
   ▼
Django + DRF ──► PostgreSQL     crops, rules, climate averages, scans, users
   │      └────► Redis           cache, login lockout counters, throttles, job queue
   └─ queues ──► Celery worker ─► AI provider (mock | openai | plantid)
```

- **Recommendations:** `GET /api/crops/recommend/` scores each crop on season (50%), temperature (35%) and rainfall (15%). With climate averages available, it judges the climate across the crop's whole growing period, and the worst month counts extra. Crops without a regional sowing calendar get an estimated season, labelled "Climate estimate".
- **Scans:** the upload is validated by its real bytes, re-encoded as JPEG with EXIF/GPS removed, stored privately under a random name, and analyzed by a Celery task. The browser polls `GET /api/scans/status/<task_id>/` every 3 seconds.

## Folder layout

```
agri-intel/
├── backend/
│   ├── config/            settings (base, dev, prod, test), urls, celery
│   ├── apps/
│   │   ├── accounts/      users, profile, JWT auth, login lockout
│   │   ├── crops/         crops, sowing rules, climate averages, recommender
│   │   ├── scans/         uploads, background jobs, history
│   │   └── ai_integration/  provider adapters, safe error handling
│   ├── data/
│   │   ├── external/      downloaded datasets (git-ignored)
│   │   └── curated/       your own CSVs, such as sowing calendars (committed)
│   └── private_media/     uploaded photos (git-ignored, never served directly)
├── frontend/              React app
└── deploy/                Docker and Nginx files
```

## Quick start (development)

**You need:** Python 3.12 or 3.13 (not 3.14), Node 20+, Docker Desktop.

```bash
# 1. Start PostgreSQL and Redis
docker compose -f deploy/docker-compose.dev.yml up -d

# 2. Backend
cd backend
python -m venv .venv                  # Windows: py -3.12 -m venv .venv
source .venv/bin/activate             # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                  # Windows: Copy-Item .env.example .env
#   edit .env: set DJANGO_SECRET_KEY (any long random value)
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_crops           # demo crops, for development only
python manage.py runserver

# 3. Background worker (second terminal, venv active)
celery -A config worker -l info       # Windows: add --pool=solo

# 4. Frontend (third terminal)
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

`AI_PROVIDER=mock` (the default) needs no keys. To use real analysis set `AI_PROVIDER=openai` and `OPENAI_API_KEY` in `backend/.env`, then restart the server **and** the worker.

## Tests

```bash
cd backend
pytest -v          # backend (uses an in-memory cache and a temporary database)
cd ../frontend
npm run build      # catches front-end compile errors
```

## Real crop and climate data

The seeded crops are **demo values**. For real data:

| Data | Source | How |
|---|---|---|
| Crop requirements (temperature, rainfall, cycle length) | [FAO EcoCrop](https://gaez.fao.org/pages/ecocrop), CSV copy from the [OpenCLIM/ecocrop](https://github.com/OpenCLIM/ecocrop) project | Save `EcoCrop_DB.csv` to `backend/data/external/`, then `python manage.py import_ecocrop data/external/EcoCrop_DB.csv --only "Oryza sativa,Zea mays"`. Start with `--show-columns` and `--dry-run`. |
| Climate averages | [Open-Meteo](https://open-meteo.com) historical weather | Automatic. The server downloads 10 years once per 25 km grid cell and stores the monthly averages. Try `python manage.py show_climate 12.97 77.59`. |
| Sowing calendars | Regional sources you trust (agricultural university, agriculture department) | Put them in a CSV under `backend/data/curated/`, then `python manage.py import_rules <file> --dry-run`. |

Every crop and rule records its `source` and a `verified` flag. Imported data starts **unverified**. Review it in the Django admin and mark it verified. Verified rows are never overwritten by later imports.

**Read before using commercially:** EcoCrop's original source is FAO and the OpenCLIM copy states an Open Government Licence, so check both and credit them. Open-Meteo's free tier is for non-commercial use. EcoCrop covers temperature and rainfall for un-irrigated crops only (no soil, pests or irrigation), and its rainfall figures can be read in more than one way (`--rain-mode season|annual`).

## API overview

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register/`, `login/`, `refresh/`, `logout/`; `GET/PATCH /api/auth/me/` |
| Crops | `GET /api/crops/` (filters `q`, `category`, `water_need`), `GET /api/crops/<slug>/`, `GET /api/crops/recommend/` (`lat`+`lon` or `location_id`, `month`, `category`, `limit`) |
| Locations and bookmarks | `GET/POST /api/crops/locations/`, `DELETE /api/crops/locations/<id>/`, `GET /api/crops/bookmarks/`, `POST/DELETE /api/crops/<slug>/bookmark/` |
| Scans | `POST /api/scans/` (multipart `image`, optional `crop_hint`), `GET /api/scans/status/<task_id>/`, `GET /api/scans/history/`, `GET/DELETE /api/scans/history/<id>/`, `GET /api/scans/history/<id>/image/` |
| Health | `GET /api/health/` |

## Security features

| Protection | How |
|---|---|
| Login lockout | 5 wrong attempts lock a username+IP pair for 15 minutes (Redis-backed) |
| Rate limits | AI scans: 10 per hour and 30 per day per user. Registration: 5 per hour per IP. Anonymous: 120 per hour |
| Uploads | Real file-type check (magic bytes), size and pixel limits, re-encoded and stripped of EXIF/GPS, random file names, stored outside any public folder, streamed only to their owner |
| Tokens | Short-lived access token in memory, rotating refresh tokens with blacklist on logout |
| Secrets | Redacted from logs. Raw provider errors are never shown to users |
| Production settings | Refuses to start with a short or default secret key; HTTPS redirect, secure cookies and HSTS |

## Environment variables

See `backend/.env.example`. The important ones:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Long random value. Never commit it |
| `POSTGRES_*`, `REDIS_URL`, `CELERY_*` | Service connections |
| `AI_PROVIDER` | `mock`, `openai` or `plantid` |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` | Real AI analysis |
| `THROTTLE_*`, `AI_DAILY_CAP_PER_USER` | Rate limits and spending cap |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_SECONDS` | Lockout rules |

`.env` files hold secrets and are git-ignored. Only `.env.example` files are committed.

## Known limitations

- Scores are heuristic estimates that have not been validated by an agronomist.
- Climate zones come only from latitude (no deserts or altitude).
- Perennial crops (fruit trees, coffee) are not modelled well because the "sowing month" idea doesn't fit.
- AI diagnoses can be wrong, and treatments are generic classes, never doses.

## Data sources and credits

- Crop requirements: FAO EcoCrop (via the OpenCLIM/ecocrop CSV).
- Climate: Open-Meteo historical weather.
- Add the sources of any sowing calendars you import.

## ScreenShots

- Dashboard View
<img width="1896" height="857" alt="Dashboard" src="https://github.com/user-attachments/assets/9c78f16a-5db2-40b9-a0e2-f818e85c8d01" />


- Crops View
<img width="1143" height="875" alt="crops" src="https://github.com/user-attachments/assets/20d4732c-2aed-4681-88ce-83e1e25b37e1" />


- Scanning View
<img width="1208" height="862" alt="scan" src="https://github.com/user-attachments/assets/269cebb4-1e69-4a76-8ae7-2804dc1ab2c9" />


- Analysis View
<img width="1160" height="853" alt="analysis" src="https://github.com/user-attachments/assets/02385f7d-47c0-46f7-a816-e36c7a996cf8" />


- Past History
<img width="1250" height="872" alt="history" src="https://github.com/user-attachments/assets/23a025ed-2d9e-49c0-9657-6409de4d23ae" />


## License

Not chosen yet. 
