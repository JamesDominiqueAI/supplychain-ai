#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$ROOT_DIR/.lambda-build"
ZIP_PATH="$ROOT_DIR/api_lambda.zip"

rm -rf "$BUILD_DIR" "$ZIP_PATH"
mkdir -p "$BUILD_DIR"

python3 -m pip install --upgrade --no-compile -r "$ROOT_DIR/requirements-lambda.txt" -t "$BUILD_DIR"

cp "$ROOT_DIR/main.py" "$BUILD_DIR/main.py"
cp "$ROOT_DIR/lambda_handler.py" "$BUILD_DIR/lambda_handler.py"
cp -R "$ROOT_DIR/src" "$BUILD_DIR/src"
cp -R "$ROOT_DIR/../database/src" "$BUILD_DIR/database_src"

(
  cd "$BUILD_DIR"
  find . -type d \( -name "__pycache__" -o -name "*.dist-info" \) -prune -exec rm -rf {} +
  zip -qr "$ZIP_PATH" .
)

rm -rf "$BUILD_DIR"

echo "Created $ZIP_PATH"
