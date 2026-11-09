#!/bin/bash
# Publish a Summit OS update: bumps the version, records the notes, commits and pushes.
# Every iMac checking this repository picks it up (within ~2 minutes in Live testing mode).
#
#   tools/publish.sh "What changed" ["Another change" ...]          -> 1.22.0 becomes 1.22.1
#   tools/publish.sh --minor "Big new feature"                       -> 1.22.x becomes 1.23.0
#   tools/publish.sh --reboot "Kernel change"                        -> asks users to restart
set -euo pipefail
cd "$(dirname "$0")/.."
MINOR=0; RESTART=session
while [[ "${1:-}" == --* ]]; do case "$1" in --minor) MINOR=1;; --reboot) RESTART=reboot;; esac; shift; done
[ $# -ge 1 ] || { echo "usage: tools/publish.sh [--minor] [--reboot] \"note\" [\"note\" ...]"; exit 64; }
python3 - "$MINOR" "$RESTART" "$@" <<'PY'
import json, sys
minor, restart, notes = sys.argv[1] == "1", sys.argv[2], sys.argv[3:]
u = json.load(open("update.json"))
maj, mi, pa = (int(x) for x in u["version"].split("."))
mi, pa = (mi + 1, 0) if minor else (mi, pa + 1)
u.update(version=f"{maj}.{mi}.{pa}", build=maj * 10000 + mi * 100 + pa, notes=notes, restart=restart)
json.dump(u, open("update.json", "w"), indent=2, ensure_ascii=False); open("update.json", "a").write("\n")
print(f"Summit OS {u['version']} (build {u['build']})")
PY
bash -n hooks/post-install.sh && bash -n hooks/user.sh
for f in $(find overlay -name "*.py" -o -path "*/bin/summit-*" -o -path "*/sbin/summit-*" -o -path "*/lib/summitos/*" | grep -v "\.sh$"); do
  head -1 "$f" | grep -q python && python3 -m py_compile "$f" && rm -rf "$(dirname "$f")/__pycache__"
  head -1 "$f" | grep -qE "/(ba)?sh" && bash -n "$f"
done
V=$(python3 -c 'import json;print(json.load(open("update.json"))["version"])')
git add -A
git commit -q -m "Summit OS $V: $1"
git push -q origin HEAD
echo "Published Summit OS $V"
