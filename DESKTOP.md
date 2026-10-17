# YouAI desktop features — 0.4

Android development is paused. This release focuses on the existing Windows laptop installation.

## Install and start

Run `dist/YouAI Setup 0.4.1.exe` to install the desktop app for your Windows account. The installer now includes the Python backend source and web assets; it no longer needs a project checkout. On first launch, automatic setup reuses a supported Python/Ollama installation or downloads them, creates a private Python environment, installs dependencies, and downloads Whisper, Vosk, Qwen, embeddings and five OCR languages. Internet and several GB of disk space are required for first setup. A progress window and `runtime/setup.log` in Electron's user-data directory provide diagnostics. Closing setup cancels it; launching again retries. Models and personal data are retained separately when updating the app.

This is an unsigned development installer. Automated dependency setup is not an offline installer with all model weights embedded. Third-party licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The app starts the local backend and Ollama when needed. Close the window to leave it in the tray; choose Quit YouAI in the tray to exit. Ctrl+Alt+Space opens the window and starts listening. The tray menu can enable startup with Windows. Existing browser startup scripts still work.

## Memory

In Conversation, enter a fact and click **Approve and remember**. You can edit it or choose Forget. Saying or typing `Remember that I prefer tea` only fills a proposed memory; it is not saved until you approve it. Ordinary conversation never automatically creates personal memories.

Approved memories are supplied to the local model as bounded context. Up to 50 memories of 1,000 characters are stored; model context includes at most 5,000 characters of the newest memories. Forgetting removes that memory from future memory context, but past conversation text remains until you clear history. Search conversation searches saved messages, independently of memory.

## Documents

- Search document names and indexed text in the library. Check specific documents to restrict retrieval; none checked means all documents.
- Summarize processes every indexed passage in bounded groups, then combines section summaries in successive stages. Progress appears while reading; Stop cancels the work. Every original passage remains inspectable as a source. This covers all extracted/indexed text, but summaries still condense details and cannot recover missing OCR content. Long documents take longer.
- Scanned PDF pages support English, Hindi, Spanish, French and German. Choose the language before importing; English is included in mixed-language choices. Setup installs all five language files. Run `scripts/setup_ocr.ps1` to repair missing files. Auto-index uses English unless `YOUAI_OCR_LANGUAGES` is set (for example `eng+hin`). To change OCR for an already indexed file, remove and re-import it. OCR may misread names and numbers.
- Under Laptop actions, approve a folder, choose **Auto-index documents in folder**, preview, and confirm. It scans supported files every 60 seconds, up to 50 documents / 10,000 inspected filenames per folder. Links/junctions are excluded. Changed files create a new indexed version; old versions and documents whose source files were deleted remain until removed manually.
- Revoke the folder permission to stop future scans. Previously indexed documents remain. Index limits still apply: 10 MB/file, 150 PDF pages, 300,000 extracted characters, 400 chunks/document and 4,000 chunks total.

## Laptop actions

Approve an `.exe` or folder by full path, or use Browse in the desktop client. Applications open with no generated command arguments. File creation supports new `.txt`/`.md` files directly inside the approved folder; existing files are never overwritten. Filename search stays within the chosen folder, skips linked directories and returns at most 50 matches after examining at most 10,000 filenames.

Opening apps and creating files require a preview and a separate confirmation, valid for two minutes and usable once. No shell, delete, overwrite, arbitrary script execution, or model-generated tool calls are exposed. Saying `open notepad` can propose opening an already approved notepad executable; `find files named budget` searches the selected approved folder. File creation is configured in the action panel.

## Voice, wake and reminders

Choose a local installed voice and preview it. Windows desktop playback uses System.Speech; the browser version uses local Web Speech voices. Zira/Heera remain preferred defaults. Speaking speed, pause duration, wake sensitivity, and recognition language are configurable. Whisper supports automatic language detection plus explicit English, Hindi, Spanish, French and German selection; accuracy across these languages still requires real-user testing.

Spoken interruption is optional: say Hey You while a reply plays, then give your request. The microphone remains on during playback; headphones reduce self-triggering. The desktop client also offers an explicit **Keep Hey You listening when minimized to tray** option. It is off by default, not persisted across app restarts, and microphone activity is shown in the tray tooltip. Browser tabs stop listening when hidden.

Native reminder delivery runs in the desktop main process even with its window closed to tray. Acknowledgments are persisted so an already delivered reminder is not repeatedly notified after a restart. Overdue, undelivered reminders are checked after resume/restart. The app must remain running, Windows notifications must be allowed, and the laptop must be awake. Focus Assist can hide notifications. This does not wake a sleeping laptop or deliver alarms while powered off; Quit stops the notifier.

## Optional web search

Free DuckDuckGo search is the default; no account, payment or API key is required. This uses the unofficial DDGS integration with only the DuckDuckGo backend enabled. It may be rate limited or unavailable; errors are displayed rather than replaced with invented answers. Optional Brave support remains available by setting `YOUAI_SEARCH_PROVIDER=brave` and `YOUAI_BRAVE_KEY` in the backend environment. Restart after changing configuration.

**Search the web** is off by default and mutually exclusive with document mode. Only the current question goes to the configured search service; stored memories, history and documents are not sent. The local model answers using returned snippets, with source links. Snippets are not full pages and results may be incomplete. Internet is required only when using this option (or first-time downloads).

## Verification and remaining acceptance work

Automated checks cover memory approval/edit/delete, file permissions and confirmation, path escape and overwrite rejection, folder indexing, reminder acknowledgments, RAG, cancellation, voice handoff, spoken interruption and UI controls. A real scanned-PDF OCR test passed. A local pipeline smoke test completed Whisper, embeddings, retrieval and Qwen generation with outbound connections blocked in the Python process; this is not a system-wide airplane-mode certification.

Desktop smoke tests exercise the actual executable, preload bridge, shortcut registration, native voice discovery and close-to-tray behavior. The installer completed an automated installation, and the installed executable passed checks using its bundled backend and a separately provisioned runtime. Windows acknowledged a native reminder while hidden to tray. The user confirmed wake detection, voice playback, spoken interruption and visible reminders. Interactive wizard, background wake, clean-machine setup and sleep/resume acceptance remain. Free web search was tested live, including local-model answers with citations. Dependency setup was exercised in a separate environment on this laptop, reusing its existing Python/Ollama; a pristine Windows VM is still needed to validate the missing-runtime download branches. No claim is made that all accents, noise conditions, notification settings or languages are validated.

Build/check commands: `npm run package:windows`, `node scripts/smoke_desktop.cjs`, `.venv/Scripts/python -m unittest discover -s tests -q`, `npm test`, `.venv/Scripts/python scripts/measure_voice.py`, and `.venv/Scripts/python scripts/check_local_pipeline.py`.

See THIRD_PARTY_NOTICES.md before distributing binaries. PyMuPDF is installed during setup under its own AGPL/commercial terms; the repository MIT license does not replace those terms.

Detailed evidence and the remaining human checks are in [RELEASE_CHECKS.md](RELEASE_CHECKS.md).

## Optional Groq chat and transcription

Version 0.4.1 adds server-side Groq support for Qwen 3.8 27B and Whisper Large v3 Turbo. See the README configuration steps. The UI discloses online processing: chat context includes recent history, approved memories and supplied document passages; voice requests are uploaded for transcription. Wake detection, installed voices and embeddings remain local. API errors do not silently switch providers. A new checkout defaults to local processing.
