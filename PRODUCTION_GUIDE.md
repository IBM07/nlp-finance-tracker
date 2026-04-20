# 🚀 Production Deployment Guide

## Architecture
This is a single-file Streamlit app.
Run with:

```bash
streamlit run app.py
```

No separate FastAPI service is required for normal usage.

## Secrets
- Local development: add `GROQ_API_KEY` to `.streamlit/secrets.toml`
- Production (Streamlit Cloud): add `GROQ_API_KEY` in **App Settings > Secrets**

Example local file:

```toml
GROQ_API_KEY = "your_key_here"
```

## Database
- `student.db` is created automatically on first run.
- The `Finance` table is initialized if missing.

## Reset Database
To reset all data:
1. Delete `student.db`
2. Restart the app

A new database file and table will be created automatically.
