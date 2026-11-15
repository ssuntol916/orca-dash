"""진행 판정: 에이전트 등록·요청 본문·JSON 해석·정지 감지·알림·모달 키(Ctrl+T) 헤드리스 테스트."""
import asyncio, json, os, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import DataTable, Select, SelectionList, TextArea

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
tmp = tempfile.mkdtemp(); cfg = os.path.join(tmp, "cfg", "config.json")
adir = od.agents_dir(cfg); os.makedirs(adir)

# 1) 등록: 내장이지만 작성 에이전트 목록에는 없고, include_hidden 일 때만 보인다
v = od.VERDICT_AGENT
assert v.id == "verdict" and v.name == "진행 판정" and not v.final and not v.memo and v.builtin
assert v.context == ("instruction", "last_message", "goal", "diff", "log") and len(v.steps) == 4
assert [a.id for a in od.BUILTIN_AGENTS] == ["goal", "review", "final"]
agents, errs = od.load_agents(cfg)
assert [a.id for a in agents] == ["goal", "review", "final"] and errs == []
hidden, _ = od.load_agents(cfg, {"verdict": ["단계A"]}, include_hidden=True)
assert [a.id for a in hidden] == ["goal", "review", "final", "verdict"] and hidden[-1].steps == ("단계A",)
assert [a.id for a in od.pick_agents(agents, ["verdict"])] == ["goal"]          # 설정에 적어도 초안에는 안 쓰임
assert od.load_verdict_agent(cfg) == v
assert od.load_verdict_agent(cfg, {"verdict": ["단계A"]}).steps == ("단계A",)
# 사용자 verdict.md 는 판정 에이전트를 덮지만 여전히 목록에 안 나오고, memo·final 은 강제로 꺼진다
open(os.path.join(adir, "verdict.md"), "w").write("---\nname: 내 판정\nmemo: on\nfinal: on\ncontext: goal\n---\n역할: 내 기준.\n")
assert [a.id for a in od.load_agents(cfg)[0]] == ["goal", "review", "final"]
mine = od.load_verdict_agent(cfg)
assert mine.name == "내 판정" and not mine.memo and not mine.final and mine.context == ("goal",) and not mine.builtin
repo = os.path.join(tmp, "repo"); os.makedirs(os.path.join(repo, ".orca-dash", "agents"))
open(os.path.join(repo, ".orca-dash", "agents", "verdict.md"), "w").write("---\nname: 저장소 판정\n---\n역할: 저장소 기준.\n")
assert od.load_verdict_agent(cfg, None, repo).name == "저장소 판정"          # 저장소 정의가 사용자 정의를 덮음
open(os.path.join(adir, "verdict.md"), "w").write("깨진 파일\n")
assert od.load_verdict_agent(cfg) == v                                          # 잘못된 파일은 무시하고 내장
os.remove(os.path.join(adir, "verdict.md")); os.remove(os.path.join(repo, ".orca-dash", "agents", "verdict.md"))
print("ok: registry")

# 2) 요청 본문과 시스템 프롬프트
def git(*a): subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True)
git("init", "-q", "-b", "main"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
open(os.path.join(repo, "GOAL.md"), "w").write("목표: 빠르게\n")
open(os.path.join(repo, "a.py"), "w").write("x = 1\n")
git("add", "."); git("commit", "-q", "-m", "init")
head0 = asyncio.run(od.repo_head(repo))
open(os.path.join(repo, "a.py"), "w").write("x = 2\n")
row = od.Row(key="k", source="local", pane_key="t:1", host="local", path=repo, repo="repo", worktree="wt",
             branch="main", agent_type="claude", state="waiting_input", main_state=None, wait="질문",
             started_at=None, updated_at=1000.0, tool="", summary="", detail="", unread=False,
             prompt="a.py 를 고쳐라", last_message="고쳤습니다. 더 할까요?")
now = time.time()
hist = [{"at": now - 60, "text": "두 번째\n지시", "auto": True}, {"at": now - 120, "text": "첫 지시", "auto": False}]
ht = od.history_text(hist)
assert ht.splitlines()[0].endswith("(사람) 첫 지시") and ht.splitlines()[1].endswith("(자동) 두 번째 지시"), ht
assert od.history_text([]) == "" and od.history_text(None) == ""
r = asyncio.run(od.build_draft_request(v, row, ht, "", True, repo))
for sec in ("[에이전트 상황]", "[원래 지시]", "[마지막 응답]", "[프로젝트 목표] (GOAL.md)", "[변경분]", "[최근 커밋]"):
    assert sec in r, (sec, r)
assert "x = 2" in r and "목표: 빠르게" in r and "init" in r and "[사용자 메모]" not in r and "[기존 초안]" not in r
assert r.rstrip().endswith("[최근 전송 기록]\n" + ht), r
assert json.loads(r.split("[에이전트]\n", 1)[1].split("\n경로:", 1)[0])["agent"]["character"] == "verdict"
r = asyncio.run(od.build_draft_request(v, row, "", "", True, repo)); assert "[최근 전송 기록]" not in r
r = asyncio.run(od.build_draft_request(v, row, ht, "", False, repo))
assert "[최근 전송 기록]" not in r and "[원래 지시]" not in r                  # 상황 전달을 끄면 상태만
r = asyncio.run(od.build_draft_request(od.BUILTIN_AGENTS[0], row, ht, "", True, repo))
assert "[최근 전송 기록]" not in r                                              # 다른 메모 없는 에이전트는 그대로
sp = od.draft_system_prompt(v)
assert sp.startswith(od.VERDICT_SYSTEM) and "[역할] (character: verdict)" in sp and "심사자" in sp
assert '"done" | "continue" | "stuck"' in sp and "프롬프트 본문만" not in sp
assert od.draft_system_prompt(od.BUILTIN_AGENTS[0]).startswith(od.DRAFT_SYSTEM)
print("ok: request")

# 3) JSON 해석: 정상 · 펜스 · 앞뒤 설명 · 깨진 것
p = od.parse_verdict('{"verdict": "done", "reason": "테스트가 모두 통과했다"}')
assert p == od.Verdict("done", "테스트가 모두 통과했다") and p.label == "달성" and not p.failed
p = od.parse_verdict('```json\n{"verdict": "stuck", "reason": "같은 오류가\\n 반복된다"}\n```')
assert p == od.Verdict("stuck", "같은 오류가 반복된다") and p.label == "막힘", p
p = od.parse_verdict('판정은 다음과 같습니다 {참고}.\n```json\n{"verdict": "Continue", "reason": "질문에 답하면 된다"}\n```\n이상입니다.')
assert p == od.Verdict("continue", "질문에 답하면 된다") and p.label == "계속", p
assert od.parse_verdict('{"verdict": "막힘", "reason": "r"}') == od.Verdict("stuck", "r")
assert od.parse_verdict('{"verdict": "done"}') == od.Verdict("done", "(사유 없음)")
for bad, word in [("", "빈 응답"), ("   \n", "빈 응답"), ('{"verdict": "done", "reason"', "JSON 해석 실패"),
                  ("끝났습니다", "JSON 해석 실패"), ('{"reason": "x"}', "JSON 해석 실패"), ('["done"]', "JSON 해석 실패"),
                  ('{"verdict": "maybe", "reason": "x"}', "모르는 판정 값"), ('{"verdict": null}', "모르는 판정 값")]:
    p = od.parse_verdict(bad)
    assert p.verdict == "continue" and p.failed and p.reason.startswith("판정 실패: ") and word in p.reason, (bad, p)
    assert p.label == "판정 실패"
p = od.parse_verdict('{"verdict": "done", "reason": "판정 실패: 라고 모델이 씀"}'); assert p.verdict == "done" and not p.failed
print("ok: parse")

# 4) is_stalled 의 각 규칙
def sends(*texts, auto=True, heads=None):
    return [dict({"at": 100.0 + i, "text": t, "auto": auto}, **({"head": heads[i]} if heads else {}))
            for i, t in enumerate(texts)]
same = "테스트를 다시 실행하고 실패하는 항목을 고쳐 주세요."
assert od.is_stalled([]) == (False, "") and od.is_stalled(None) == (False, "")
ok, why = od.is_stalled(sends(same, same + " 부탁합니다", same))
assert ok and why.startswith("같은 지시 반복"), why
assert od.is_stalled(sends(same, same)) == (False, "")                          # 두 번은 아직
assert od.is_stalled(sends(same, same, same, auto=False)) == (False, "")        # 사람이 보낸 것은 세지 않음
assert od.is_stalled(sends(same, "README 를 갱신하세요", same)) == (False, "")  # 하나라도 다르면 아님
assert od.is_stalled(sends("", "", "")) == (False, "")
mixed = sends(same, same) + [{"at": 50.0, "text": same, "auto": True}, {"at": 200.0, "text": "사람 지시", "auto": False}]
assert od.is_stalled(mixed)[0]                                                  # 순서가 섞여 있어도 at 으로 정렬, 사람 것은 건너뜀
old = sends(same, same, same) + [{"at": 300.0, "text": "전혀 다른 새 작업을 시작하세요", "auto": True}]
assert od.is_stalled(old) == (False, "")                                        # 최근 3회만 봄
diff3 = sends("테스트를 추가하세요", "문서를 갱신하세요", "커밋 메시지를 고치세요")
assert od.is_stalled(diff3) == (False, "")
ok, why = od.is_stalled(diff3, heads=["abc", "abc", "abc"]); assert ok and why.startswith("변경 없이 반복"), why
assert od.is_stalled(diff3, heads=["abc", "abd", "abd"]) == (False, "")
assert od.is_stalled(diff3, heads=["abc", "abc"]) == (False, "")                # 세 시점이 있어야 함
assert od.is_stalled(diff3, heads=["", "", ""]) == (False, "")                  # 읽지 못한 HEAD 는 근거가 아님
assert od.is_stalled(diff3, heads=["x", "abc", "abc", "abc"])[0]
t3 = ["테스트를 추가하세요", "문서를 갱신하세요", "커밋 메시지를 고치세요"]
assert od.is_stalled(sends(*t3, heads=["h1", "h1", "h1"]))[1].startswith("변경 없이 반복")   # 기록의 head 값
assert od.is_stalled(sends(*t3, heads=["h1", "h2", "h1"])) == (False, "")
assert od.is_stalled(sends(same, same, same), heads=["a", "b", "c"])[1].startswith("같은 지시 반복")
head1 = asyncio.run(od.repo_head(repo))
assert head0 and head1 and head0 != head1 and head1.startswith(head0) and "+" in head1   # 커밋 전 변경도 값에 반영
assert asyncio.run(od.repo_head(None)) == "" and asyncio.run(od.repo_head(tmp)) == ""
print("ok: is_stalled")

# 5) judge_progress: 가짜 draft_prompt
calls = []; reply = ['{"verdict": "done", "reason": "끝"}']
async def fake(cfg, agent, row, note, current, cwd, repo_dir=None, drafts=""):
    calls.append((agent.id, note, current, cwd, repo_dir))
    if isinstance(reply[0], Exception): raise reply[0]
    return reply[0]
real_draft = od.draft_prompt; od.draft_prompt = fake
ai = od.AIConfig(provider="claude")
assert asyncio.run(od.judge_progress(ai, row, repo, hist)) == od.Verdict("done", "끝")
assert calls == [("verdict", ht, "", repo, repo)], calls
calls.clear(); reply[0] = "```\n{\"verdict\": \"continue\", \"reason\": \"남음\"}\n```"
assert asyncio.run(od.judge_progress(ai, row, None, [])) == od.Verdict("continue", "남음")
assert calls[0][1] == "" and calls[0][3] == tempfile.gettempdir() and calls[0][4] is None
for bad in ("", "모르겠습니다", od.DraftError("60초 내 응답 없음"), RuntimeError("뜻밖의 오류")):
    reply[0] = bad; got = asyncio.run(od.judge_progress(ai, row, repo, hist))
    assert got.verdict == "continue" and got.failed, (bad, got)
assert "60초 내 응답 없음" not in got.reason and "뜻밖의 오류" in got.reason
calls.clear(); reply[0] = '{"verdict": "done", "reason": "끝"}'
got = asyncio.run(od.judge_progress(ai, row, repo, sends(same, same, same)))
assert got.verdict == "stuck" and got.reason.startswith("같은 지시 반복") and calls == []   # 반복이면 AI 를 부르지 않음
got = asyncio.run(od.judge_progress(od.AIConfig(provider="off"), row, repo, hist))
assert got.verdict == "continue" and got.failed and "꺼져" in got.reason and calls == []
asyncio.run(od.judge_progress(ai, row, repo, hist, agent=od.dataclasses.replace(v, steps=("s",))))
assert calls[-1][0] == "verdict"
print("ok: judge_progress")

# 6) notify_user: 어떤 경우에도 예외 없음, macOS 에서만 osascript 를 인자로 호출
popen_calls = []
real_popen, real_platform = subprocess.Popen, sys.platform
try:
    subprocess.Popen = lambda cmd, **kw: popen_calls.append(cmd)
    sys.platform = "darwin"
    assert od.notify_user('제목 "따옴표"', "본문 \\ 역슬래시\n둘째 줄") is None
    cmd = popen_calls[0]
    assert cmd[0] == "osascript" and cmd[-2:] == ['제목 "따옴표"', "본문 \\ 역슬래시\n둘째 줄"], cmd
    assert not any("따옴표" in c for c in cmd[:-2])                              # 스크립트 본문에 끼워 넣지 않음
    def boom(cmd, **kw): raise OSError("osascript 없음")
    subprocess.Popen = boom
    assert od.notify_user("t", "x") is None
    sys.platform = "linux"; popen_calls.clear(); subprocess.Popen = lambda cmd, **kw: popen_calls.append(cmd)
    assert od.notify_user("t", "x") is None and popen_calls == []
    sys.platform = "darwin"
    assert od.notify_user(None, 123) is None and popen_calls[-1][-2:] == ["None", "123"]
finally:
    subprocess.Popen, sys.platform = real_popen, real_platform
print("ok: notify_user")

# 7) 모달: Ctrl+T 가 판정을 요청하고 상태 줄·표·상세에 남는다. 입력창은 건드리지 않는다
async def flow():
    settings = od.Settings()
    app = od.OrcaDash(settings, ai, config_path=cfg, files=[od.Source(label="file", file=f"{FIX}/sample.json")])
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause(); app.input_source.available = False
        target = app._current_row(); assert target is not None
        loaded = []
        od.load_send_history = lambda d, key, limit=20: loaded.append((d, key)) or hist   # 자동 전송 작업의 함수를 흉내
        scr = od.PromptScreen(target, ai, "/tmp", repo_dir=None, agents=agents, agent_ids=["goal"])
        app._attach_verdict(scr, target, None)
        del od.load_send_history
        assert loaded == [(os.path.dirname(cfg), target.key)] and scr.history == hist and scr.verdict_agent == v
        app.push_screen(scr); await pilot.pause()
        assert "Ctrl+T 진행 판정" in str(scr.query_one("#title").render())
        sl = scr.query_one("#agents", SelectionList)
        assert [sl.get_option_at_index(i).value for i in range(sl.option_count)] == ["goal", "review", "final"]   # 목록에는 없음
        status = lambda: str(scr.query_one("#ai-status").render())
        area = scr.query_one(TextArea); area.insert("쓰던 메모")
        calls.clear(); reply[0] = '{"verdict": "stuck", "reason": "같은 [오류]가 반복된다"}'
        await pilot.press("ctrl+t"); await pilot.pause(0.3)
        assert calls == [("verdict", ht, "", "/tmp", None)], calls
        assert status() == "진행 판정: 막힘 — 같은 [오류]가 반복된다", status()
        assert area.text == "쓰던 메모" and scr.last_draft is None and app.screen is scr
        assert scr.last_verdict == od.Verdict("stuck", "같은 [오류]가 반복된다")
        assert app.verdicts[target.key] == (scr.last_verdict, target.updated_at)
        table = app.query_one(DataTable)
        cell = lambda: table.get_row(target.key)[0].plain
        assert cell().endswith(" · 판정 막힘"), cell()
        assert "판정: 막힘 1" in app.query_one("#status").render().plain
        assert "진행 판정 막힘 — 같은 [오류]가 반복된다" in app.query_one("#detail").render().plain
        # 판정 실패는 창을 막지 않고 실패로 표시
        reply[0] = od.DraftError("claude 실패 — 한도 초과")
        await pilot.press("ctrl+t"); await pilot.pause(0.3)
        assert status() == "진행 판정: 판정 실패 — 판정 실패: claude 실패 — 한도 초과", status()
        assert cell().endswith(" · 판정 판정 실패") and "판정:" not in app.query_one("#status").render().plain
        # 느린 판정은 Esc 로 판정만 중단하고 창은 남는다
        gate = asyncio.Event()
        async def slow(cfg, agent, row, note, current, cwd, repo_dir=None, drafts=""):
            await gate.wait(); return '{"verdict": "done", "reason": "끝"}'
        od.draft_prompt = slow
        await pilot.press("ctrl+t"); await pilot.pause(0.1)
        assert scr.judging and status().startswith("진행 판정 중…"), status()
        await pilot.press("escape"); await pilot.pause(0.2)
        assert app.screen is scr and not scr.judging and status() == "진행 판정 중단됨", status()
        # 초안 작성 중에는 판정을 시작하지 않는다
        await pilot.press("ctrl+g"); await pilot.pause(0.1); assert scr.drafting
        await pilot.press("ctrl+t"); await pilot.pause(0.1); assert not scr.judging
        await pilot.press("escape"); await pilot.pause(0.2)
        od.draft_prompt = fake; reply[0] = '{"verdict": "done", "reason": "모두 끝났다"}'
        await pilot.press("ctrl+t"); await pilot.pause(0.3)
        assert status() == "진행 판정: 달성 — 모두 끝났다" and cell().endswith(" · 판정 달성"), (status(), cell())
        await pilot.press("escape"); await pilot.pause()
        assert not isinstance(app.screen, od.PromptScreen)
        # 에이전트가 더 움직이면(updated_at 변화) 이전 판정으로 흐리게 표시
        target.updated_at = (target.updated_at or 0) + 5000; app._render_table(); await pilot.pause()
        assert cell().endswith(" · 판정 달성(이전)"), cell()
        # 자동 전송 루프용: alert 이면 달성·막힘만 알림
        notified = []; real_notify = od.notify_user; od.notify_user = lambda t, x: notified.append((t, x))
        app.set_verdict(target, od.Verdict("continue", "남음"), alert=True)
        app.set_verdict(target, od.Verdict("continue", "판정 실패: x"), alert=True)
        app.set_verdict(target, od.Verdict("stuck", "막혔다"))
        assert notified == []
        app.set_verdict(target, od.Verdict("stuck", "막혔다"), alert=True)
        assert notified == [("orca-dash · 막힘", f"{target.repo}/{target.worktree}: 막혔다")], notified
        od.notify_user = real_notify
        # AI 가 꺼져 있으면 Ctrl+T 는 동작하지 않고 안내에도 없다
        off = od.PromptScreen(target, od.AIConfig(provider="off"), "/tmp")
        app.push_screen(off); await pilot.pause(); calls.clear()
        assert "Ctrl+T" not in str(off.query_one("#title").render())
        await pilot.press("ctrl+t"); await pilot.pause(0.2)
        assert calls == [] and not off.judging
        await pilot.press("escape"); await pilot.pause()
        # 옵션의 에이전트 탭: 판정 에이전트의 생각의 흐름을 고칠 수 있지만 작성 에이전트로는 고를 수 없다
        sscr = od.SettingsScreen(settings, cfg, [], file_mode=True)
        app.push_screen(sscr); await pilot.pause()
        pick = sscr.query_one("#agent-pick", Select)
        assert "verdict" in sscr.steps and "프롬프트 초안용이 아님" in sscr._agent_desc(v)
        assert "verdict" not in str(sscr.query_one("#form .hint").render())
        sscr.steps["verdict"] = ["한 단계만"]
        assert sscr._collect_steps() == {"verdict": ["한 단계만"]}
        sscr.query_one("#ai_agents").value = "verdict"; await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert "모르는 작성 에이전트: verdict" in str(sscr.query_one("#form-error").render())
        app.exit()
asyncio.run(flow())
od.draft_prompt = real_draft
print("ok: modal")
print("ALL OK")
