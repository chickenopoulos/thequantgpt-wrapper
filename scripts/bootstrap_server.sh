#!/usr/bin/env bash
# Bootstrap Ubuntu 22.04+ for TheQuantGPT Cursor Lab (client server).
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/chickenopoulos/thequantgpt-wrapper.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/thequantgpt-wrapper}"

echo "==> System packages"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-venv python3-pip tmux curl

echo "==> Clone wrapper repo"
if [[ -d "$INSTALL_DIR/.git" ]]; then
  git -C "$INSTALL_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

echo "==> Python venv"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

if [[ ! -f config.yaml ]]; then
  cp config.example.yaml config.yaml
  echo "Created config.yaml — edit tqg_api.base_url and set TQG_API_KEY"
fi

mkdir -p data/binance runs reports

echo "==> Done"
echo "Next:"
echo "  1. export TQG_API_KEY=..."
echo "  2. python scripts/tqg_init.py   # checks bundled Binance daily OHLCV"
echo "  3. Configure Cursor MCP (tqg_client/mcp_config.example.json)"
echo "  4. Connect Cursor to this server via SSH remote workspace"
echo "  5. python scripts/tqg_create_run.py --title \"<first strategy>\""
