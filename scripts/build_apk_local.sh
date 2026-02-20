#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JAVA_17="/root/.local/share/mise/installs/java/17.0.2"

if [[ -d "$JAVA_17" ]]; then
  export JAVA_HOME="$JAVA_17"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

cd "$ROOT_DIR"

echo "[build] Java: $(java -version 2>&1 | head -n 1)"
echo "[build] Running Gradle assembleDebug..."

if gradle :app:assembleDebug; then
  APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
  if [[ -f "$APK_PATH" ]]; then
    cp -f "$APK_PATH" dist/overlaytester-debug.apk
    echo "[ok] APK: $ROOT_DIR/dist/overlaytester-debug.apk"
  else
    echo "[error] Build completed but APK not found at $APK_PATH" >&2
    exit 2
  fi
else
  echo "[error] APK build failed. Check repository/network access to Gradle/Android dependencies." >&2
  exit 1
fi
