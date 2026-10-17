# Android with a laptop-hosted AI

The phone captures audio and displays the circular assistant UI. The laptop runs Vosk wake recognition, Whisper transcription, Qwen through Ollama, document retrieval and SQLite storage. Replies stream back to the phone and its installed Android speech engine speaks them. No LLM is installed on the phone.

## Run and pair

1. Run `./setup.ps1` if this is a new laptop installation. Ollama needs `qwen2.5:3b` and `nomic-embed-text` downloaded.
2. Run `./start-phone.ps1`. Keep the laptop awake and connect both devices to the same private Wi-Fi network.
3. Run `./build-android.ps1`. The first build downloads JDK 17, Android SDK 35 and Gradle into `%LOCALAPPDATA%/YouAI/devtools`.
4. Transfer `android/app/build/outputs/apk/debug/app-debug.apk` to the phone and install it. Android may ask you to allow installation from that transfer app.
5. Open `http://127.0.0.1:8765` on the laptop. In Conversation, choose Pair Android phone. Scan the QR with the phone's camera, or paste the private pairing link into YouAI. Confirm the laptop address.
6. Allow microphone permission. Tap the circle, or enable Hey You while the app is open. Use Connection / Voice to preview installed English voices and choose the one you prefer.

Windows Firewall must allow inbound TCP 8768 on the private network. If connection fails, run `./enable-phone-firewall.ps1` once in an Administrator PowerShell and check Wi-Fi client isolation. The rule permits only the local subnet on a Private network. Do not expose Ollama's port or forward router ports. This version supports home-LAN access; access away from home needs a separately configured private network.

The APK embeds only the laptop's public certificate authority. TLS verifies the server normally; certificate errors are never bypassed. Pairing also supplies a secret token stored in private Android preferences. Do not share pairing links. The token and private certificate keys remain under `%LOCALAPPDATA%/YouAI/mobile`. To revoke all paired phones, stop the server, remove just `pairing.json` from that directory, restart, and pair again. If the laptop's IP changes, restart the phone server and pair again. The same APK remains usable as long as the laptop CA remains unchanged.

## Document answers

Open Conversation, upload a PDF, TXT or Markdown file, then enable **Answer from my documents**. The laptop extracts text, splits it into overlapping passages, embeds them with `nomic-embed-text`, stores vectors in SQLite and uses bounded cosine search to supply relevant passages to Qwen. The UI shows the retrieved excerpts and PDF page numbers, including in saved history. These are retrieved sources, not a guarantee that every generated claim is correct.

Document mode is optional and normal conversation does not perform retrieval. Explicit notes/reminder commands still use the deterministic task handler. Retrieved document text is reference material and never executes tasks. Removing a document removes its search index; previously saved answers and excerpts remain until history is cleared.

Limits: 10 MB per file, 150 PDF pages, 300,000 text characters, 400 passages per document and 4,000 passages total. Scanned PDFs need OCR elsewhere; password-protected PDFs are rejected. If the embedding model changes, re-import documents. Upload trusted personal files.

## Current limits

- The laptop must be on and reachable. After downloads, the AI pipeline requires no cloud AI account or per-message API fee.
- Hey You works with the app visible. Screen-off/background listening and system-wide Android assistant integration are not implemented.
- Reminders are stored on the laptop and displayed while the app is connected; they are not Android OS alarms.
- Phone calls, messages, calendar, contacts and device automation are not integrated.
- Voice quality/gender depend on the installed Android TTS engine. Local voice selection and a slower speaking rate are provided; Windows Zira does not transfer to Android.
- This is a development APK, not a Play Store release. Physical microphone, wake reliability, file picker and voice playback need validation on your Android phone.
