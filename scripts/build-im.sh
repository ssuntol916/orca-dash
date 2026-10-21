#!/bin/zsh
# 입력 소스 전환 보조 도구(orca-dash-im)를 app/imselect.swift 에서 빌드해 bin/ 에 둔다.
# 대시보드는 bin/orca-dash-im 이 있으면 한글 입력기로 되돌릴 때 이것을 쓴다 (없으면 macism 을 PATH 에서 찾음).
set -euo pipefail
REPO="${0:A:h:h}"
mkdir -p "$REPO/bin"
if ! command -v swiftc >/dev/null; then
  echo "swiftc 가 없어 orca-dash-im 을 빌드하지 못했습니다. Xcode Command Line Tools 를 설치하거나" >&2
  echo "brew tap laishulu/homebrew && brew install macism 으로 대체할 수 있습니다." >&2
  exit 1
fi
swiftc -O -o "$REPO/bin/orca-dash-im" "$REPO/app/imselect.swift" -framework Cocoa -framework Carbon 2>&1 | grep -v warning || true
[[ -x "$REPO/bin/orca-dash-im" ]] && echo "✔ $REPO/bin/orca-dash-im ($("$REPO/bin/orca-dash-im" --version))"
