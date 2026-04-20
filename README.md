# ATS Resume Builder

React + FastAPI resume builder that lets users fill structured sections and download an ATS-friendly PDF in a style inspired by the Abhishek resume layout.

## Stack

- Frontend: React + Vite
- Backend: FastAPI
- Database: PostgreSQL
- PDF generation: ReportLab

## Run Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8005
```

Backend URL: `http://127.0.0.1:8005`

The backend reads `DATABASE_URL` from `backend/.env`. For a local PostgreSQL database, use:

```bash
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/Resume
```

On startup, the API creates these PostgreSQL tables automatically if they do not exist:

- `resume_drafts`
- `pdf_exports`
- `ats_analyses`
- `ats_optimizations`

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5174`

## Environment Variables

- Frontend: copy `frontend/.env.example` to `.env` and set `VITE_API_BASE_URL`
- Backend: set `ALLOWED_ORIGINS` to a comma-separated list of frontend URLs that should be allowed to call the API
- Backend: set `DATABASE_URL` to your PostgreSQL connection string

Example:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8005
ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/Resume
```

## API

- `GET /api/health`
- `GET /api/sample`
- `GET /api/resume/latest`
- `POST /api/resume/save`
- `DELETE /api/resume/saved`
- `POST /api/resume/generate`
- `POST /api/ats/analyze`
- `POST /api/ats/optimize`

## Make It Usable By Anyone

For production deployment, see [DEPLOYMENT.md](DEPLOYMENT.md).

You have two good options:

### 1. Share it on the same Wi-Fi or office network

Run the backend on all interfaces:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8005
```

Run the frontend so other devices can open it:

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5174
```

Then open it from another device with your computer's local IP:

- Frontend: `http://YOUR_LOCAL_IP:5174`
- Backend: `http://YOUR_LOCAL_IP:8005`

Set:

```bash
VITE_API_BASE_URL=http://YOUR_LOCAL_IP:8005
ALLOWED_ORIGINS=http://YOUR_LOCAL_IP:5174
```

### 2. Deploy it publicly

Recommended simple setup:

- Frontend on Vercel or Netlify
- Backend on Render or Railway

Deployment flow:

1. Deploy the FastAPI backend first.
2. Copy the public backend URL, for example `https://your-api.onrender.com`.
3. Deploy the frontend with `VITE_API_BASE_URL=https://your-api.onrender.com`.
4. Set backend `ALLOWED_ORIGINS` to your frontend URL, for example `https://your-app.vercel.app`.

Example production values:

```bash
VITE_API_BASE_URL=https://your-api.onrender.com
ALLOWED_ORIGINS=https://your-app.vercel.app
```

After that, anyone with the frontend link can use the app in their browser.
