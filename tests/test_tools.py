"""결정 품질: 에이전트 읽기 도구·모델·제한 시간(frontmatter, 명령줄 조립)과 프로젝트별 에이전트 디렉터리 헤드리스 테스트.
실제 claude/codex 는 부르지 않는다 — _run_cli 를 가짜로 바꿔 명령줄·작업 디렉터리·제한 시간만 본다."""
import asyncio, json, os, sys, tempfile, textwrap
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import Label, Select, SelectionList

tmp = os.path.realpath(tempfile.mkdtemp())
cfg = os.path.join(tmp, "cfg", "config.json")
adir = od.agents_dir(cfg)
os.makedirs(adir)
repo = os.path.join(tmp, "repo")
pdir = os.path.join(repo, ".orca-dash", "agents")
os.makedirs(pdir)


def write(d, name, text):
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(text))


# 1) 내장: review·final 은 읽기 도구를 갖고 직접 읽으라는 지시가 있다. goal 은 도구 없음
b = {a.id: a for a in od.BUILTIN_AGENTS}
assert b["review"].tools == b["final"].tools == ("Read", "Grep", "Glob") == od.READ_TOOLS
assert b["goal"].tools == () and all(a.model is None and a.timeout is None for a in od.BUILTIN_AGENTS)
for i in ("review", "final"):
    assert "파일을 직접 읽어 확인한 뒤 쓴다. 읽지 못한 것은 추측하지 않는다." in b[i].instructions, i
assert "직접 읽어" not in b["goal"].instructions
print("ok: builtin tools")

# 2) frontmatter 파싱: 정상 (대소문자·중복·값 뒤 주석), 생략 시 기본값
write(adir, "deep.md", """\
    ---
    name: 깊이 읽기
    context: diff, log        # 주석을 달아도 된다
    tools: read, Grep,glob, Read   # 읽기 전용만
    model: sonnet
    timeout: 120              # 초
    memo: off                 # 메모 안 받음
    ---
    역할: 파일을 읽고 쓴다.
    """)
write(adir, "plain.md", "---\nname: 기본\ntools:\nmodel:\ntimeout:\n---\n본문\n")
a = od.parse_agent_file(os.path.join(adir, "deep.md"))
assert a.tools == ("Read", "Grep", "Glob") and a.model == "sonnet" and a.timeout == 120.0, a
assert a.context == ("diff", "log") and a.memo is False, a
p = od.parse_agent_file(os.path.join(adir, "plain.md"))
assert p.tools == () and p.model is None and p.timeout is None, p

# 금지 도구·잘못된 timeout·잘못된 model 은 ConfigError (파일 경로와 이유가 함께)
bad_cases = {
    "bash.md": ("tools: Read, Bash", "Bash"),
    "edit.md": ("tools: Edit, Write", "Edit, Write"),
    "web.md": ("tools: WebFetch", "WebFetch"),
    "scoped.md": ("tools: Bash(git *)", "Bash(git"),
    "t0.md": ("timeout: 0", "timeout 은 0보다 큰 수(초) — 0"),
    "tneg.md": ("timeout: -5", "timeout 은 0보다 큰 수(초) — -5"),
    "tstr.md": ("timeout: 빨리", "timeout 은 0보다 큰 수(초) — 빨리"),
    "tinf.md": ("timeout: inf", "timeout 은 0보다 큰 수(초)"),
    "tnan.md": ("timeout: nan", "timeout 은 0보다 큰 수(초)"),
    "mflag.md": ("model: --dangerously-skip-permissions", "model 은 모델 이름 하나"),
    "mtwo.md": ("model: sonnet --tools Bash", "model 은 모델 이름 하나"),
}
for name, (line, want) in bad_cases.items():
    write(adir, name, f"---\nname: x\n{line}\n---\n본문\n")
    try:
        od.parse_agent_file(os.path.join(adir, name))
        raise SystemExit(f"should raise: {name}")
    except od.ConfigError as e:
        assert want in str(e) and os.path.join(adir, name) in str(e), (name, str(e))
try:
    od.parse_agent_file(os.path.join(adir, "bash.md"))
except od.ConfigError as e:
    assert "읽기 전용 Read, Grep, Glob 만 가능" in str(e), str(e)
agents, errs = od.load_agents(cfg)
ids = {x.id: x for x in agents}
assert set(ids) == {"goal", "review", "final", "deep", "plain"} and len(errs) == len(bad_cases), (ids.keys(), errs)
for name in bad_cases:
    os.remove(os.path.join(adir, name))
print("ok: frontmatter")

# 3) 명령줄 조립: 허용 플래그와 도구 목록, 모델 우선
ai = od.AIConfig(provider="claude", model="haiku", timeout=60)


def opt(cmd, flag):
    return cmd[cmd.index(flag) + 1]


c = od.claude_command(ai, b["goal"], "SYS", repo)            # 도구 없는 에이전트: 이전과 같은 명령줄
assert c == ["claude", "-p", "--no-session-persistence", "--tools", "", "--output-format", "json",
             "--system-prompt", "SYS", "--model", "haiku"], c
c = od.claude_command(ai, b["review"], "SYS", repo)
assert opt(c, "--tools") == "Read,Grep,Glob" and opt(c, "--permission-mode") == "dontAsk", c
assert "--strict-mcp-config" in c and opt(c, "--system-prompt") == "SYS" and opt(c, "--model") == "haiku", c
# 미리 승인(--allowedTools)하면 저장소 밖까지 읽히므로 쓰지 않고, 권한을 건너뛰는 플래그도 없다
assert not any(x in c for x in ("--allowedTools", "--allowed-tools", "--dangerously-skip-permissions")), c
assert "bypassPermissions" not in c and c[:2] == ["claude", "-p"], c
one = od.dataclasses.replace(b["review"], tools=("Grep",), model="opus")
c = od.claude_command(ai, one, "SYS", repo)
assert opt(c, "--tools") == "Grep" and opt(c, "--model") == "opus" and c.count("--model") == 1, c
c = od.claude_command(od.AIConfig(provider="claude", model=None), b["goal"], "SYS", repo)
assert "--model" not in c, c
# 읽을 로컬 저장소가 없거나(원격) 상황 전달이 꺼져 있으면 도구를 주지 않는다
for cfg_x, rd in ((ai, None), (ai, os.path.join(tmp, "nope")),
                  (od.AIConfig(provider="claude", model="haiku", include_context=False), repo)):
    c = od.claude_command(cfg_x, b["review"], "SYS", rd)
    assert opt(c, "--tools") == "" and "--permission-mode" not in c and "--strict-mcp-config" not in c, c
# 쓰기·실행 도구가 요청되면 (md 를 거치지 않고 만든 에이전트라도) ConfigError
for bad in (("Read", "Bash"), ("Edit",), ("Write",), ("Read,Bash",), ("default",)):
    try:
        od.claude_command(ai, od.dataclasses.replace(b["review"], tools=bad), "SYS", repo)
        raise SystemExit(f"should raise: {bad}")
    except od.ConfigError as e:
        assert "쓰기·실행 도구는 허용하지 않음" in str(e), str(e)
    try:   # 저장소가 없어 도구를 안 줄 상황이어도 거절한다
        od.claude_command(ai, od.dataclasses.replace(b["review"], tools=bad), "SYS", None)
        raise SystemExit(f"should raise: {bad}")
    except od.ConfigError:
        pass
print("ok: command line")

# 4) draft_prompt: 작업 디렉터리·제한 시간·모델이 실제 호출에 들어가는지 (_run_cli 가짜)
row = od.Row(key="k", source="local", pane_key="t:1", host="local", path=repo, repo="repo", worktree="feat",
             branch="feat", agent_type="claude", state="waiting", main_state=None, wait="질문",
             started_at=None, updated_at=None, tool="", summary="", detail="", unread=False,
             prompt="a.py 를 고쳐라", last_message="고쳤습니다. 더 할까요?")
runs = []


async def fake_cli(cmd, stdin, cwd, timeout):
    runs.append((cmd, stdin, cwd, timeout))
    if cmd[0] == "codex":
        with open(opt(cmd, "-o"), "w", encoding="utf-8") as f:
            f.write("코덱스 초안")
        return ""
    return json.dumps({"result": "초안", "is_error": False})


od._run_cli = fake_cli
other = tempfile.gettempdir()   # PromptScreen 이 원격일 때 넘기는 임시 디렉터리
assert asyncio.run(od.draft_prompt(ai, b["review"], row, "", "", other, repo)) == "초안"
cmd, stdin, cwd, timeout = runs[-1]
assert opt(cmd, "--tools") == "Read,Grep,Glob" and cwd == repo and timeout == 60, (cmd, cwd, timeout)
sysmsg = opt(cmd, "--system-prompt")
assert "[에이전트 상황]" in stdin and "직접 읽어 확인한 뒤 쓴다" in sysmsg
# 도구를 실제로 준 호출에만 [도구] 절이 붙는다 (없으면 작은 모델은 도구를 받아도 쓰지 않는다)
assert sysmsg == od.draft_system_prompt(b["review"], od.READ_TOOLS) and sysmsg.startswith(od.draft_system_prompt(b["review"]))
assert "[도구]" in sysmsg and "Read·Grep·Glob 도구로" in sysmsg and "반드시 도구를 써서" in sysmsg, sysmsg
assert "[도구]" not in od.draft_system_prompt(b["review"])
asyncio.run(od.draft_prompt(ai, b["goal"], row, "", "", other, repo))        # 도구 없음: 넘겨받은 cwd 그대로
assert opt(runs[-1][0], "--tools") == "" and runs[-1][2] == other and runs[-1][3] == 60, runs[-1]
assert "[도구]" not in opt(runs[-1][0], "--system-prompt")
asyncio.run(od.draft_prompt(ai, b["review"], row, "", "", other, None))      # 원격: 도구 없이, cwd 그대로
assert opt(runs[-1][0], "--tools") == "" and runs[-1][2] == other, runs[-1]
assert "[도구]" not in opt(runs[-1][0], "--system-prompt")
off = od.AIConfig(provider="claude", model="haiku", include_context=False)   # 상황 전달 끔: 도구도 주지 않는다
asyncio.run(od.draft_prompt(off, b["review"], row, "", "", other, repo))
assert opt(runs[-1][0], "--tools") == "" and runs[-1][2] == other and "[도구]" not in opt(runs[-1][0], "--system-prompt")
slow = od.dataclasses.replace(b["review"], model="sonnet", timeout=240.0)    # 에이전트 값이 전역보다 우선
asyncio.run(od.draft_prompt(ai, slow, row, "", "", other, repo))
assert opt(runs[-1][0], "--model") == "sonnet" and runs[-1][3] == 240.0, runs[-1]
asyncio.run(od.draft_prompt(ai, od.dataclasses.replace(b["goal"], timeout=5.0), row, "", "", other, repo))
assert opt(runs[-1][0], "--model") == "haiku" and runs[-1][3] == 5.0, runs[-1]
# 금지 도구: 호출 전에 DraftError 로 (창의 「AI 초안 실패」 경로) 끝나고 CLI 는 실행되지 않는다
n = len(runs)
try:
    asyncio.run(od.draft_prompt(ai, od.dataclasses.replace(b["review"], tools=("Bash",)), row, "", "", other, repo))
    raise SystemExit("should raise")
except od.DraftError as e:
    assert "Bash" in str(e) and "문제 발견" in str(e) and len(runs) == n, (str(e), runs[n:])
# codex: 도구 플래그 없이 기존 읽기 전용 샌드박스 그대로, 모델·제한 시간만 에이전트 값 우선
cx = od.AIConfig(provider="codex", model=None, timeout=90)
assert asyncio.run(od.draft_prompt(cx, b["review"], row, "", "", repo, repo)) == "코덱스 초안"
cmd, _, cwd, timeout = runs[-1]
assert cmd[:6] == ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only"], cmd
assert opt(cmd, "-C") == repo and "-m" not in cmd and "--tools" not in cmd and timeout == 90 and cmd[-1] == "-", cmd
asyncio.run(od.draft_prompt(cx, slow, row, "", "", repo, repo))
assert opt(runs[-1][0], "-m") == "sonnet" and runs[-1][3] == 240.0, runs[-1]
print("ok: draft_prompt call")

# 5) 프로젝트별 디렉터리: 내장 < 사용자 < 프로젝트, 잘못된 파일은 건너뛰고 오류로 전달
write(adir, "review.md", "---\nname: 사용자 리뷰\n---\n사용자 지시문\n")
write(adir, "final.md", "---\nname: 사용자 결정\nfinal: on\n---\n사용자 결정 지시문\n")
write(pdir, "review.md", """\
    ---
    name: 프로젝트 리뷰
    context: diff
    tools: Read, Grep
    timeout: 200
    step: 프로젝트 단계
    ---
    프로젝트 지시문
    """)
write(pdir, "domain.md", "---\nname: 도메인\n---\n도메인 지시문\n")
write(pdir, "final.md", "---\nname: 프로젝트 결정\ntools: Read, Bash\n---\n본문\n")   # 금지 도구 → 건너뜀
write(pdir, "goal.md", "---\nname: 프로젝트 목표\ntimeout: 0\n---\n본문\n")           # 잘못된 timeout → 건너뜀
write(pdir, "notes.txt", "md 가 아니면 읽지 않는다")
agents, errs = od.load_agents(cfg)                       # repo_dir 없으면 프로젝트 디렉터리는 읽지 않는다
ids = {x.id: x for x in agents}
assert ids["review"].name == "사용자 리뷰" and ids["review"].tools == () and "domain" not in ids and errs == [], errs
agents, errs = od.load_agents(cfg, repo_dir=repo)
ids = {x.id: x for x in agents}
assert [x.id for x in agents] == ["goal", "review", "final", "deep", "plain", "domain"], [x.id for x in agents]
r = ids["review"]
assert (r.name, r.tools, r.timeout, r.steps) == ("프로젝트 리뷰", ("Read", "Grep"), 200.0, ("프로젝트 단계",)), r
assert r.path == os.path.join(pdir, "review.md") and not r.builtin and r.instructions.strip() == "프로젝트 지시문"
assert ids["domain"].path == os.path.join(pdir, "domain.md")
assert ids["final"].name == "사용자 결정" and ids["final"].final      # 프로젝트 파일이 잘못됨 → 사용자 정의가 남는다
assert ids["goal"].builtin and ids["goal"].name == "목표 지향"         # 프로젝트 파일이 잘못됨 → 내장이 남는다
assert len(errs) == 2 and all(e.startswith(pdir) for e in errs), errs
assert any("final.md" in e and "Bash" in e for e in errs) and any("goal.md" in e and "timeout" in e for e in errs), errs
# 설정의 생각의 흐름 덮어쓰기는 프로젝트 정의 위에도 적용된다
agents, _ = od.load_agents(cfg, {"review": ["내 단계"], "domain": ["d1", "d2"]}, repo_dir=repo)
ids = {x.id: x for x in agents}
assert ids["review"].steps == ("내 단계",) and ids["review"].name == "프로젝트 리뷰" and ids["domain"].steps == ("d1", "d2")
# 저장소에 .orca-dash/agents 가 없으면 사용자 정의 그대로, 오류 없음
empty = os.path.join(tmp, "empty"); os.makedirs(empty)
agents, errs = od.load_agents(cfg, repo_dir=empty)
assert {x.id: x.name for x in agents}["review"] == "사용자 리뷰" and errs == [], errs
print("ok: project agents")

# 6) 앱: p 로 창을 열면 로컬 저장소의 프로젝트 정의가 목록에 들어오고 오류가 창 상단에 보인다. 옵션 탭 설명에 도구·모델·제한 시간
calls = []


async def fake_draft(cfg, agent, row, note, current, cwd, repo_dir=None, drafts=""):
    calls.append((agent.id, agent.name, agent.tools, agent.timeout, cwd, repo_dir)); return f"초안({agent.id})"


od.draft_prompt = fake_draft


async def app_flow():
    settings = od.Settings(ai="claude", ai_agents=["review"])
    app = od.OrcaDash(settings, ai, config_path=cfg, files=[od.Source(label="file", file="/dev/null")])
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.input_source.available = False
        app.source_by_label["local"] = od.Source(label="local")   # 로컬 소스의 행으로 취급 (전송은 하지 않는다)
        app.rows = [row]; app._render_table(); await pilot.pause()
        await pilot.press("p"); await pilot.pause()
        scr = app.screen
        assert isinstance(scr, od.PromptScreen) and scr.repo_dir == repo and scr.cwd == repo, scr
        got = {x.id: x.name for x in scr.agents}
        assert got["review"] == "프로젝트 리뷰" and got["domain"] == "도메인" and got["final"] == "사용자 결정", got
        assert set(scr.query_one("#agents", SelectionList).selected) == {"review"}
        status = str(scr.query_one("#ai-status", Label).render())
        assert "에이전트 파일 오류 2건" in status and pdir[:20] in status, status
        await pilot.press("ctrl+g"); await pilot.pause(0.3)
        assert calls == [("review", "프로젝트 리뷰", ("Read", "Grep"), 200.0, repo, repo)], calls
        await pilot.press("escape"); await pilot.pause()
        # 원격 소스의 행이면 저장소를 읽지 않는다: 프로젝트 정의 없음
        app.source_by_label["srv"] = od.Source(label="srv", env="srv")
        app.rows = [od.dataclasses.replace(row, source="srv")]; app._render_table(); await pilot.pause()
        await pilot.press("p"); await pilot.pause()
        scr = app.screen
        got = {x.id: x.name for x in scr.agents}
        assert scr.repo_dir is None and got["review"] == "사용자 리뷰" and "domain" not in got, got
        await pilot.press("escape"); await pilot.pause()
        # 옵션 > 에이전트 탭 설명 (사용자 디렉터리 기준)
        sscr = od.SettingsScreen(settings, cfg, [], file_mode=True)
        app.push_screen(sscr); await pilot.pause()
        d = sscr._agent_desc(od.pick_agent(sscr.agents, "deep"))
        assert "도구: Read, Grep, Glob" in d and "모델: sonnet" in d and "제한 시간: 120초" in d, d
        d = sscr._agent_desc(b["review"])
        assert "도구: Read, Grep, Glob" in d and "모델:" not in d and "제한 시간:" not in d, d
        d = sscr._agent_desc(b["goal"])
        assert "도구:" not in d, d
        sscr.query_one("#agent-pick", Select).value = "deep"; await pilot.pause()
        assert "모델: sonnet" in str(sscr.query_one("#agent-desc", Label).render())
        await pilot.press("escape"); await pilot.pause()
        app.exit()


asyncio.run(app_flow())
print("ok: app flow")
print("ALL OK")
