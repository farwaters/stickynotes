#!/usr/bin/env bash
# Refuse battery (ethical hacker). No exploit payloads. Workshop only.
# Usage: tests/security-battery.sh [product-root]
set -euo pipefail
ROOT="$(cd "${1:-$(dirname "$0")/..}" && pwd)"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0
pass() { printf 'PASS %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1" >&2; FAIL=1; }

# S1 default bind
if grep -q 'STICKYNOTE_BIND", "127.0.0.1"' "$ROOT/serve.py" \
  && ! grep -q 'STICKYNOTE_BIND", "0.0.0.0"' "$ROOT/serve.py"; then
  pass S1-default-bind-localhost
else
  fail S1-default-bind-localhost
fi

# S2 POST requires loopback (source contract)
if grep -q 'def _local_ok' "$ROOT/serve.py" \
  && grep -q 'send_error(403)' "$ROOT/serve.py"; then
  pass S2-post-loopback-guard
else
  fail S2-post-loopback-guard
fi

# S5 textContent for payload fields
if grep -q 'el.querySelector(".body").textContent' "$ROOT/board.html" \
  && grep -q 'el.querySelector(".slug").textContent' "$ROOT/board.html" \
  && grep -q 'el.querySelector(".from").textContent' "$ROOT/board.html"; then
  pass S5-textContent-payload
else
  fail S5-textContent-payload
fi

# S6 index is env, not query
if grep -q 'os.environ.get("NOTICE_BOARD_INDEX"' "$ROOT/serve.py" \
  && ! grep -q 'urlparse(self.path).query' "$ROOT/serve.py"; then
  pass S6-index-env-not-query
else
  fail S6-index-env-not-query
fi

# S9 wallet stub + no .env in tree
if grep -q 'wallet not in this repo' "$ROOT/serve.py" \
  && ! find "$ROOT" -name .env -o -name '*.pem' | grep -q .; then
  pass S9-no-secrets
else
  fail S9-no-secrets
fi

# S10 TEST look — product faces only (not workshop iceberg)
S10_PATHS=("$ROOT/README.md" "$ROOT/docs" "$ROOT/fixtures" "$ROOT/board.html" "$ROOT/serve.py")
if grep -RInE 'this is test data|TEST ENVIRONMENT|UAT only|dummy PI' \
  --exclude='*.bkp' "${S10_PATHS[@]}" >/tmp/s10.out 2>/dev/null \
  && [ -s /tmp/s10.out ]; then
  cat /tmp/s10.out >&2
  fail S10-test-look
else
  pass S10-test-look
fi

# S11 302 location is /notice-board only
IDX=/tmp/stickynote-battery-index.md
VIEW=/tmp/stickynote-battery-view.json
cp "$ROOT/fixtures/NOTICE-BOARD.md" "$IDX"
cp "$ROOT/fixtures/VIEW.json" "$VIEW"

python3 - <<PY
import os, sys, threading, urllib.request
from http.server import HTTPServer
os.chdir("$ROOT")
os.environ["NOTICE_BOARD_INDEX"] = "$IDX"
os.environ["NOTICE_BOARD_VIEW"] = "$VIEW"
sys.path.insert(0, "$ROOT")
import serve
httpd = HTTPServer(("127.0.0.1", 19134), serve.Handler)
t = threading.Thread(target=httpd.serve_forever, daemon=True)
t.start()

class Noredir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

opener = urllib.request.build_opener(Noredir)
code = loc = None
try:
    opener.open("http://127.0.0.1:19134/")
except urllib.error.HTTPError as e:
    code, loc = e.code, e.headers.get("Location")

# S3 bad json
req = urllib.request.Request(
    "http://127.0.0.1:19134/api/board",
    data=b"not-json",
    method="POST",
    headers={"Content-Type": "application/json"},
)
s3 = None
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    s3 = e.code

# S4 unknown
s4 = urllib.request.urlopen("http://127.0.0.1:19134/no-such").getcode() if False else None
try:
    urllib.request.urlopen("http://127.0.0.1:19134/no-such")
except urllib.error.HTTPError as e:
    s4 = e.code

# S7 api board fixtures
raw = urllib.request.urlopen("http://127.0.0.1:19134/api/board").read().decode()
s7 = "/home/" not in raw and "05-Keys" not in raw

# S2 local POST allowed
req2 = urllib.request.Request(
    "http://127.0.0.1:19134/api/board",
    data=b'{"slug":"sample-ask-note","action":"park"}',
    method="POST",
    headers={"Content-Type": "application/json"},
)
s2local = urllib.request.urlopen(req2).status

# S3 oversize
req3 = urllib.request.Request(
    "http://127.0.0.1:19134/api/board",
    data=b"x" * 5000,
    method="POST",
    headers={"Content-Type": "application/json"},
)
s3big = None
try:
    urllib.request.urlopen(req3)
except urllib.error.HTTPError as e:
    s3big = e.code

httpd.shutdown()
open("/tmp/s-battery.env", "w").write(
    f"S11={code}:{loc}\nS3={s3}\nS4={s4}\nS7={int(s7)}\nS2L={s2local}\nS3B={s3big}\n"
)
PY

# shell-check live results
# shellcheck disable=SC1091
. /tmp/s-battery.env
if [ -f "$ROOT/cockpit.html" ]; then
  pass S11-cockpit-present-skip-302
elif [ "$S11" = "302:/notice-board" ]; then
  pass S11-302-notice-board
else
  fail "S11-302-notice-board ($S11)"
fi
if [ "$S3" = "400" ]; then pass S3-bad-json; else fail "S3-bad-json ($S3)"; fi
if [ "$S3B" = "400" ]; then pass S3-oversize; else fail "S3-oversize ($S3B)"; fi
if [ "$S4" = "404" ]; then pass S4-unknown-404; else fail "S4-unknown-404 ($S4)"; fi
if [ "$S7" = "1" ]; then pass S7-api-no-home; else fail S7-api-no-home; fi
if [ "$S2L" = "200" ]; then pass S2-local-post-ok; else fail "S2-local-post-ok ($S2L)"; fi

# S8 author privacy — denylist vs the payload under test.
# Workshop trees (have changes/RFC iceberg) are not the public face.
if [ -d "$ROOT/changes" ]; then
  pass S8-workshop-tree-skip-denylist
elif [ -x "$HERE/scripts/public-gate.sh" ]; then
  if bash "$HERE/scripts/public-gate.sh" "$ROOT"; then
    pass S8-author-privacy-gate
  else
    fail S8-author-privacy-gate
  fi
else
  pass S8-author-privacy-gate-skipped-no-denylist
fi

if [ "$FAIL" -ne 0 ]; then
  echo "security-battery: FAIL" >&2
  exit 1
fi
echo "security-battery: PASS"
