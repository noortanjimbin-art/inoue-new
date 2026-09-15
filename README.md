# INOUEE — Video Annotation Platform

Annotators mark the start and end of each work action in a video and caption it.
Admins upload videos, assign tasks, and track coverage.

## Stack

| Concern | Choice |
|---|---|
| Hosting + API | Vercel (`api/*.js` serverless functions, static `public/`) |
| Auth | **Supabase Auth** (email + password) |
| Data | Supabase Postgres — `inoue_new` schema (`supabase-schema.sql`) |
| Video files | Cloudflare R2 — bucket `inoue-new-videos`, via the S3 API |

This mirrors the INOUE Tool stack (Next.js + Supabase + R2) rather than
introducing a new one.

## Why Supabase Auth

The single-file version had no password check at all — sign-in only verified the
email existed, so any string worked, and registration was open to anyone with the
link (`docs/HANDOFF.md` §7). Supabase Auth replaces that with real credentials,
hashed server-side, plus email confirmation if you enable it.

The split that matters: **Supabase Auth decides who gets in, the `users` table
decides what they can do.** Roles stay `admin` / `annotator`. The first account to
register becomes admin (`first_user_is_admin` trigger); everyone after is an
annotator until an admin promotes them, and nobody can change their own role, so
the team cannot be locked out.

API routes use the **service-role key server-side only** and enforce the rules
themselves. RLS is enabled with no public policies, so the anon key alone reaches
nothing.

> If you later want to drop passwords entirely, Cloudflare Access in front of a
> Workers deployment does that — but it is Workers-only and does not apply to a
> Vercel deployment.

## Why the video path looks the way it does

Vercel caps both request and response bodies at **4.5 MB**, so a 500 MB video can
never pass through a function. Instead:

- **Upload** — `POST /api/upload` returns a presigned PUT; the browser uploads
  straight to R2.
- **Playback** — `GET /api/stream?key=…&json=1` returns a presigned GET; the
  browser makes its own Range requests to R2, so seeking works.

This removes the 20 MB ceiling from `docs/HANDOFF.md` §9. The cost is that R2
needs a CORS policy, because the upload PUT comes from the browser.

## Setup

### 1. Supabase — already done

The schema is applied. It lives in an isolated **`inoue_new`** schema inside the
existing `inoe-annotation` project (`svenzdtasbmhogowknws`), because that
project's `public` schema already holds unrelated videos/clips/annotations
tables that would otherwise collide.

One dashboard step remains: **Settings → API → Exposed schemas**, add
`inoue_new`. PostgREST will not serve the schema until it is listed there.

Then collect the `service_role` key from **Settings → API**.

### 2. Cloudflare R2

The bucket `inoue-new-videos` already exists. You need two things:

**An S3 API token** — R2 → Manage API Tokens → Create, with Object Read & Write
on that bucket. Note the Access Key ID and Secret Access Key.

**A CORS policy** on the bucket, or browser uploads will fail:

```json
[
  {
    "AllowedOrigins": ["https://*.vercel.app"],
    "AllowedMethods": ["PUT", "GET", "HEAD"],
    "AllowedHeaders": ["content-type"],
    "ExposeHeaders": ["etag"],
    "MaxAgeSeconds": 3600
  }
]
```

The wildcard covers preview deployments as well as production. It is not a
security boundary on its own: an upload still requires a presigned URL, which
`/api/upload` only issues to a signed-in admin. Narrow it to the exact domain
once one is settled.

### 3. Vercel environment variables

Settings → Environment Variables:

| Variable | From |
|---|---|
| `SUPABASE_URL` | Supabase → Settings → API |
| `SUPABASE_ANON_KEY` | same |
| `SUPABASE_SERVICE_ROLE_KEY` | same — **secret** |
| `R2_ACCOUNT_ID` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | R2 API token |
| `R2_SECRET_ACCESS_KEY` | R2 API token — **secret** |
| `R2_BUCKET` | `inoue-new-videos` |

Redeploy after adding them. Until they are all set the app shows a "Setup
required" screen listing what is missing, rather than failing obscurely.

## Layout

```
public/index.html      the annotation tool (single file, no build step)
api/_lib.js            auth check, Supabase service client, R2 client
api/config.js          public bootstrap: Supabase URL + anon key, readiness
api/me.js              current user, created on first sign-in
api/users.js           list, promote/demote, delete
api/videos.js          list, create, delete (also removes the R2 object)
api/tasks.js           list (scoped by role), create, patch, delete
api/anns.js            read and whole-list replace for one task
api/upload.js          presigned PUT to R2
api/stream.js          presigned GET from R2
supabase-schema.sql    tables, RLS, first-admin trigger
docs/HANDOFF.md        history, keyboard shortcuts, layout rules
```

## Known gaps

- **Polling, not realtime.** `pull()` refreshes every 5s and fetches annotations
  per task (N+1). Fine for a small team; swap to Supabase Realtime if it grows.
- **Admins cannot pre-create annotator accounts.** Supabase owns identity, so
  annotators self-register and an admin promotes them. The Team tab's add-member
  control no longer persists.
- **Not yet exercised end to end** against a live Supabase project or R2 token.
