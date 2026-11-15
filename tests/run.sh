#!/bin/zsh
# 헤드리스 테스트 전체 실행. 저장소 루트의 .venv 를 쓰고, 없으면 PATH 의 python3 를 쓴다.
set -e
ROOT="${0:A:h:h}"
PY="$ROOT/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
cd "$ROOT"
for t in tests/test_settings.py tests/test_agents.py tests/test_steps.py tests/test_final.py tests/test_tools.py; do
  echo "== $t"; "$PY" "$t" 2>&1 | tail -1
done
