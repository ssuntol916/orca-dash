"""작성 에이전트: 파일 파싱·레지스트리·컨텍스트 제공자·프롬프트 모달 헤드리스 테스트."""
import asyncio, os, subprocess, sys, tempfile, textwrap
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import Input, Select, TextArea

tmp = tempfile.mkdtemp()
cfg = os.path.join(tmp, "cfg", "config.json")
adir = od.agents_dir(cfg)
os.makedirs(adir)

# 1) 레지스트리: 내장만
agents, errs = od.load_agents(cfg)
assert [a.id for a in agents] == ["goal", "review", "final"] and errs == [], (agents, errs)
assert od.pick_agent(agents, "nope").id == "goal" and od.pick_agent(agents, "review").id == "review"

# 2) 사용자 정의 추가 + 내장 덮어쓰기 + 잘못된 파일 건너뜀
open(os.path.join(adir, "tests.md"), "w").write(textwrap.dedent("""\
    ---
    name: 테스트 작성
    description: 변경분에 맞는 테스트
    context: diff, log
    ---
    역할: 테스트 작성자.
    - 변경분에 대한 테스트를 쓰게 한다.
    """))
open(os.path.join(adir, "goal.md"), "w").write("---\nname: 내 목표\n---\n내 지시문\n")
open(os.path.join(adir, "bad ctx.md"), "w").write("---\nname: x\n---\nbody\n")        # id 형식 오류
open(os.path.join(adir, "noname.md"), "w").write("---\ndescription: x\n---\nbody\n")   # name 없음
open(os.path.join(adir, "badctx.md"), "w").write("---\nname: x\ncontext: diff, nope\n---\nbody\n")
open(os.path.join(adir, "empty.md"), "w").write("---\nname: x\n---\n\n")
open(os.path.join(adir, "plain.md"), "w").write("frontmatter 없음\n")  # name 없음 → 오류
agents, errs = od.load_agents(cfg)
ids = {a.id: a for a in agents}
assert set(ids) == {"goal", "review", "final", "tests"}, ids
assert ids["goal"].name == "내 목표" and not ids["goal"].builtin and ids["goal"].instructions.strip() == "내 지시문"
assert ids["tests"].context == ("diff", "log") and ids["tests"].description == "변경분에 맞는 테스트"
assert len(errs) == 5, errs
for e in errs: print("  skip:", e)
print("ok: registry")

# 3) 컨텍스트 제공자: 임시 git 저장소
repo = os.path.join(tmp, "repo"); os.makedirs(repo)
def git(*a): subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True)
git("init", "-q", "-b", "main"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
open(os.path.join(repo, "README.md"), "w").write("# 프로젝트\n\n설명\n")
open(os.path.join(repo, "a.py"), "w").write("x = 1\n")
git("add", "."); git("commit", "-q", "-m", "init")
git("checkout", "-q", "-b", "feat")
open(os.path.join(repo, "a.py"), "w").write("x = 2\n"); git("commit", "-q", "-am", "change a")
open(os.path.join(repo, "b.py"), "w").write("y = 1\n")            # 추적 안 됨
open(os.path.join(repo, "a.py"), "w").write("x = 3\n")            # 커밋 전 변경

row = od.Row(key="k", source="local", pane_key="t:1", host="local", path=repo, repo="repo", worktree="feat",
             branch="feat", agent_type="claude", state="waiting_input", main_state=None, wait="질문",
             started_at=None, updated_at=None, tool="", summary="", detail="", unread=False,
             prompt="a.py 를 고쳐라", last_message="고쳤습니다. 더 할까요?")

async def req(agent_id, include=True, repo_dir=repo):
    # goal 은 위에서 사용자 파일이 덮었으므로 제공자 검사는 내장 정의로 한다
    agent = od.pick_agent(od.BUILTIN_AGENTS if agent_id == "goal" else agents, agent_id)
    return await od.build_draft_request(agent, row, "메모", "", include, repo_dir)

r = asyncio.run(req("review"))
assert "[변경분]" in r and "x = 3" in r and "추적 안 된 파일: b.py" in r, r
assert "(main 대비 이 브랜치의 커밋된 변경)" in r and "x = 2" in r, r
assert "[최근 커밋]" in r and "change a" in r and "[원래 지시]" in r and "[마지막 응답]" in r, r
assert "[프로젝트 목표]" not in r
r = asyncio.run(req("goal"))
assert "[프로젝트 목표] (README.md 앞부분 (목표 문서 없음))" in r and "# 프로젝트" in r and "[변경분]" not in r, r
os.makedirs(os.path.join(repo, "docs")); open(os.path.join(repo, "docs", "GOAL.md"), "w").write("목표: 빠르게\n")
r = asyncio.run(req("goal"))
assert "[프로젝트 목표] (docs/GOAL.md)" in r and "목표: 빠르게" in r, r
r = asyncio.run(req("review", repo_dir=None))
assert "원격 호스트라 로컬에서 읽을 수 없어 생략" in r and "[원래 지시]" in r, r
r = asyncio.run(req("review", include=False))
assert "[변경분]" not in r and "[원래 지시]" not in r and "[사용자 메모]" in r, r
sysmsg = od.draft_system_prompt(ids["review"])
assert sysmsg.startswith(od.DRAFT_SYSTEM) and "[역할]" in sysmsg and "리뷰어" in sysmsg
print("ok: context providers")

# 4) Settings: ai_agents 저장·검증·CLI·이전 형식 호환
s = od.Settings(); s.ai_agents = ""; assert s.validate() == [] and s.ai_agents == ["goal"]
s.ai_agents = "tests goal tests"; assert s.validate() == [] and s.ai_agents == ["tests", "goal"]
s.save(cfg); assert od.Settings.load(cfg).ai_agents == ["tests", "goal"]
import json; d = json.load(open(cfg)); del d["ai_agents"]; d["ai_agent"] = "review"; json.dump(d, open(cfg, "w"))
assert od.Settings.load(cfg).ai_agents == ["review"]
s.save(cfg)
import argparse
ns = argparse.Namespace(interval=None, orca=None, env=None, host=None, ssh=None, ai=None, ai_model=None,
                        ai_timeout=None, ai_agent=["review", "goal"], no_local=False, ai_context=None)
assert s.apply_args(ns) == ["ai_agents"] and s.ai_agents == ["review", "goal"]
assert [a.id for a in od.pick_agents(agents, ["nope", "review", "goal", "review"])] == ["review", "goal"]
assert [a.id for a in od.pick_agents(agents, ["nope"])] == ["goal"]
print("ok: settings")

# 5) 독립 실행: 각자 같은 메모로 쓰고 머리말로 묶음, 다듬기는 머리말로 나눠 자기 부분만
calls = []
async def fake_draft(cfg, agent, row, note, current, cwd, repo_dir=None):
    calls.append((agent.id, note, current, repo_dir)); return f"초안({agent.id})"
od.draft_prompt = fake_draft
ai = od.AIConfig(provider="claude")
steps = []
two = od.pick_agents(od.BUILTIN_AGENTS, ["goal", "review"])
out = asyncio.run(od.draft_each(ai, two, row, "메모", {}, "/tmp", repo, on_step=lambda i, a, c: steps.append((i, a.id, c))))
assert out == "[목표 지향]\n초안(goal)\n\n[문제 발견]\n초안(review)", out
assert steps == [(0, "goal", "초안(goal)"), (1, "review", out)], steps
assert calls == [("goal", "메모", "", repo), ("review", "메모", "", repo)], calls
assert asyncio.run(od.draft_each(ai, two[:1], row, "", {}, "/tmp", None)) == "초안(goal)"   # 하나면 머리말 없음
parts = od.split_draft(out + "\n수정 추가", two)
assert parts == {"goal": "초안(goal)", "review": "초안(review)\n수정 추가"}, parts
assert od.split_draft("머리말 없는 글", two) == {"goal": "머리말 없는 글", "review": "머리말 없는 글"}
calls.clear()
asyncio.run(od.draft_each(ai, two, row, "메모", parts, "/tmp", None))
assert [c[2] for c in calls] == ["초안(goal)", "초안(review)\n수정 추가"], calls
# 중간 단계 실패: 예외가 그대로 전파되고 뒤 단계는 실행되지 않음
async def failing(cfg, agent, row, note, current, cwd, repo_dir=None):
    if agent.id == "goal": raise od.DraftError("실패")
    return "x"
od.draft_prompt = failing; steps.clear()
try:
    asyncio.run(od.draft_each(ai, od.pick_agents(agents, ["tests", "goal", "review"]), row, "", {}, "/tmp", None,
                              on_step=lambda i, a, c: steps.append(a.id)))
    raise SystemExit("should raise")
except od.DraftError as e:
    assert str(e) == "실패" and steps == ["tests"], steps
od.draft_prompt = fake_draft
print("ok: independent drafts")

# 6) 프롬프트 모달 헤드리스: 체크 순서가 실행 순서, Ctrl+G 가 체인으로 호출, 중간 결과 표시
from textual.widgets import SelectionList, Label
class T(od.OrcaDash):
    pass

async def modal_flow():
    settings = od.Settings.load(cfg)   # ai_agents=["tests","goal"]
    app = T(settings, ai, config_path=cfg, files=[od.Source(label="file", file="/dev/null")])
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.input_source.available = False
        scr = od.PromptScreen(row, ai, repo, repo_dir=repo, agents=agents, agent_ids=settings.ai_agents,
                              agent_errors=errs)
        app.push_screen(scr)
        await pilot.pause()
        sl = scr.query_one("#agents", SelectionList)
        assert scr.agent_ids == ["tests", "goal"] and set(sl.selected) == {"tests", "goal"}, (scr.agent_ids, sl.selected)
        assert "실행 순서: 테스트 작성 → 내 목표" in str(scr.query_one("#agent-order", Label).render())
        assert "에이전트 파일 오류 5건" in str(scr.query_one("#ai-status").render())
        calls.clear()
        scr.query_one(TextArea).insert("메모1")
        await pilot.press("ctrl+g"); await pilot.pause(0.3)
        assert [c[0] for c in calls] == ["tests", "goal"] and calls[1][2] == "", calls
        assert scr.query_one(TextArea).text == "[테스트 작성]\n초안(tests)\n\n[내 목표]\n초안(goal)"
        assert "테스트 작성 → 내 목표" in str(scr.query_one("#ai-status").render())
        # 토글: tests 해제 → review 추가 → 순서 goal, review
        sl.deselect("tests"); await pilot.pause()
        sl.select("review"); await pilot.pause()
        assert scr.agent_ids == ["goal", "review"], scr.agent_ids
        assert "실행 순서: 내 목표 → 문제 발견" in str(scr.query_one("#agent-order", Label).render())
        calls.clear()   # 초안이 들어 있으니 다듬기: goal 은 자기 부분, review 는 새로(기존 부분 없음)
        await pilot.press("ctrl+g"); await pilot.pause(0.3)
        assert [(c[0], c[2]) for c in calls] == [("goal", "초안(goal)"), ("review", "")], calls
        calls.clear()
        scr.query_one(TextArea).load_text("새 메모")
        await pilot.press("ctrl+g"); await pilot.pause(0.3)
        assert [(c[0], c[1], c[2]) for c in calls] == [("goal", "새 메모", ""), ("review", "새 메모", "")], calls
        # 모두 해제하면 첫 에이전트 하나
        sl.deselect_all(); await pilot.pause()
        assert [a.id for a in scr.chain] == ["goal"]
        await pilot.press("escape"); await pilot.pause()
        # 옵션 화면: Input 에 순서대로, 모르는 id 는 저장 거절
        sscr = od.SettingsScreen(settings, cfg, [], file_mode=True)
        app.push_screen(sscr); await pilot.pause()
        inp = sscr.query_one("#ai_agents", Input)
        assert inp.value == "tests goal", inp.value
        inp.value = "review nope"; await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert "모르는 작성 에이전트: nope" in str(sscr.query_one("#form-error").render())
        assert app.screen is sscr
        inp.value = "review goal"; await pilot.pause()
        new = sscr._collect(); assert new.validate() == [] and new.ai_agents == ["review", "goal"]
        await pilot.press("escape"); await pilot.pause()
        app.exit()
asyncio.run(modal_flow())
print("ok: modal + settings screen")
print("ALL OK")
