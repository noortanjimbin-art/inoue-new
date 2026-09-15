# Video Annotation Platform — Handoff / Memory

Everything needed to continue this build in a different chat or from a different
account. Supersedes the earlier handoff file.

Current at the point where video storage was being moved off the 20 MB artifact
limit — see §9, which is the live open thread.

---

## 1. What this is

A single-file web app for video work-activity annotation, built for Anosupo AI.
Annotators watch a video, mark the start and end time of each work action, and
caption it. Admins upload videos, assign tasks, and track progress.

**Live artifact:** https://claude.ai/code/artifact/1b347a3e-ce5e-4c58-ac09-58ce64ea4faf
**Source file:** `annotation-platform-v2.html` — self-contained, no build step, no dependencies

Reference implementation this is modelled on: the INOUE Tool
(`inouelab-main-one.vercel.app`, Next.js + Supabase + Cloudflare R2). The admin shell
here was built from the same five-tab shape. Its `/admin` route redirects to a login
screen, so the tab *contents* were designed from the workflow rather than copied —
worth comparing against the real screens.

---

## 2. Continuing the work

1. Upload `annotation-platform-v2.html` to the new session, **or** use the Artifact
   tool's `read` action with the URL above to pull the published files into the container.
2. Edit the file directly.
3. Republish with the Artifact tool, passing the **same URL** so it updates in place
   rather than creating a second artifact.

**Publish call — capabilities must be restated every time.** A non-empty
`capabilities` object is a full-set declaration; anything omitted is revoked.

```
Artifact(
  action: "publish",
  file_path: "/mnt/user-data/outputs/annotation-platform-v2.html",
  url: "https://claude.ai/code/artifact/1b347a3e-ce5e-4c58-ac09-58ce64ea4faf",
  capabilities: {"db": {}, "assets": {}, "downloads": true},
  title: "動画アノテーションツール",
  favicon: "🎬"
)
```

Dropping `db` or `assets` wipes the shared-mode wiring. Publishing without `url`
creates a *second* artifact with an empty database, cutting the team off from all
accumulated tasks and annotations.

Two practical notes: the publish card needs the user's approval and sometimes isn't
granted, in which case `present_files` is the fallback; and the file is large, so
edits are done by string replacement and the script should be parse-checked before
every publish:

```bash
node -e "const h=require('fs').readFileSync('annotation-platform-v2.html','utf8');
new Function(h.match(/<script>([\s\S]*)<\/script>/)[1]); console.log('OK');"
```

---

## 3. Architecture

One HTML file, three screens toggled by CSS class, all state in one in-memory `DB`
object that the views render from.

```
#login    email + password form, sign in / create account
#app      top bar + nav + #view (the five admin tabs render into #view)
#work     the annotation workspace (video left 2/3, panel right 1/3)
```

Script layout, in order:

| Section | Contains |
|---|---|
| i18n | `STR.ja` / `STR.en` dictionaries, `t(key, vars)`, `applyLang()` |
| storage | `KEY`, `DB`, `load()`, `save()`, `seed()`, `resetAll()` |
| shared store | `CLOUD`, `DBC`, `ASSETS`, `ASSET_MAX`, `wUser/wVideo/wTask/wAnns`, `d*` deletes, `startCloud()`, `refresh()`, `ensureAdmin()` |
| file store | IndexedDB helpers (`idb/idbPut/idbGet/idbDel/idbKeys`), `ensureFile()`, `makeThumb()`, `fsize()` |
| helpers | `fmt()`, `dur()`, `clock()`, `ago()`, `tstats()`, `vstats()`, `ustats()`, `isMine()` |
| auth | sign in / sign up, `enter()`, `showLogin()` |
| language | `setLang()`, `applyLang()` |
| nav | `TABS`, `go()`, `render()` |
| views | `viewDash()`, `viewTeam()`, `viewVideos()`, `viewExport()`, `viewTasks()` |
| wire | `wire()` — rebinds all event handlers after every `render()` |
| upload | `upload()`, `shareFile()` |
| workspace | `openTask()`, `persist()`, `stamp()`, `commit()`, `renderRows()`, keydown handler |
| boot | capability connect, then `boot()` |

Views return HTML strings; `render()` writes them into `#view` then calls `wire()`.
**Any new interactive element needs its handler added in `wire()`** or it is dead
after the next re-render.

---

## 4. Data model

### Shared mode (published artifact, `db` capability)

| Path | Body |
|---|---|
| `users/<id>` | `{name, email, role}` — role is `"admin"` or `"annotator"` |
| `videos/<id>` | `{name, dur, size, added, thumb, assetId}` — `thumb` is a base64 JPEG data URL; `assetId` points at the shared video file |
| `tasks/<id>` | `{videoId, userId, status, created, updated}` — status is `todo` / `doing` / `done` |
| `anns/<taskId>` | `{items: [{start, end, caption, at}]}` — one doc per task, times in seconds |

Four `onSnapshot` subscriptions rebuild `DB.users` / `DB.videos` / `DB.tasks` /
`DB.anns` and call `refresh()` (debounced 120 ms). The `anns` snapshot deliberately
skips the currently open task so a live edit isn't clobbered by an echo of itself.

Writes are last-writer-wins with no transactions. One task is edited by one
annotator, so this is safe as designed; it would not be if two people edited the
same task simultaneously.

### Local fallback (unpublished preview, or `db` unavailable)

- `localStorage["anno_platform_v3"]` — the whole `DB` object as JSON
- `IndexedDB "anno_files"`, store `files` — video blobs keyed by video id
- `sessionStorage["anno_me"]` — signed-in user id
- `localStorage["anno_lang"]`, `localStorage["anno_taskview"]` — UI preferences

`CLOUD` decides which path runs. `save()` is a no-op in shared mode; the `w*` helpers
write to `db` instead. **If you add a mutation, add the matching `w*` / `d*` call or
it silently won't sync.**

### Video files (current state — this is what §9 changes)

- ≤ 20 MB → uploaded via `assets.upload()`, played from `"/_blob/" + assetId`, visible to everyone
- \> 20 MB → stays in the uploader's IndexedDB, badged この端末のみ; each annotator must load their own copy

`ensureFile(videoId, cb)` resolves in order: session cache → shared asset → local
IndexedDB → `null`.

---

## 5. Behaviour worth preserving

### Keyboard shortcuts (the core of the tool — the user designed these)

| Key | Action |
|---|---|
| `Space` | play / pause |
| `←` `→` | seek −3s / +3s |
| `Enter` | stamp current time and advance: start → end → caption → commit |
| `Delete` | clear the focused cell; on an empty caption, step back to the end cell |
| `Esc` | leave the caption field |

`#cStart` and `#cEnd` are focusable divs, not inputs, so Space and arrows still work
while they hold focus. `#cCap` is a real input where the playback shortcuts are
suspended so typing works. `which()` reports which cell has focus; the keydown
handler branches on it.

### Layout rules the user asked for explicitly

- Video 2/3 left, annotation panel 1/3 right, both scaling with the window
- Video box fixed at 16:9 (they first asked for 4:3, then changed to 16:9)
- Whole app fits the viewport; only the annotation list scrolls
- Input row (start / end / caption in one horizontal row) pinned bottom-right
- Saved annotations use the same start / end / caption column order, stacked above the input row
- The on-screen shortcut legend was removed to free space; `?` in the header shows it

### Metrics

`coverage` = annotated seconds ÷ video length. It is the backbone metric across
Dashboard, Videos, and task cards — status alone doesn't show whether a "doing" task
is 4% or 90% done.

**Open question, never answered:** video-level coverage averages across all tasks on
that video. Correct for redundant double annotation; wrong if one video is split by
time range between annotators. Confirm which model they use before trusting it.

### Other features present

- JA/EN toggle (🌐) on login and in the header; covers every screen, errors, dialogs, and `dur()` formatting. Choice persists.
- Tasks tab has thumbnail card view and list view; choice persists. Thumbnails captured via canvas at 10% into the video.
- Export tab filters by video / annotator / status, previews, and downloads JSON (grouped by video) or CSV (flat, timecode + raw seconds). Export routes through the `downloads` capability because a plain `<a download>` is inert in a published page.
- Getting-started panel on an empty dashboard; Tasks blocks creation with a pointer to the missing step.
- データを初期化 button at the bottom of the Videos panel clears videos/tasks/annotations but keeps members.

---

## 6. Fix history worth knowing

**Tasks invisible to the assigned annotator.** The same person existed as two
accounts (one added by the admin in Team, one self-registered); the task pointed at
one id and sign-in resolved to the other, because the email lookup took the *last*
match. Fixed four ways: sign-in takes the first match and breaks; `isMine()` matches
by id **or** email; Team rejects duplicate emails on add; and a 重複アカウントを統合
button in Team merges existing duplicates and repoints their tasks.

**Demo data removal.** The app originally seeded demo videos/tasks/annotations. The
user asked for a clean start, so `seed()` now creates only the admin account and the
storage key moved to `anno_platform_v3` to bypass stale local data.

**Self-registration.** Open signup, no approval. The role picker was removed from the
signup form — self-registered accounts are always `annotator`, and only an admin can
promote via the Team dropdown. Nobody can change their own role, so admins can't lock
the team out.

---

## 7. Known limitations

Deliberate consequences of a single HTML page with no server.

**No password check.** Sign-in only verifies the email exists. Anything stored to
compare against would be readable in the page source. The user has asked about the
password three times — the answer is that there isn't one, any string works.

**Open registration, no verification.** Anyone with the link can register under any
email they type, including one that isn't theirs.

**20 MB shared-video ceiling.** Hard limit of the `assets` capability. See §9.

**Organization-scoped.** Declaring `db` makes the artifact org-internal; viewers must
be signed in to the same organization.

**5,000 document cap** on the artifact database, and thumbnails are base64 inside
`videos` docs (~20–30 KB each), so a large library would need thumbnails moved to
`assets`.

---

## 8. Migration path (the real fix)

The user already runs the target stack on the INOUE Tool, so the swap is narrow:

- `users` / `videos` / `tasks` / `anns` → Supabase tables (replaces `db` calls in `w*` / `d*` / `startCloud`)
- video blobs → Cloudflare R2 (replaces `assets.upload` and the IndexedDB fallback; `ensureFile` fetches a signed URL)
- sign-in → Supabase auth (replaces the email-existence check)

Everything above those functions — annotation logic, shortcuts, layout, i18n,
metrics — is storage-agnostic and carries over unchanged.

---

## 9. OPEN THREAD — 500 MB video sharing

**This is where the conversation stopped. Pick up here.**

The user asked for 500 MB videos to be shared. That cannot be done inside the
artifact's `assets` capability (20 MB hard cap), so three options were presented:

1. Cloudflare R2 + signed URLs via a Worker (recommended; reuses the INOUE Tool stack)
2. Google Drive or S3 direct upload
3. Status quo — distribute files manually, each annotator loads their own copy

**The user chose option 2.** They have not yet said Google Drive *or* S3. This
comparison was given and three questions are outstanding:

- **Google Drive** — no new infrastructure, a Google Drive connector is available in-session, share links give playable URLs. Risk: large-file streaming in the browser can be unreliable.
- **S3** — better for streaming, but needs a bucket, CORS config, and IAM keys. Keys can't be hardcoded safely in a public HTML file, so it needs a signed-URL proxy (Lambda), making it the same amount of work as option 1.

The assessment given: S3 has little advantage over option 1, and Google Drive is the
fastest thing to get running.

**Unanswered questions blocking implementation:**

1. Which Google account / Drive should host the videos — the one connected in-session?
2. New folder for videos, or an existing one?
3. Do annotators have Google accounts on the same domain, and is "anyone with the link" sharing acceptable?

**Implementation shape once answered (Google Drive):**

- `upload()` → upload the file to Drive via the connector, set link sharing, store the file id on the video doc (a new `driveId` field alongside or replacing `assetId`)
- `ensureFile()` → gain a branch resolving `driveId` to a playable URL, placed before the IndexedDB fallback
- The 20 MB branch and `ASSET_MAX` can remain as a small-file fallback, or be retired
- Video docs stay in the artifact `db`; only the file bytes move

**CSP constraint — verify this first.** A published artifact can only load scripts
from cdnjs / jsdelivr / cdn.tailwindcss / code.jquery and cannot make arbitrary
cross-origin requests. A Drive URL used directly as a `<video src>` may be blocked.
**Confirm playback works end to end before building the rest of the flow.** If it's
blocked, option 1 (R2 with a permissive CORS policy) becomes the only workable path,
and that should be raised with the user immediately rather than worked around.

---

## 10. Working preferences observed

- Reply in English by default. The user switched the conversation to Japanese partway through by asking directly (`日本語で応答して`); follow the language they ask for. UI copy and client-facing Japanese stay Japanese either way.
- They iterate in small, specific UI increments. Make the requested change, then flag consequences and open questions — don't expand scope.
- They act on flagged trade-offs, so surfacing them is worth the sentence.
- Verify the script parses before every publish; the file is large and edited by string replacement.
