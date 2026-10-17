# Third-party components

YouAI's own source is provided under the repository's MIT license. Third-party
components and model weights retain their separate licenses; MIT does not
relicense them. Setup downloads these separately rather than bundling weights.

- Electron: MIT; Chromium and Node.js include additional notices shipped with Electron.
- Python: PSF license. https://docs.python.org/3/license.html
- Ollama: MIT. https://github.com/ollama/ollama/blob/main/LICENSE
- Qwen2.5-3B: Qwen Research license; review the model's use and distribution terms.
  https://huggingface.co/Qwen/Qwen2.5-3B/blob/main/LICENSE
- Nomic Embed Text: Apache-2.0. https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
- Whisper / faster-whisper: MIT. https://github.com/SYSTRAN/faster-whisper
- Vosk and the small English model: Apache-2.0. https://alphacephei.com/vosk/models
- Tesseract fast language data: Apache-2.0. https://github.com/tesseract-ocr/tessdata_fast
- DDGS: MIT (unofficial search integration; upstream service terms also apply).
  https://github.com/deedy5/ddgs
- PyMuPDF / MuPDF: AGPL-3.0 or commercial licensing.
  https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright
  Setup installs this dependency for local OCR. Before distributing a combined
  application or offering it as a service, resolve the applicable AGPL source
  obligations or obtain the appropriate commercial license. A source-code push
  does not establish that a distributed binary complies with those obligations.

Pinned direct Python dependencies are in requirements.txt; JavaScript dependency
versions and package metadata are in package-lock.json. This is a component
inventory, not a replacement for the complete licenses delivered by each package.
