"""생각의 흐름: 파싱·덮어쓰기·시스템 프롬프트·설정·에이전트 탭 헤드리스 테스트."""
import asyncio, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import Button, Input, Label, Select, Static, TabbedContent

tmp = tempfile.mkdtemp()
cfg = os.path.join(tmp, "cfg", "config.json")
adir = od.agents_dir(cfg); os.makedirs(adir)

# 1) md 파일의 step: 줄, 설정 덮어쓰기, 시스템 프롬프트
open(os.path.join(adir, "tests.md"), "w").write(
    "---\nname: 테스트 작성\nstep: 바뀐 함수를 본다\nstep: 빠진 테스트를 찾는다\n---\n역할: 테스트 작성자.\n")
agents, errs = od.load_agents(cfg)
ids = {a.id: a for a in agents}
assert errs == [] and ids["tests"].steps == ("바뀐 함수를 본다", "빠진 테스트를 찾는다")
assert len(ids["goal"].steps) == 4 and len(ids["review"].steps) == 4
agents2, _ = od.load_agents(cfg, {"goal": ["단계X"], "tests": [], "nope": ["x"]})
ids2 = {a.id: a for a in agents2}
assert ids2["goal"].steps == ("단계X",) and ids2["tests"].steps == () and ids2["review"].steps == ids["review"].steps
sp = od.draft_system_prompt(ids2["goal"])
assert "[역할] (character: goal)" in sp and "리드" in sp and "think_steps" in sp and "단계X" not in sp, sp
spec = json.loads(od.agent_json(ids2["goal"]))
assert spec == {"agent": {"character": "goal", "think_steps": {"1": "단계X"}}}, spec
spec = json.loads(od.agent_json(ids["review"]))
assert list(spec["agent"]["think_steps"]) == ["1", "2", "3", "4"] and spec["agent"]["character"] == "review"
assert json.loads(od.agent_json(ids2["tests"]))["agent"]["think_steps"] == {}
row = od.Row(key="k", source="local", pane_key=None, host="h", path="", repo="r", worktree="w", branch="b",
             agent_type="claude", state="running", main_state=None, wait="", started_at=None, updated_at=None,
             tool="", summary="", detail="", unread=False)
req = asyncio.run(od.build_draft_request(ids2["goal"], row, "메모", "", False, None))
assert "[사용자 메모]" not in req and "메모" not in req.split("[에이전트]")[1], req   # goal 은 메모를 받지 않음
block = req.split("[에이전트]\n", 1)[1]
assert json.loads(block) == {"agent": {"character": "goal", "think_steps": {"1": "단계X"}}}, block
req = asyncio.run(od.build_draft_request(ids2["review"], row, "메모", "기존", False, None))
assert req.index("[에이전트 상황]") < req.index("[에이전트]") < req.index("[사용자 메모]\n메모") < req.index("[기존 초안]")
# md 의 memo: off, 잘못된 값, 라벨 표시
open(os.path.join(adir, "quiet.md"), "w").write("---\nname: 조용\nmemo: off\n---\n역할: x\n")
open(os.path.join(adir, "bad.md"), "w").write("---\nname: 나쁨\nmemo: maybe\n---\n역할: x\n")
ag3, errs3 = od.load_agents(cfg); id3 = {a.id: a for a in ag3}
assert not id3["quiet"].memo and id3["tests"].memo and not id3["goal"].memo and id3["review"].memo
assert len(errs3) == 1 and "memo" in errs3[0] and "bad" not in id3, errs3
assert id3["quiet"].label.endswith("(메모 안 받음)") and "메모" not in id3["tests"].label
os.remove(os.path.join(adir, "bad.md"))
print("ok: steps parsing/override/prompt")

# 2) Settings.agent_steps 검증·저장
s = od.Settings(); s.agent_steps = {"goal": ["a", " ", "b"], "": ["x"], "review": "한 줄"}
assert s.validate() == [] and s.agent_steps == {"goal": ["a", "b"], "review": ["한 줄"]}, s.agent_steps
s.save(cfg); assert od.Settings.load(cfg).agent_steps == {"goal": ["a", "b"], "review": ["한 줄"]}
s.agent_steps = ["list"]; assert any("agent_steps" in e for e in s.validate()) and s.agent_steps == {}
print("ok: settings")

# 3) 에이전트 탭 헤드리스
ai = od.AIConfig(provider="claude")
async def flow():
    settings = od.Settings.load(cfg)   # goal: [a,b], review: [한 줄]
    app = od.OrcaDash(settings, ai, config_path=cfg, files=[od.Source(label="file", file="/dev/null")])
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(); app.input_source.available = False
        scr = od.SettingsScreen(settings, cfg, [], file_mode=True)
        app.push_screen(scr); await pilot.pause()
        scr.query_one(TabbedContent).active = "tab-agents"; await pilot.pause()
        assert scr.cur_agent == "goal"
        inputs = lambda: [i.value for i in scr.query(".step-input")]
        assert inputs() == ["a", "b"], inputs()
        # + 추가 → 빈 입력이 포커스
        await pilot.click("#step-add"); await pilot.pause()
        assert inputs() == ["a", "b", ""] and isinstance(app.focused, Input) and app.focused.value == ""
        app.focused.insert("c", 0); await pilot.pause()
        # - 로 첫 단계 삭제
        await pilot.click("#step-del-0"); await pilot.pause()
        assert inputs() == ["b", "c"], inputs()
        # 에이전트 바꾸면 보관되고, 다른 에이전트의 단계가 보임
        scr.query_one("#agent-pick", Select).value = "review"; await pilot.pause()
        assert scr.cur_agent == "review" and inputs() == ["한 줄"], inputs()
        assert "리뷰어" in str(scr.query_one("#agent-role", Static).render())
        # 기본값으로 → 내장 4단계
        await pilot.click("#step-reset"); await pilot.pause()
        assert len(inputs()) == 4 and inputs() == list(od.BUILTIN_AGENTS[1].steps)
        # 모두 삭제 → '단계 없음' 안내
        for _ in range(4):
            await pilot.click("#step-del-0"); await pilot.pause()
        assert inputs() == [] and scr.query("#steps-empty")
        # tests(md 기본 2단계) 는 건드리지 않음
        scr.query_one("#agent-pick", Select).value = "tests"; await pilot.pause()
        assert inputs() == ["바뀐 함수를 본다", "빠진 테스트를 찾는다"]
        new = scr._collect(); assert new.validate() == []
        # goal 은 기본과 다르니 저장, review 는 빈 목록(단계 없음)으로 저장, tests 는 기본과 같아 생략
        assert new.agent_steps == {"goal": ["b", "c"], "review": []}, new.agent_steps
        # 저장 흐름: Enter → dismiss 결과
        got = []
        scr2 = od.SettingsScreen(settings, cfg, [], file_mode=True)
        app.pop_screen(); await pilot.pause()
        app.push_screen(scr2, lambda r: got.append(r)); await pilot.pause()
        scr2.query_one(TabbedContent).active = "tab-agents"; await pilot.pause()
        await pilot.click("#step-add"); await pilot.pause()
        app.focused.insert("새 단계", 0); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert got and got[0].agent_steps["goal"] == ["a", "b", "새 단계"], got
        # 프롬프트 모달이 설정의 단계를 반영한 에이전트를 받는지
        ag, _ = od.load_agents(cfg, got[0].agent_steps)
        assert {a.id: a for a in ag}["goal"].steps == ("a", "b", "새 단계")
        app.exit()
asyncio.run(flow())
print("ok: agents tab")
print("ALL OK")
