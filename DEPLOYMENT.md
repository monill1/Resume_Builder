# Deployment Guide

This app has three production pieces:

- React/Vite frontend in `frontend`
- FastAPI backend in `backend`
- PostgreSQL database

The recommended setup is Vercel for the frontend and Render for the backend plus PostgreSQL.

## 1. Push The Repo To GitHub

Commit and push the project to a GitHub repository. Both Vercel and Render can deploy directly from GitHub.

## 2. Deploy Backend And Database On Render

Use the root-level `render.yaml` blueprint.

1. Open Render and create a new Blueprint from this repository.
2. Render will create:
   - `ats-resume-builder-api`
   - `ats-resume-builder-db`
3. Make sure both resources use the **Free** plan.
4. Wait for the backend deploy to finish.
5. Open the backend URL and verify:

```txt
https://your-api.onrender.com/api/health
```

Expected response:

```json
{"status":"ok"}
```

The backend service uses:

```txt
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /api/health
Python Version: 3.12.8
```

Render injects `DATABASE_URL` from the managed PostgreSQL database.

Note: Render's free PostgreSQL databases are good for first-time testing, but they expire after 30 days. For a longer-lived free database, use Supabase Free Postgres and set Render's `DATABASE_URL` to the Supabase connection string instead.

## 3. Deploy Frontend On Vercel

Create a Vercel project from the same GitHub repo.

Use these project settings:

```txt
Root Directory: frontend
Framework Preset: Vite
Install Command: npm ci
Build Command: npm run build
Output Directory: dist
```

Add this Vercel environment variable:

```txt
VITE_API_BASE_URL=https://your-api.onrender.com
```

The repo also includes `frontend/.env.production` with the current Render backend URL so Vercel production builds have the API URL even if the dashboard variable is missed.

Deploy the frontend.

## 4. Update Backend CORS

After Vercel gives you a frontend URL, update the Render backend environment variable:

```txt
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
```

Redeploy the backend after changing it.

If you add a custom domain later, include both origins separated by commas:

```txt
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app,https://yourdomain.com
```

## 5. Configure Email And Razorpay

Add these backend environment variables in Render:

```txt
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_gmail_app_password
SMTP_FROM=ResuME <your_email@gmail.com>
RAZORPAY_KEY_ID=rzp_live_your_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
ADMIN_BYPASS_EMAILS=panchalmonil44@gamil.com,panchalmonil44@gmail.com
```

`ADMIN_BYPASS_EMAILS` is a comma-separated list of account emails that can download PDFs without payment.

## 6. Test Public Usage

Open the Vercel URL in a normal browser window and test:

- Sign up
- Log in
- Reset password
- Buy a PDF download or monthly pack
- Save a resume
- Generate a PDF
- Run ATS analyze/optimize

If the frontend says it cannot reach the backend, check:

- `VITE_API_BASE_URL` on Vercel points to the Render backend URL
- `ALLOWED_ORIGINS` on Render exactly matches the Vercel frontend URL
- `/api/health` works on the backend URL
