"""최종 결정 에이전트: 등록·파싱·요청 본문·실행 순서·모달 헤드리스."""
import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import Label, SelectionList, TextArea

tmp = tempfile.mkdtemp(); cfg = os.path.join(tmp, "cfg", "config.json")
adir = od.agents_dir(cfg); os.makedirs(adir)
open(os.path.join(adir, "judge.md"), "w").write("---\nname: 심판\nfinal: on\nmemo: off\n---\n역할: 고른다.\n")
open(os.path.join(adir, "bad.md"), "w").write("---\nname: 나쁨\nfinal: maybe\n---\n역할: x\n")
agents, errs = od.load_agents(cfg); ids = {a.id: a for a in agents}
assert ids["final"].final and ids["final"].memo and not ids["goal"].final and not ids["review"].final
assert "(다른 초안을 받아 하나로)" in ids["final"].label and "(다른 초안을 받아 하나로)" not in ids["review"].label
assert ids["judge"].final and not ids["judge"].memo and ids["judge"].label.endswith("(다른 초안을 받아 하나로 · 메모 안 받음)")
assert len(errs) == 1 and "final 는 on 또는 off" in errs[0] and "bad" not in ids, errs
assert [a.id for a in od.BUILTIN_AGENTS] == ["goal", "review", "final"]
w, d = od.split_run(od.pick_agents(agents, ["final", "goal", "judge", "review"]))
assert [a.id for a in w] == ["goal", "review"] and d.id == "judge"          # 결정 에이전트는 마지막 체크한 것 하나
assert [a.id for a in od.run_order(od.pick_agents(agents, ["final", "goal"]))] == ["goal", "final"]
assert od.split_run([ids["goal"]]) == ([ids["goal"]], None)
print("ok: registry")

row = od.Row(key="k", source="local", pane_key=None, host="h", path="", repo="r", worktree="w", branch="b",
             agent_type="claude", state="waiting_input", main_state=None, wait="질문", started_at=None,
             updated_at=None, tool="", summary="", detail="", unread=False)
r = asyncio.run(od.build_draft_request(ids["final"], row, "메모", "", False, None, drafts="[목표 지향]\nA\n\n[문제 발견]\nB"))
assert r.index("[에이전트]") < r.index("[에이전트 초안]\n[목표 지향]\nA") < r.index("[사용자 메모]\n메모") and "[기존 초안]" not in r, r
r = asyncio.run(od.build_draft_request(ids["final"], row, "메모", "", False, None))
assert "[에이전트 초안]" not in r, r          # 단독 실행: 받을 초안이 없으면 절 없음
r = asyncio.run(od.build_draft_request(ids["final"], row, "메모", "기존", False, None, drafts="X"))
assert "[에이전트 초안]" not in r and "[기존 초안]\n기존" in r, r          # 다듬기에는 초안 절 없음
r = asyncio.run(od.build_draft_request(ids["review"], row, "메모", "", False, None, drafts="X"))
assert "[에이전트 초안]" not in r
assert "[에이전트 초안]" in od.DRAFT_SYSTEM and "편집자" in od.draft_system_prompt(ids["final"])
print("ok: request")

calls, steps = [], []
async def fake(cfg, agent, row, note, current, cwd, repo_dir=None, drafts=""):
    calls.append((agent.id, note, current, drafts)); return f"초안({agent.id})"
od.draft_prompt = fake
ai = od.AIConfig(provider="claude")
three = od.pick_agents(agents, ["final", "goal", "review"])
out = asyncio.run(od.draft_each(ai, three, row, "메모", {}, "/tmp", None, on_step=lambda i, a, c: steps.append((i, a.id, c))))
assert out == "초안(final)", out
assert [c[0] for c in calls] == ["goal", "review", "final"], calls
assert calls[2][3] == "[목표 지향]\n초안(goal)\n\n[문제 발견]\n초안(review)" and calls[0][3] == "" and calls[2][2] == ""
assert steps == [(0, "goal", "초안(goal)"), (1, "review", "[목표 지향]\n초안(goal)\n\n[문제 발견]\n초안(review)"),
                 (2, "final", "초안(final)")], steps
calls.clear()
asyncio.run(od.draft_each(ai, od.pick_agents(agents, ["goal", "final"]), row, "", {}, "/tmp", None))
assert calls[1][3] == "[목표 지향]\n초안(goal)", calls          # 하나뿐이어도 결정 에이전트에게는 머리말
calls.clear()
assert asyncio.run(od.draft_each(ai, [ids["final"]], row, "m", {}, "/tmp", None)) == "초안(final)" and calls[0][3] == ""
calls.clear()
asyncio.run(od.draft_each(ai, [ids["final"]], row, "m", {"final": "이전 결정"}, "/tmp", None))
assert calls == [("final", "m", "이전 결정", "")], calls
calls.clear()   # 작성 에이전트 없이 밖에서 받은 묶음으로 결정
asyncio.run(od.draft_each(ai, [ids["final"]], row, "m", {}, "/tmp", None, drafts="[목표 지향]\nA"))
assert calls == [("final", "m", "", "[목표 지향]\nA")], calls
assert od.has_section_headers("[목표 지향]\nA", [ids["goal"]]) and not od.has_section_headers("[목표 지향] x\nA", [ids["goal"]])
assert not od.has_section_headers("[최종 결정]\nA", [ids["goal"], ids["review"]])
# 작성 에이전트 실패 → 결정 에이전트는 돌지 않고 예외 전파
async def failing(cfg, agent, row, note, current, cwd, repo_dir=None, drafts=""):
    calls.append((agent.id, note, current, drafts))
    if agent.id == "review": raise od.DraftError("실패")
    return f"초안({agent.id})"
od.draft_prompt = failing; calls.clear(); steps.clear()
try:
    asyncio.run(od.draft_each(ai, three, row, "", {}, "/tmp", None, on_step=lambda i, a, c: steps.append(a.id)))
    raise SystemExit("should raise")
except od.DraftError:
    assert [c[0] for c in calls] == ["goal", "review"] and steps == ["goal"], (calls, steps)
od.draft_prompt = fake
# 상황 전달을 꺼도 [에이전트 초안]·[사용자 메모]는 들어감
r = asyncio.run(od.build_draft_request(ids["final"], row, "메모", "", False, None, drafts="[목표 지향]\nA"))
assert "[에이전트 초안]\n[목표 지향]\nA" in r and "[원래 지시]" not in r, r
print("ok: draft_each")

async def flow():
    settings = od.Settings(); settings.ai_agents = ["goal", "review", "final"]
    app = od.OrcaDash(settings, ai, config_path=cfg, files=[od.Source(label="file", file="/dev/null")])
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(); app.input_source.available = False
        scr = od.PromptScreen(row, ai, "/tmp", repo_dir=None, agents=agents, agent_ids=settings.ai_agents, agent_errors=errs)
        app.push_screen(scr); await pilot.pause()
        order = lambda: str(scr.query_one("#agent-order", Label).render())
        assert order() == "실행 순서: 목표 지향(메모 안 받음) → 문제 발견 ⇒ 최종 결정  (각자 쓴 초안을 최종 결정이 하나로 정함)", order()
        calls.clear()
        scr.query_one(TextArea).insert("메모1")
        await pilot.press("ctrl+g"); await pilot.pause(0.3)
        assert [c[0] for c in calls] == ["goal", "review", "final"] and calls[2][1] == "메모1", calls
        assert scr.query_one(TextArea).text == "초안(final)"
        status = str(scr.query_one("#ai-status").render())
        assert "목표 지향 → 문제 발견 ⇒ 최종 결정" in status, status
        calls.clear()   # 다듬기: 결정 에이전트만, 기존 결정을 current 로
        await pilot.press("ctrl+g"); await pilot.pause(0.3)
        assert calls == [("final", "메모1", "초안(final)", "")], calls
        assert scr.query_one(TextArea).text == "초안(final)"
        # 결정 전에 중단된 것처럼 머리말 묶음이 남아 있으면(사용자가 고친 것 포함) 결정 에이전트가 그것을 [에이전트 초안]으로 받음
        bundle = "[목표 지향]\n초안(goal) 고침\n\n[문제 발견]\n초안(review)"
        scr.query_one(TextArea).load_text(bundle); scr.last_draft = bundle
        calls.clear()
        await pilot.press("ctrl+g"); await pilot.pause(0.3)
        assert calls == [("final", "메모1", "", bundle)], calls
        assert scr.query_one(TextArea).text == "초안(final)"
        # 작성 에이전트가 중간에 실패하면 끝난 부분이 남고 last_draft 로 기억되어 다음 Ctrl+G 가 메모로 오해하지 않음
        od.draft_prompt = failing
        scr.query_one(TextArea).load_text("새 메모2"); calls.clear()
        await pilot.press("ctrl+g"); await pilot.pause(0.3)
        assert [c[0] for c in calls] == ["goal", "review"] and scr.query_one(TextArea).text == "초안(goal)", calls
        assert scr.last_draft == "초안(goal)" and scr._looks_like_draft("초안(goal)")
        od.draft_prompt = fake; calls.clear()
        await pilot.press("ctrl+g"); await pilot.pause(0.3)   # 머리말 없는 한 조각 → 결정 에이전트가 다듬기
        assert calls == [("final", "새 메모2", "초안(goal)", "")], calls
        sl = scr.query_one("#agents", SelectionList)
        sl.deselect("goal"); sl.deselect("review"); await pilot.pause()
        assert order() == "실행 순서: 최종 결정  (받을 초안이 없어 직접 작성)", order()
        sl.select("judge"); sl.select("goal"); await pilot.pause()   # 결정 에이전트 둘이면 마지막 체크한 심판(메모 off)
        assert order() == "실행 순서: 목표 지향(메모 안 받음) ⇒ 심판(메모 안 받음)  (각자 쓴 초안을 심판이 하나로 정함)", order()
        sl.deselect("judge"); sl.deselect("goal"); await pilot.pause()
        sl.deselect("final"); sl.select("review"); sl.select("goal"); await pilot.pause()
        assert order() == "실행 순서: 문제 발견 → 목표 지향(메모 안 받음)  (각자 독립적으로 쓰고 이 순서로 묶음)", order()
        assert [a.id for a in scr.chain] == ["review", "goal"]
        sscr = od.SettingsScreen(settings, cfg, [], file_mode=True)
        assert "최종 결정: 다른 에이전트들의 초안을 받아 하나로 정함" in sscr._agent_desc(ids["final"])
        assert "최종 결정:" not in sscr._agent_desc(ids["goal"])
        app.exit()
asyncio.run(flow())
print("ok: modal")
print("ALL OK")
