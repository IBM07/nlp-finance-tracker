# InvoiceFlow — AI-Powered Finance Tracker

A full-stack, multi-user personal finance tracker. Users log expenses in plain English
(e.g. `I spent 250 on groceries yesterday using UPI`) and the backend uses an LLM (Groq)
to translate that into a validated, parameterized database operation.

## Tech stack

**Backend**
- FastAPI (Python)
- PostgreSQL via [Neon](https://neon.tech) (SQLite supported for local dev)
- SQLAlchemy + Alembic migrations
- JWT authentication with refresh token rotation/revocation
- Groq LLM for natural-language → query translation
- SQL guard layer to block dangerous/unintended queries
- Rate limiting via `slowapi`

**Frontend**
- React + Vite
- React Router
- Axios
- Recharts (dashboard charts)

## Project structure

```
nlp-finance-tracker/
├── backend/
│   ├── app/
│   │   ├── auth/           # signup/login, JWT, token rotation
│   │   ├── finance/        # NLP query handling, SQL guard, transactions
│   │   ├── middleware/     # rate limiting
│   │   ├── config.py       # env-var driven settings (pydantic-settings)
│   │   ├── database.py
│   │   ├── models.py
│   │   └── main.py         # FastAPI app entrypoint
│   ├── alembic/             # DB migrations
│   ├── tests/                # auth, finance, sql_guard tests
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api/             # axios client
    │   ├── components/
    │   ├── context/         # auth context
    │   ├── pages/           # Login, Signup, Dashboard, Settings
    │   └── config.js
    ├── package.json
    └── .env.example
```

## Quick start (local development)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

cp .env.example .env         # fill in GROQ_API_KEY, JWT_SECRET, etc.
alembic upgrade head         # run DB migrations

uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` (interactive docs at `/docs`).

### Frontend

```bash
cd frontend
npm install
cp .env.example .env         # point at your backend API URL
npm run dev
```

The app will be available at `http://localhost:5173`.

## Environment variables

See `backend/.env.example` and `frontend/.env.example` for the full list. Key backend
variables:

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key for LLM-powered query parsing |
| `DATABASE_URL` | Postgres (Neon) or SQLite connection string |
| `JWT_SECRET` | Secret used to sign access/refresh tokens — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | JWT signing algorithm (default `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins |

**Never commit `.env` files.** Both `backend/.env` and `frontend/.env` are gitignored.

## Testing

```bash
cd backend
pytest
```

Covers auth flows, finance/transaction endpoints, and the SQL guard layer.

## Security notes

- All secrets are loaded from environment variables — nothing is hardcoded in source.
- User-submitted natural-language queries are translated to SQL by the LLM and then
  validated by a SQL guard layer before execution (blocks destructive/out-of-scope statements).
- JWT access tokens are short-lived; refresh tokens support rotation and revocation.
- CORS origins are configurable per environment (no wildcard in production).

## License

MIT — feel free to reuse the code.
