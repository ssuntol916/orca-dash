# orca-dash

Orca 에이전트 상태를 터미널에서 한눈에 보는 TUI 대시보드입니다. `orca worktree ps --json` 결과를 주기적으로 읽어 표로 보여 주고, 선택한 에이전트에게 프롬프트를 보내거나 로컬 claude·codex로 프롬프트 초안을 만들 수 있습니다. 실행 방법과 키는 `orca_dash.py` 상단 설명을 참고하세요.

## 커밋 메시지 훅 활성화

이 저장소는 `.githooks/commit-msg`로 커밋 메시지 규격(`<type>(<scope>): <한국어 명사구>` 제목과 `- `로 시작하는 본문 bullet 2개 이상)을 검사합니다. 훅은 저장소 안에 들어 있지만 git은 기본적으로 `.git/hooks`만 보므로, 새로 clone한 뒤에는 저장소 루트에서 `git config core.hooksPath .githooks`를 한 번 실행해야 훅이 동작합니다. 규격 전체는 훅 파일 머리의 주석에 있고, 규격에 맞지 않는 메시지는 커밋이 거절되며 이유와 예시가 함께 출력됩니다.

## macOS 앱으로 쓰기 (Orca Dash.app)

터미널 없이 독립된 창과 Dock 아이콘을 가진 앱으로 쓰려면 Alacritty를 껍데기로 쓰는 앱 번들을 만듭니다. Homebrew의 alacritty cask는 공증 미통과로 비활성화되어 있어, 빌드 스크립트가 GitHub 공식 릴리스 dmg를 받아 번들을 복사한 뒤 전용 설정과 실행 스크립트를 넣고 ad-hoc 서명합니다. `gh` CLI 로그인이 필요합니다.

```
scripts/build-app.sh                      # ~/Applications/Orca Dash.app 설치
scripts/build-app.sh --install-dir /Applications
```

앱은 이 저장소의 `.venv/bin/python`으로 `orca_dash.py`를 실행하므로 저장소를 옮기면 다시 빌드해야 합니다. 실행 옵션은 대시보드에서 `o` 키로 바꾸면 설정 파일에 저장되어 앱에도 그대로 적용됩니다. 명령줄 인자로 고정하고 싶은 값만 설치된 앱의 `Contents/Resources/launch.sh` 안 `ARGS` 배열에 적습니다. 창 크기·글꼴은 `app/alacritty.toml`에서 바꾸고 다시 빌드합니다. 개인 Alacritty 설정(`~/.config/alacritty`)과는 무관합니다.
