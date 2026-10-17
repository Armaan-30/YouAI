const { defineConfig } = require("@playwright/test");
const path = require("path");
module.exports = defineConfig({
  testDir: "./tests/browser",
  timeout: 20000,
  workers: 1,
  use: {baseURL:"http://127.0.0.1:8766", headless:true, reducedMotion:"reduce"},
  webServer: {
    command: ".venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8766",
    url: "http://127.0.0.1:8766/",
    reuseExistingServer: false,
    env: {YOUAI_DATA_DIR:path.resolve(".runtime/browser-tests"), YOUAI_PRELOAD:"0"},
  }
});
