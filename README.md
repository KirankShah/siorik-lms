# Bank LMS Monorepo

Monorepo for the Learning Management System MVP.

- **Backend:** Django 5 + Django REST Framework + PostgreSQL (`/backend`)
- **Frontend:** React + Vite + TypeScript + Tailwind CSS (`/frontend`)

This is a native local setup — no Docker. You need Python 3.11+, Node.js 20+,
and a running local PostgreSQL server installed on your machine.

## 1. Backend setup

Open a terminal in the project root.

```powershell
cd backend

# Create the virtual environment (already created if you cloned this repo as-is,
# but this is the command to recreate it from scratch)
python -m venv venv

# Activate the virtual environment
venv\Scripts\Activate.ps1
# (cmd.exe users: venv\Scripts\activate.bat)
# (macOS/Linux users: source venv/bin/activate)

# Install backend dependencies
pip install -r requirements.txt

# Copy the example env file and fill in real values
copy .env.example .env
```

Edit `backend/.env` and set your local PostgreSQL credentials (`DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`), a `SECRET_KEY`, and `DEBUG`.

## 2. Frontend setup

Open a **second** terminal in the project root.

```powershell
cd frontend

# Install frontend dependencies
npm install

# Copy the example env file and fill in real values
copy .env.example .env
```

Edit `frontend/.env` and set `VITE_API_BASE_URL` to point at the backend
(defaults to `http://localhost:8000/api`).

## 3. Running both dev servers side by side

Use two terminals so both servers run concurrently.

**Terminal 1 — backend** (from `/backend`, with the venv activated):

```powershell
venv\Scripts\Activate.ps1
python manage.py runserver
```

Backend will be available at `http://localhost:8000`.

**Terminal 2 — frontend** (from `/frontend`):

```powershell
npm run dev
```

Frontend will be available at `http://localhost:5173`.

Keep both terminals open while developing — the frontend dev server proxies
API calls to the backend via `VITE_API_BASE_URL`.

## Project structure

```
.
├── backend/          # Django + DRF project (venv, requirements.txt, .env.example)
└── frontend/         # Vite + React + TypeScript project (Tailwind CSS, .env.example)
```
