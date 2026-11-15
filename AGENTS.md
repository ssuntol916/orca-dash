# AGENTS.md — orca-dash 에서 일하는 에이전트의 규칙

이 저장소에서 코드를 고치는 에이전트(하위 워크트리의 code agent)와 그 일을 맡기고 병합하는 「오케스트라」가 함께 따르는 규칙이다. 프로젝트의 목표와 범위는 `GOAL.md`, 기능 설명은 `README.md` 와 `orca_dash.py` 상단 docstring 에 있다.

## 커밋 규칙

`.githooks/commit-msg` 가 메시지의 모양을 기계로 판정한다. 새로 받은 뒤 한 번 `git config core.hooksPath .githooks` 를 실행해야 훅이 동작한다.

- 제목: `<type>(<scope>): <한국어 명사구>`. type 은 `feat|fix|test|docs|refactor|chore|merge|ops|db|release` 중 하나, scope 는 소문자. 100자 이내. 끝에 "다" 나 종결 문장부호를 쓰지 않는다.
- 제목 다음 줄은 비우고, 본문은 `- ` 로 시작하는 줄 2개 이상으로 주요 변경을 적는다. 권고는 2~4개이며 그보다 많으면 커밋을 가를 수 있는지 살핀다. 본문 줄도 "다" 나 문장부호로 끝내지 않는다.
- `fixup!`·`squash!`·`amend!`, Git 기본 `Merge …`·`Revert …` 제목은 쓰지 않는다. `merge` type 은 부모가 둘 이상인 실제 병합 커밋에만 쓴다.
- `Co-Authored-By`, `Signed-off-by`, 생성 도구 표기(`Generated with`, 🤖) 줄은 넣지 않는다.
- 기능과 문서(README·docstring)는 같은 커밋에서 고친다. 새 기능에는 `tests/` 에 같은 방식의 헤드리스 테스트를 더한다.

## 코드 규칙

- 코드는 `orca_dash.py` 단일 파일 안에서 고친다. 새 모듈을 만들지 않는다.
- 테스트는 `tests/run.sh` 로 전부 돌린다(저장소 루트의 `.venv` 사용). 실제 `claude`/`codex` 호출은 테스트에서 가짜 함수로 바꾼다.
- 하위 워크트리에는 `.venv` 가 없으므로 메인 체크아웃의 `.venv` 를 심볼릭 링크로 연결해 쓴다(`ln -s /Users/songjunho/projects/utility/orca-dash/.venv <워크트리>/.venv`).
- 사용자가 쓰는 Orca Dash 앱(`orca_dash.py` 프로세스)은 건드리지 않는다. `pkill -f orca_dash.py` 같은 패턴 kill 은 금지. 화면을 눌러 봐야 하면 `python orca_dash.py --file tests/fixtures/sample.json` 으로 따로 띄우고 자기가 띄운 PID 만 끈다.
- 사용자 설정(`~/.config/orca-dash/`)에는 쓰지 않는다. 테스트는 임시 디렉터리를 쓴다.

## 오케스트라 (메인 체크아웃)

메인 체크아웃 `/Users/songjunho/projects/utility/orca-dash` 는 조율 전용이다. Orca 표시 이름은 `오케스트라`, 브랜치는 `dev`. 코드를 직접 고치지 않고 하위 워크트리의 code agent 에게 맡기고 결과를 검토·병합한다. 모든 응답은 한국어로 한다.

### 브랜치

- 일상 작업은 `dev` 에 모은다. 하위 에이전트 결과는 검토 뒤 묻지 않고 `dev` 에 병합하고 `git push origin dev` 한다.
- `dev → main` 병합과 앱 재빌드(`scripts/build-app.sh`)·사용자 앱 재시작은 사용자의 명시적 허락을 받은 뒤에만 한다. 이 저장소에는 운영 서버·DB·배포가 없다. 자동 배포 연결은 하지도 제안하지도 않는다.

### 워크트리 풀

- `~/orca/workspaces/orca-dash/` 아래 최대 5개. 동시에 맡기는 일도 최대 5개. 다 바쁘면 대기열에 두고 빈 워크트리가 생기면 맡긴다.
- 맡기기 전에 `orca worktree ps --json` 으로 확인하고, 비어 있고 `dev` 와 맞춰진 워크트리를 먼저 재사용한다. 워크트리는 지우지 않는다.
  - 재사용: `orca agent launch --agent claude --worktree path:<wt> --prompt "$(cat <지시서>)" --json`
  - 새로 만들기: `orca worktree create --name <이름> --base-branch dev --parent-worktree active --agent claude --prompt "..." --json`
- 표시 이름으로 상태를 보인다.
  - 일하는 중: `orca worktree set --worktree path:<wt> --display-name "[작업중] 워크트리N · <짧은 작업명>" --comment "<한 줄 요약>" --workspace-status in-progress`
  - 쉬는 중: 정확히 `[대기] 워크트리N`, `--comment ""`, `--workspace-status todo`

### 지시서

scratchpad 에 md 로 쓰고 `--prompt` 로 넘긴다. 구성: 목표 → 현재 구조(참고 파일 경로) → 요구사항 → 시험 → 지킬 것 → 보고.

「지킬 것」에는 반드시 넣는다.

- 자기 브랜치에 커밋까지만. push, 병합, 사용자 설정 파일 쓰기, 사용자 앱 재시작 금지.
- 위 「커밋 규칙」과 「코드 규칙」을 따른다. 훅이 판정한다.
- 여러 작업이 동시에 돌 때는 다른 작업의 범위와 그 인터페이스 계약(이름·시그니처)을 알려 주고, 없는 기능은 getattr 이나 기본값으로 안전하게 동작하게 한다. 공통 영역(Settings 필드·SettingsScreen·키 바인딩·run.sh 목록·README 테스트 절) 수정은 최소로 한다.
- 「보고」: 커밋 목록, 고른 방법과 임의로 정한 기본값, 테스트 결과, 병합 시 충돌 예상 지점, 오케스트라가 할 일을 짧게.

### 감시

- 맡긴 직후 background 셸 루프를 건다. 15초마다 `orca worktree ps --json` 에서 그 워크트리의 `agents[].state` 를 보고, `working` 이 아니거나 터미널이 사라지면 깨어난다. `orca terminal show` 의 `agentWait` 만 믿지 않는다.
- 멈추면 터미널 화면(`orca terminal read`)이나 대화 기록에서 마지막 질문을 읽는다. 지시서에 기준이 있으면 `orca terminal send` 로 답하고 사용자에게 알린다. 사용자가 정할 일이면 사용자에게 묻는다.

### 끝난 뒤 순서

1. 검토: diff, 커밋 메시지, 지시서 요구사항 충족 여부.
2. 메인 체크아웃에서 `git merge --no-ff <워크트리 브랜치>`. 메시지는 `merge(<scope>): <한국어 명사구>` + `- ` 본문 2줄 이상. 충돌은 양쪽 의도를 살려 풀고, 중복 구현은 계약을 먼저 맡은 쪽을 남긴다.
3. `.venv/bin/python -m py_compile orca_dash.py` 와 `tests/run.sh` 를 돌리고 통과하면 `git push origin dev`.
4. 쉬는 워크트리를 모두 `git -C <wt> merge --ff-only dev` 로 최신화.
5. `orca terminal close --worktree path:<wt> --all` 로 세션을 닫는다.
6. 이름을 `[대기] 워크트리N` 으로 되돌린다(comment 비움, status todo).
7. 사용자에게 결과를 보고하고 main 반영·앱 재빌드 여부를 묻는다. 허락을 받으면: `git switch main && git merge --ff-only dev` → (앱 번들을 바꿨으면) `scripts/build-app.sh` → 앱 재시작 → `git push origin main` → `git switch dev`.
