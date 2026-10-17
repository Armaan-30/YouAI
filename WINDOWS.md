# YouAI on Windows

The local backend supports both a browser interface and the Windows desktop client. See [desktop installation, new features and limits](DESKTOP.md). Android work is paused.

## Start

Run these commands in PowerShell from this folder:

```powershell
.\setup.ps1 # First install only; downloads model assets
.\start.ps1
```

If script execution is restricted, run `powershell -ExecutionPolicy Bypass -File .\start.ps1` for this script only. Open http://127.0.0.1:8765 in Edge or Chrome. Allow microphone access when prompted. Ollama must be installed from https://ollama.com/download/windows before setup can finish.

To stop the app server, run `.\stop.ps1`. Ollama has its own tray application and lifecycle.

## Try it

- Tap the circle, speak, then pause or tap again to submit.
- Type a message as an alternative. Typed and spoken turns share conversation history.
- Tap while thinking or speaking to interrupt.
- Say or type “Save a note: my next idea is a voice journal.” The note is actually saved locally.
- Enable “Listen for Hey You”, then say “Hey You, show my notes.” A continuous local Vosk recognizer handles activation, and Whisper transcribes the command. The microphone stays open between activation and your request, with 1.6 seconds of buffered audio to preserve the start of the command. This is a lightweight phrase recognizer, not a custom-trained wake-word neural model; accuracy with your voice and background noise still needs testing.
- Ask “Show my notes” or “Find notes about groceries” to retrieve saved notes.
- Say “Remind me in 10 minutes to drink water”, “Remind me tomorrow at 9 AM to call Sam”, or “Set a timer for 5 minutes”.
- Ask “Show my reminders” or “Cancel reminder 3”. In Conversation, enable desktop notifications if desired.
- Open Conversation to see history, notes, clear the conversation, or disable spoken replies.

In the browser, microphone listening stops when the page is hidden; the desktop client has a separate opt-in tray listening setting. Wake mode resumes on return if still enabled. If the browser cannot provide a local installed speech voice, the app shows the text answer and explains that speech playback is unavailable.

Reminders are saved across restarts. Keep the page open and laptop awake for timely alerts: these are in-app reminders, not Windows Task Scheduler jobs. Overdue reminders remain visible until marked Done, including after reopening the app. Hidden-tab throttling or sleep can delay notifications. Times default to Asia/Kolkata; bare “9” requires AM/PM rather than guessing.

## Implementation

Spoken replies prefer the installed Microsoft Zira female voice, with Heera as a fallback. Playback uses a slightly slower pace (0.9), natural pitch (1.0) and softer volume (0.9). Other local voices are used only if neither preferred voice is available.

Browser audio → local faster-whisper (Whisper base, CPU int8) → normalized text → FastAPI orchestration + SQLite context → Ollama Qwen 2.5 3B → displayed text + local Windows browser speech synthesis.

faster-whisper implements Whisper with CTranslate2; it replaces the suggested whisper.cpp runtime for this Windows prototype without changing the architecture. Ollama hosts the local model and isolates inference from the UI. CPU transcription leaves limited GPU VRAM available for the LLM. The active inference target is this Windows laptop.

- `app/speech.py`: local speech adapter; normal app use forbids automatic model downloads.
- `app/main.py`: API, context assembly, model adapter and cancellation. Desktop mode uses loopback; optional legacy phone mode adds authenticated TLS.
- `app/wake.py`: per-session continuous Vosk phrase recognition; only local, same-origin WebSocket connections are accepted.
- `app/tasks.py`: deterministic note/reminder/timer commands, validation and timezone handling.
- `app/storage.py`: local conversation and notes persistence.
- `web/`: one-button UI, browser audio capture, silence detection, state machine and opt-in wake preview.

Tasks include saving/listing/searching notes and creating/listing/cancelling reminders and timers. Action receipts are committed atomically and keyed by request ID to prevent duplicate writes on retry. Unsupported or ambiguous reminder syntax asks for clarification instead of guessing. Document import and local RAG are available in Conversation; see [document features and limits](DESKTOP.md). Arbitrary app control, messages and calendar integration remain future work. There is no shell execution or general tool access.

Replies stream as text arrives, and complete sentences can be spoken before the full reply is finished. Cancellation stops pending speech and model work; partial failed replies are not stored as completed turns. Whisper and the wake model preload at server startup, and Ollama keeps the model warm for 30 minutes after use. This consumes some idle RAM/VRAM in exchange for lower startup latency; set `YOUAI_PRELOAD=0` to disable startup preloading.

## Data and model locations

Conversations, notes and Whisper assets default to `%LOCALAPPDATA%\YouAI`, outside this repository's OneDrive folder. Ollama manages its models separately. Application logs are under `.runtime`; they contain request paths/status, not prompt content. Audio is processed in memory and is not saved by the app. Conversation clearing does not remove saved notes.

First setup requires internet downloads. The chat and transcription adapters connect only to local inference; TTS selects local voices only. The user confirmed wake, voice playback and spoken interruption on the development laptop. Broader hardware/noise, background wake and system-wide airplane-mode testing remain. No cloud fallback is implemented.

Set `YOUAI_MODEL` before launch to select another installed Ollama model, `YOUAI_WHISPER_MODEL` before setup/launch for another Whisper size, `YOUAI_TIMEZONE` for another IANA time zone, or `YOUAI_DATA_DIR` to override storage.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
npm install
npx playwright install chromium
npm test
```

The browser tests use a separate test server and temporary data. Python tests exercise note persistence, conversation context, model failure, cancellation, input validation and cross-site access rejection. Browser tests use mocked inference and test UI interaction; they do not establish actual microphone or speaker quality.
