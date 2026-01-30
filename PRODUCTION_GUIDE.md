# 🚀 Production Deployment Guide

This project has been refactored to be **Industry Ready**. 
Follow this guide to deploy and maintain the application secure and effectively.

## 1. Security First
*   **Secrets**: The `.env` file contains your API Keys. **NEVER** commit this file to GitHub/GitLab. We have added a `.gitignore` to prevent this automatically.
*   **Database**: The `student.db` is a local file. For true production (AWS/GCP), you should migrate to MySQL/PostgreSQL as noted in `sql.py`.

## 2. Running the Application
The app is split into two services:

### A. The Backend API (FastAPI)
This handles the "Brain" (AI) and "Memory" (Database).
```bash
# Terminal 1
uvicorn api:app --host 0.0.0.0 --port 8000
```
*   **Production Tip**: In production, use `gunicorn` with `uvicorn` workers for better performance.
    *   Command: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app`

### B. The Frontend (Streamlit)
This handles the "Face" (UI).
```bash
# Terminal 2
streamlit run app.py
```

## 3. Environment Variables
Ensure your `.env` file looks like this:
```ini
GEMINI_API_KEY="AIzaSy..."
```

## 4. Troubleshooting
*   **"Connection Refused"**: Ensure the Backend (Terminal 1) is actually running.
*   **"Database Locked"**: We use SQLite WAL mode implicitly via our connection checks, but if this persists under high load, it's time to switch to MySQL.

## 5. Updates & Maintenance
*   **Dependencies**: Always freeze your requirements: `pip freeze > requirements.txt`.
*   **Logs**: The API prints logs to stdout. Retrieve them from your container logs or terminal.
