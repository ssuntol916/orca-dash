#!/bin/zsh
# Orca Dash 가 실제로 실행되는 자리. 로그인 셸(zsh -l)에서 source 되므로 PATH 에 orca·claude·codex 가 있다.
#
# REPO 는 build-app.sh 가 빌드 시점에 채운다. 옵션은 대시보드에서 o 키로 바꾸면 ~/.config/orca-dash/config.json
# 에 저장되므로 보통 ARGS 는 비워 둔다. 명령줄 인자로 고정할 값만 적는다 (파일 값보다 우선).
#   예) ARGS=(--config "$HOME/.config/orca-dash/work.json" --ai off)
REPO="__REPO__"
ARGS=()

PYTHON="$REPO/.venv/bin/python"
SCRIPT="$REPO/orca_dash.py"

# Finder 에서 띄운 앱의 로그인 셸에는 orca·claude·codex 가 PATH 에 없다. (.zshrc 는 대화식 셸에서만
# 읽히고, Orca CLI 경로는 Orca 터미널 안에서만 주어진다.) 알려진 위치를 앞에 넣는다.
# 다른 곳에 있으면 ORCA_DASH_EXTRA_PATH 에 콜론으로 이어 적는다.
for dir in \
  "${ORCA_DASH_EXTRA_PATH:-}" \
  "$HOME/.local/bin" \
  "/Applications/Orca.app/Contents/Resources/bin" \
  "$HOME/Applications/Orca.app/Contents/Resources/bin" \
  "/opt/homebrew/bin" "/usr/local/bin"; do
  [[ -n "$dir" && -d "${dir%%:*}" ]] && PATH="$dir:$PATH"
done
export PATH

if [[ -n "${ORCA_DASH_DRY_RUN:-}" ]]; then
  print "python: $PYTHON"; print "script: $SCRIPT"
  for c in orca claude codex; do print "$c: $(command -v $c || print 없음)"; done
  return 0 2>/dev/null || exit 0
fi

cd "$REPO" 2>/dev/null
if [[ ! -x "$PYTHON" || ! -f "$SCRIPT" ]]; then
  print -u2 "Orca Dash: 실행 파일을 찾을 수 없습니다.\n  python: $PYTHON\n  script: $SCRIPT\n저장소 위치가 바뀌었으면 scripts/build-app.sh 를 다시 실행하세요."
  print -n "아무 키나 누르면 닫힙니다…"; read -k1
  exit 1
fi

"$PYTHON" "$SCRIPT" "${ARGS[@]}"
status=$?
if (( status != 0 )); then
  print -u2 "\nOrca Dash 가 오류로 종료되었습니다 (exit $status)."
  print -n "아무 키나 누르면 닫힙니다…"; read -k1
fi
exit $status
