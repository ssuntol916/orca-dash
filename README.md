# orca-dash

Orca 에이전트 상태를 터미널에서 한눈에 보는 TUI 대시보드입니다. `orca worktree ps --json` 결과를 주기적으로 읽어 표로 보여 주고, 선택한 에이전트에게 프롬프트를 보내거나 로컬 claude·codex로 프롬프트 초안을 만들 수 있습니다. 실행 방법과 키는 `orca_dash.py` 상단 설명을 참고하세요.

## 커밋 메시지 훅 활성화

이 저장소는 `.githooks/commit-msg`로 커밋 메시지 규격(`<type>(<scope>): <한국어 명사구>` 제목과 `- `로 시작하는 본문 bullet 2개 이상)을 검사합니다. 훅은 저장소 안에 들어 있지만 git은 기본적으로 `.git/hooks`만 보므로, 새로 clone한 뒤에는 저장소 루트에서 `git config core.hooksPath .githooks`를 한 번 실행해야 훅이 동작합니다. 규격 전체는 훅 파일 머리의 주석에 있고, 규격에 맞지 않는 메시지는 커밋이 거절되며 이유와 예시가 함께 출력됩니다.
