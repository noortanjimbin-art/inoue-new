# INOUEE — Video Annotation Platform

Annotators mark the start and end of each work action in a video and caption it.
Admins upload videos, assign tasks, and track coverage.

## Stack

| Concern | Choice |
|---|---|
| Auth | **Cloudflare Access** (Zero Trust) — no passwords in this codebase |
| App + API | Cloudflare Workers (`worker/`), static tool served from `public/` |
| Data | Cloudflare D1 (`schema.sql`) |
| Video files | Cloudflare R2 — bucket `inouee-annotation-videos` |
| Deploy | GitHub → Cloudflare Workers Builds (push to `main` deploys) |

Everything except GitHub lives in one Cloudflare account: one bill, one dashboard,
one set of logs.

## Why Cloudflare Access for auth

The previous single-file version had no password check at all — sign-in only
verified the email existed, so any string worked, and registration was open to
anyone with the link (see `docs/HANDOFF.md` §7).

Access fixes all of that without adding auth code to maintain:

- Login happens **before** a request reaches the Worker. Google Workspace SSO, or
  one-time PIN to an email address on an allowlist.
- No password is ever stored, hashed, reset, or leaked here.
- Revoking an annotator is removing their email from one policy.
- Free for up to 50 users.

The Worker still verifies the signed `Cf-Access-Jwt-Assertion` header
(`worker/access.js`) rather than trusting it blindly — otherwise anything that
reached the Worker origin directly could forge an identity.

Access decides **who gets in**. The `users` table decides **what they can do**
once inside (`admin` vs `annotator`). The first person to sign in becomes admin;
everyone after is an annotator until an admin promotes them.

## Video files

Upload and playback both proxy through the Worker, so the browser only ever
talks to its own origin:

- **No R2 CORS policy to configure** and no presigned URLs that can leak.
- 500 MB uploads use R2 multipart (`/api/upload/create` → `part` → `complete`),
  which removes the 20 MB ceiling that was blocking the old version.
- `/api/stream/<key>` honours HTTP Range, so seeking in `<video>` works.

## Setup

Run once, from a machine with Node installed (this project's dev machine has
none — see "Deploying without Node" below).

```bash
npm install -g wrangler
wrangler login

wrangler d1 create inouee-annotation          # paste database_id into wrangler.toml
wrangler d1 execute inouee-annotation --remote --file=./schema.sql
wrangler deploy
```

Then in the Cloudflare dashboard, **Zero Trust → Access → Applications**:

1. Add a self-hosted application pointing at the deployed Worker's hostname.
2. Add a policy: Allow → Emails / Email domain → your annotators.
3. Copy the application's **AUD tag** into `ACCESS_AUD` in `wrangler.toml`, and
   your team name (the `<team>` in `<team>.cloudflareaccess.com`) into
   `ACCESS_TEAM`. Redeploy.

### Deploying without Node

Workers Builds compiles in Cloudflare's cloud, so no local toolchain is needed:
**Workers & Pages → the Worker → Settings → Build → Connect to Git**, pick this
repo, and every push to `main` deploys. The one-time `d1 create` above still
needs either Node or the dashboard's D1 console.

## Layout

```
public/index.html   the annotation tool (single file, no build step)
worker/index.js     API routes: users, videos, tasks, anns, upload, stream
worker/access.js    Access JWT verification and identity → users row
schema.sql          D1 tables
docs/HANDOFF.md     history, keyboard shortcuts, layout rules, known issues
```

`public/index.html` is still the artifact-era build and talks to the artifact
`db`/`assets` capabilities. Porting its `w*`/`d*` storage helpers to `fetch('/api/…')`
is the next step; the annotation logic, shortcuts, layout and i18n above that
layer are storage-agnostic and carry over unchanged (`docs/HANDOFF.md` §8).
