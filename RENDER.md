# Deploy the YouAI web preview on Render

The web profile runs independently of your laptop. It uses Groq for chat and transcription, browser/device voices for playback, and server-side keyword retrieval for document assistance. It does not install Ollama, Whisper weights, Vosk, Electron or Windows speech components.

## Cost and scope

`render.yaml` provisions a **paid** `0.5c-512mb` web service and a **1 GB persistent disk**. Review Render's displayed price before creating it. Groq usage is subject to your account limits. No resources are created merely by pushing this repository.

This is an invitation-only preview for a small group, capped at 100 accounts. It is not an unlimited public service. The owner can access server files; account isolation prevents users from reading each other's app data, but is not end-to-end encryption.

Supported: typed and click-to-talk conversation, streamed answers, click-to-interrupt, replay, available device voices, approved memory, notes, reminders while the page is open, document uploads, selected-document answers, summaries, OCR and optional web search.

Desktop-only: Hey You detection, spoken interruption, Windows tray/shortcuts, local application launch, local folder access and folder watching. The web interface disables these controls. Browser voices may use the device vendor's online speech service. Device voices vary; the Windows Zira voice is not guaranteed on phones. Notifications are not scheduled push messages when the browser is closed. Overdue reminders appear on return. Reminder interpretation currently uses Asia/Kolkata for all accounts.

## Setup

1. Push these changes to your GitHub repository.
2. In Render, choose **New → Blueprint**, connect the repository and use `render.yaml`.
3. Enter your own **GROQ_API_KEY** in Render's secret configuration. Do not put it in GitHub or frontend files. If a key was shared in chat, replace it before public use.
4. Review and approve the paid service and disk in Render. The Docker build installs the cloud dependencies and OCR language data. Startup uses `app.cloudapp:app` with exactly **one worker**. Do not change the entry point to `app.main:app` for hosting.
5. Render supplies `RENDER_EXTERNAL_URL`; YouAI uses it as the allowed origin. For a custom domain, set `YOUAI_PUBLIC_ORIGIN` to the exact HTTPS origin (no path). Only that origin is accepted.
6. Wait for `/healthz` to pass and open the generated HTTPS URL. This endpoint checks app startup, not Groq quota/availability; the signed-in status screen checks Groq.
7. Retrieve the generated **YOUAI_INVITE_CODE** privately from Render's Environment settings. Create your account using a username, a password of at least 12 characters and this invitation. Share the URL and invitation with your intended users, never the Groq API key. They create separate accounts. Rotate the invitation to stop new registrations using the old code; existing accounts remain valid.

Existing laptop accounts/data are not automatically uploaded. This deployment starts with empty private accounts.

## Storage and operating limits

- Persistent mount: `/var/data`; application data: `/var/data/youai`.
- `accounts.sqlite3` stores usernames, scrypt password hashes, hashed session tokens and daily usage counters. Passwords are not stored in plaintext. Session cookies are Secure, HttpOnly and SameSite=Strict; sessions expire after seven days. Sign-out revokes every session for the account.
- Each account has a separate SQLite file under `users/<random-id>/youai.sqlite3`. Conversation, notes, memories, reminders, extracted document passages and retrieval data live there. Original uploaded files are not retained.
- Document retrieval matches words; it is not semantic embedding search. No document embedding API or laptop connection is needed. Local desktop mode retains Nomic semantic embeddings.
- Hosted imports: 3 MB, 25 PDF pages and 50 passages per document; 4,000 indexed passages per account. PDF OCR runs on the server. One document import runs at a time. Large scanned PDFs can be slow on the smallest plan.
- At most 200 chat/transcription requests per account per UTC day, plus per-minute limits and an account data limit of approximately 5 MB. Quota failures are explicit. Provider quotas are shared by everyone using your Groq key. Summaries can make several Groq calls per request.
- Use one instance and one worker: cancellation, in-flight locks and per-minute limits are process-local. Multi-instance scaling requires a shared database and coordination redesign.
- No email verification, password recovery, administration UI or automated external backup is implemented. Use unique passwords and keep them in a password manager. Back up the full data directory using a consistent stopped-service copy or SQLite backup tooling, and test restoration. Do not delete the Render disk unless you intend to delete the accounts and data.

## Free temporary demo

Render free web services cannot attach this persistent disk. If you manually select free hosting without a disk, accounts and saved data can disappear on restart, redeploy or sleep. That is a disposable demo, not the supported persistent setup. Do not use Render's expiring free database as a permanent-storage promise. See [Render free limits](https://render.com/docs/free) and [persistent disk documentation](https://render.com/docs/disks).

## Validation before sharing

Create two accounts and confirm separate histories/documents. Try a typed question and a real microphone question, import a short document and ask about it, preview a device voice, interrupt a reply, and verify an overdue reminder. Restart the service and confirm data survives. Check narrow-screen layout, sign-out, and Groq quota errors. Only then share the URL with your group.

Local automated checks use synthetic accounts and a mock Groq service: `python scripts/check_cloud.py`, the Python suite and the browser suite. A live Render deployment and real mobile microphone/audio acceptance are separate checks; they have not been completed merely by running these tests.

## Container smoke test

With Docker running: `docker build -t youai-cloud .`. Run behind an HTTPS proxy, bind a persistent directory to `/var/data`, and provide `GROQ_API_KEY`, `YOUAI_PUBLIC_ORIGIN` and `YOUAI_INVITE_CODE` (at least 32 characters) as runtime secrets. Never bake them into the image. Render supplies HTTPS automatically. The local HTTP health endpoint can be checked without a browser session; login requires HTTPS for the secure cookie.
