# Version 0.5.0 hosted and Windows checks

## Hosted profile (18 October 2026)

- Python suite: 44 tests, including a subprocess integration check for invitation registration, authentication, secure cookies, CSRF rejection, concurrent user isolation, document retrieval with streamed answers, restart persistence and logout revocation.
- Browser suite: 18 checks, including hosted controls, server-storage disclosure and sign-in error recovery.
- Live Groq streaming through the authenticated cloud gateway completed and persisted a synthetic test conversation.
- Automated cloud checks use synthetic accounts and mocked Groq responses. The existing live Groq checks below are separate evidence.
- Docker is installed, but its Linux engine was unavailable on this laptop; a Linux container build has not yet been verified.
- No Render service has been created. Actual HTTPS deployment, persistent-disk restart, browser microphone/voice and OCR within the Linux container require acceptance after deployment.
- The Render blueprint is a paid small-group preview with a persistent disk, not a permanent free hosting promise.

## Prior Windows 0.4.1 evidence

## Verified on this laptop

- Python suite: 43 checks passed (memory, actions, document coverage, cancellation, OCR configuration, search privacy/errors, reminder persistence and existing voice/RAG behavior).
- Browser suite: 16 checks passed, covering voice handoff/interruption, permissions, OCR upload choice and summary progress.
- Live free DuckDuckGo search returned official Python sources; Qwen answered with source cards. Inline citations are model-generated and may vary.
- Real Qwen hierarchical summary retained facts from the beginning and end of the fixture.
- Image-only PDFs rendered and recognized in English, Hindi, Spanish, French and German.
- Five synthetic wake clips passed; this is not a real microphone accuracy benchmark.
- Local Whisper, embeddings, retrieval and generation passed with outbound Python sockets blocked.
- Automatic setup completed in a separate environment. A redirected Windows folder caused pip rename failures; resolving its physical path fixed installation.
- NSIS installer completed with exit code 0 in a test installation directory.
- Installed executable ran its bundled backend with the separate environment. Preload bridge, native Zira voice discovery, shortcut and tray behavior passed.
- Windows emitted the native notification show event while the window was hidden, and the delivery acknowledgment was persisted.
- Git excludes models, Python environments, generated installers, databases, pairing certificates and .env secrets.

Groq integration additionally passed live model availability, streamed chat persistence, synthetic audio transcription and synthetic document grounding checks. Mocked tests cover authorization, sanitized API failures, incomplete streams, reasoning exclusion, status caching and cancellation. Real microphone testing through the new Groq transcription path has not yet been confirmed by the user.

## Human acceptance (do not mark passed without observation)

- [x] User confirmed wake detection works. Extended distance/noise benchmarking remains optional.
- [x] User confirmed voice playback works and sounds right.
- [x] User confirmed spoken interruption works.
- [ ] In the desktop app, enable background listening, minimize to tray, and try the wake phrase.
- [x] User confirmed seeing the real Windows release-test reminder.
- [ ] Sleep across a reminder due time and confirm delivery after resume.
- [ ] Confirm the interactive installation wizard and a pristine Windows VM with Python/Ollama absent. The automated installer test reused installed runtimes; missing-runtime download/install branches are implemented but not validated on a clean machine.

The installer remains unsigned. No signing certificate was supplied. Hosted deployment files are now included; live Render acceptance remains pending. See THIRD_PARTY_NOTICES.md for dependency/model terms before distributing binaries.

## Hosted wake fix

Browser suite extended to 21 checks: same-utterance wake/command, separate wake/command, unrelated-speech rejection, automatic rearming, toggle-off cleanup, permission-denial recovery and unsupported-browser fallback use a mocked recognition service. Real microphone/browser-provider recognition accuracy is not covered by these mocks and requires user acceptance.
