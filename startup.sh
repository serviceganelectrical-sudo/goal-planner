#!/bin/sh
set -eu
cd /workspace

if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/_stcore/health; then
  exit 0
fi
# also accept root if health path differs
if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  # If something answers but is not streamlit health, only skip if it's streamlit
  if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/_stcore/health 2>/dev/null; then
    exit 0
  fi
fi

if command -v fuser >/dev/null 2>&1; then
  fuser -k 8080/tcp >/dev/null 2>&1 || true
  sleep 0.3
fi

mkdir -p /workspace/data/goals /workspace/screenshots /tmp

# Streamlit on the preview port (0.0.0.0:8080)
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

python3 -m streamlit run /workspace/streamlit_app.py \
  --server.address 0.0.0.0 \
  --server.port 8080 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false \
  >>/tmp/app-startup.log 2>&1 &

# wait briefly for bind
i=0
while [ "$i" -lt 30 ]; do
  if curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8080/_stcore/health 2>/dev/null \
     || curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8080/ 2>/dev/null; then
    exit 0
  fi
  i=$((i + 1))
  sleep 0.3
done
exit 0
