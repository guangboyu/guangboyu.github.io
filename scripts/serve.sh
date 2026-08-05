#!/usr/bin/env bash
# Serve the site for local preview.
#
#   ./scripts/serve.sh          # port 8000
#   ./scripts/serve.sh 8080     # any other port
#
# Previewing from a MacBook over SSH: forward the port when you connect, then
# open http://localhost:8000 in a browser on the Mac.
#
#   ssh -L 8000:localhost:8000 guangbo@GuangboLab
#
set -euo pipefail

PORT="${1:-8000}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
echo "Serving $ROOT on http://localhost:$PORT"
echo "If you are on another machine, forward the port:"
echo "  ssh -L $PORT:localhost:$PORT $(whoami)@$(hostname)"
echo "Ctrl-C to stop."
exec python3 -m http.server "$PORT" --bind 127.0.0.1
