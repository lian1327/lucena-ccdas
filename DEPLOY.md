# CCADSS deployment guide (free tier, research-prototype mode)

What you end up with, at ₱0 a month and without a credit card:

```
 Citizen / staff browser
        │
        ├──► Cloudflare Pages   frontend (React build)          https://ccadss.pages.dev
        │
        └──► Render (free)      Django API + Gunicorn            https://ccadss-api.onrender.com
                 ├──► Neon (free)            PostgreSQL 1 GB, Singapore
                 └──► Backblaze B2 (free)    private bucket: photos + trained models (10 GB)
 GitHub Actions (free)  every 30 min → POST /api/v1/internal/cron/  (SMS queue, reminders, escalation)
```

Limits to expect on free plans:

| Service | Limit | What it means for you |
|---|---|---|
| Render | sleeps after 15 min idle, ~1 min to wake, 512 MB RAM, disk wiped on restart | The 30-min job keeps it awake most of the day. Never store files on Render's disk. Retrain the AI on your own PC. No shell on the free plan, so admin commands are run from your PC against Neon. |
| Neon | 1 GB storage, 100 compute-hours/month, sleeps after 5 min | Check the size of your data before loading it (step 2). |
| Backblaze B2 | first 10 GB free | Plenty for photos. Bucket stays private. |
| Cloudflare Pages | free static hosting | Instant, never sleeps. |

Plans change; check each provider's pricing page before the pilot.

---

## 0. Before you start

- Run the system in **prototype mode** (`SITE_MODE=prototype`, the default). It removes the GOVPH bar and seal, shows a banner
  that reports do not reach City Hall, and uses the college as data controller in the privacy notice. Switch to `official`
  only with the City's written authorization (section 9).
- Get your research ethics clearance if you will collect responses from the public.
- Everything below uses PowerShell on your PC, from the project root `Research2-CMS\`.

## 1. Prepare the repository

1. Copy the kit files over the project (see `STEP16-INSTALL.txt` for the list).
2. Add the lines in `backend/requirements-deploy.txt` to `backend/requirements.txt`, then:
   ```powershell
   cd backend
   pip install -r requirements.txt
   python manage.py check
   python manage.py test tests
   ```
3. **Migrations must be committed.** Render runs `migrate` from what is in Git:
   ```powershell
   python manage.py makemigrations --check   # must say "No changes detected"
   ```
4. Make sure secrets are ignored (the kit's `.gitignore` covers `.env`, `venv/`, `media/`, `ml/models/`,
   `CCADSS-demo-accounts.txt`). Then push to GitHub (a **private** repo is fine):
   ```powershell
   cd ..
   git status            # .env, venv and the demo-accounts file must NOT be listed
   git add .
   git commit -m "Step 16: deployment kit"
   git push
   ```

## 2. Database: Neon

1. Sign up at neon.com (GitHub login works). **Create project** → name `ccadss`, region
   **AWS Asia Pacific (Singapore)**, Postgres version = the same major version as your PC (`psql --version`).
2. **Connect** → turn **off** "Connection pooling" → copy the connection string. It looks like
   `postgresql://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`. This is your `DATABASE_URL`.
3. Check your local data fits in 1 GB:
   ```powershell
   psql -U postgres -d ccadss -c "SELECT pg_size_pretty(pg_database_size('ccadss'));"
   ```
   If it's over ~800 MB, regenerate smaller sample data first (fewer months in `generate_synthetic_data`).
4. Copy your local database (schema, migrations, sample data, users) to Neon:
   ```powershell
   pg_dump -U postgres -d ccadss -Fc --no-owner --no-privileges -f ccadss.dump
   pg_restore --no-owner --no-privileges --clean --if-exists -d "PASTE_DATABASE_URL" ccadss.dump
   ```
   Warnings about the `public` schema are normal. This also brings the barangay outlines and puroks.
   Delete `ccadss.dump` afterwards (it holds personal data).

## 3. File storage: Backblaze B2

1. Sign up at backblaze.com → **B2 Cloud Storage**.
2. **Buckets → Create a bucket**: name `ccadss-media-<something-unique>`, **Files in bucket: Private**, encryption on.
   Note the **Endpoint**, e.g. `s3.us-west-004.backblazeb2.com`. The region is the middle part, `us-west-004`.
3. **Application Keys → Add a New Application Key**: allow access to that bucket only, Read and Write.
   Copy the **keyID** and **applicationKey** now (the key is shown once).
4. Upload your local photos and trained models. In PowerShell, set the variables for this window only:
   ```powershell
   cd backend
   $env:MEDIA_S3_BUCKET="ccadss-media-xxxx"
   $env:MEDIA_S3_ENDPOINT="https://s3.us-west-004.backblazeb2.com"
   $env:MEDIA_S3_REGION="us-west-004"
   $env:MEDIA_S3_ACCESS_KEY_ID="keyID"
   $env:MEDIA_S3_SECRET_ACCESS_KEY="applicationKey"
   $env:AWS_REQUEST_CHECKSUM_CALCULATION="when_required"
   $env:AWS_RESPONSE_CHECKSUM_VALIDATION="when_required"
   python manage.py upload_media --dry-run
   python manage.py upload_media
   python manage.py sync_models --push
   ```
   Close this PowerShell window when done, so your local server keeps using `backend\media\`.

Cloudflare R2 works the same way (endpoint `https://<account_id>.r2.cloudflarestorage.com`, region `auto`), but Cloudflare
asks for a payment method to turn R2 on.

## 4. Accounts on the server (from your PC)

Render's free plan has no shell, so run these on your PC against Neon:

```powershell
cd backend
$env:DATABASE_URL="PASTE_DATABASE_URL"
python manage.py createsuperuser
python manage.py demo_users --rotate      # new random passwords, printed once: save them in a password manager
python manage.py demo_users --list        # every account must say "ok", none "PUBLISHED PASSWORD"
```

The published demo password must never work on a server reachable from the internet. Give panelists and testers the new
passwords privately.

## 5. API: Render

1. Sign up at render.com with GitHub. **New → Blueprint** → pick your repo. Render reads `render.yaml`.
2. Fill in the values it asks for:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the Neon string from step 2 |
   | `MEDIA_S3_*` | the five B2 values from step 3 |
   | `ADMIN_URL` | something unguessable ending in `/`, e.g. `ccadss-admin-7f3k/` |
   | `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `PUBLIC_SITE_URL` | put `https://ccadss.pages.dev` for now; fix after step 6 |

   `SECRET_KEY` and `CRON_TOKEN` are generated for you.
3. **Apply**. The first build takes 3–6 minutes. Then open
   `https://<your-service>.onrender.com/api/v1/health/` → `{"ok": true}`, and
   `/api/v1/public/site/` → `"mode": "prototype"`.
4. Admin: `https://<your-service>.onrender.com/<ADMIN_URL>` with the superuser from step 4.

## 6. Frontend: Cloudflare Pages

1. dash.cloudflare.com → **Workers & Pages → Create**. Choose the **Pages** option ("Import an existing Git repository"),
   not a Worker, and connect your repo.
2. Build settings: framework **None** (or Vite), root directory `frontend`, build command `npm run build`,
   output directory `dist`.
3. Environment variables (Production):
   ```
   NODE_VERSION=22
   VITE_API_URL=https://<your-service>.onrender.com/api/v1
   VITE_SITE_MODE=prototype
   VITE_ORG_NAME=Dalubhasaan ng Lungsod ng Lucena
   VITE_LGU_NAME=City Government of Lucena
   ```
4. **Save and Deploy**. Note the address, e.g. `https://ccadss.pages.dev`.
5. Back in Render → Environment: set `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `PUBLIC_SITE_URL` to that exact
   address (no trailing slash). Render redeploys.
6. `frontend/public/_redirects` makes deep links (`/track/...`, `/staff/...`) work; `_headers` adds security headers.

## 7. Scheduled jobs: GitHub Actions

1. Render → your service → Environment → copy `CRON_TOKEN`.
2. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:
   `API_URL` = `https://<your-service>.onrender.com`, `CRON_TOKEN` = the value you copied.
3. **Actions → ccadss-cron → Run workflow**. The log should end with JSON like `{"escalated":0,"sent":0,...}`.

It then runs every 30 minutes. On a private repo this uses about 1,500 of the 2,000 free Actions minutes a month.
On a public repo, GitHub pauses scheduled workflows after 60 days without commits.

## 8. Go-live checklist

- [ ] `DEBUG=False`, `SITE_MODE=prototype`, prototype banner visible on the landing page
- [ ] `demo_users --list` shows no "PUBLISHED PASSWORD"
- [ ] Admin only at your `ADMIN_URL`; `/admin/` returns 404
- [ ] `/api/docs/` asks for a login (API docs are not public in production)
- [ ] `SMS_PROVIDER=console` and `NOTIFY_EMAIL=0` unless you have budget and consent wording for real messages
- [ ] Privacy notice shows the college as controller; contact email set (`CONTACT_EMAIL` on Render)
- [ ] Submit a test report on your phone (with photo and pin), track it, open it in the staff portal
- [ ] No `.env`, dump file or demo-accounts file in the GitHub repo

## 9. Later: official City pilot

Only with a signed MOA or written authorization from the City:

1. Render: `SITE_MODE=official`, `ORG_NAME=City Government of Lucena`, `SMS_SIGNATURE=LGU Lucena`, `PUBLIC_SAMPLE_DATA=False`.
2. Cloudflare Pages: `VITE_SITE_MODE=official`, then redeploy.
3. Add the official seals to `frontend/public/` (`seal.png`, `govph-seal.png`) with the City's permission.
4. Delete the demo accounts (`demo_users --delete`) and the sample data
   (`generate_synthetic_data --purge`), create real staff accounts in the admin.
5. Real SMS: Semaphore account and sender name, then `SMS_PROVIDER=semaphore`, `SEMAPHORE_API_KEY`, `NOTIFY_SEND_INLINE=0`.
6. Update the privacy notice with the City's DPO, and sign data processing agreements with each provider.

## 10. Backups

Neon's free plan only keeps a 6-hour restore window. Once a week:

```powershell
pg_dump "PASTE_DATABASE_URL" -Fc --no-owner -f "backup-$(Get-Date -Format yyyyMMdd).dump"
```

Keep the dumps on an encrypted drive. Photos stay in B2; download the bucket from the B2 web page if you need a copy.

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Site loads but "Network Error" everywhere | `VITE_API_URL` wrong, or the API is waking up (wait 1 min). Check `/api/v1/health/`. |
| CORS error in the browser console | `CORS_ALLOWED_ORIGINS` must exactly match the Pages address, `https://`, no trailing slash. |
| Login works locally, 400/403 online | `CSRF_TRUSTED_ORIGINS` / `ALLOWED_HOSTS` mismatch. Render adds its own hostname automatically. |
| Photos broken | `MEDIA_S3_*` wrong or `upload_media` not run. Signed links expire after 1 h: reload the page. |
| "AI suggestion" never appears | Model file not in storage: run `sync_models --push` from your PC. |
| Build fails on `migrate` | Uncommitted migrations, or `DATABASE_URL` uses the pooled host. Use the direct one. |
| Build fails with `$'\r': command not found` | `build.sh` saved with Windows line endings. The kit's `.gitattributes` fixes it; re-commit the file. |
| Render "out of memory" | Don't train the classifier on Render. Train locally, `sync_models --push`, then activate. |
| Cron job shows 403 | `CRON_TOKEN` secret in GitHub differs from Render's. |
