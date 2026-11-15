"""백그라운드 제안: 저장소 무효화·대상 행 고르기·한 번에 하나씩 도는 큐·모달 미리 채움과 다듬기·실패 재시도 상한."""
import asyncio, dataclasses, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import Checkbox, DataTable, TextArea

tmp = tempfile.mkdtemp(); cfg = os.path.join(tmp, "cfg", "config.json")


def mkrow(key, state, updated=1000.0, pane="t:l", **kw):
    return od.Row(key=key, source="local", pane_key=pane, host="h", path=kw.pop("path", ""), repo="r", worktree=key, branch="b",
                  agent_type="claude", state=state, main_state=None, wait=kw.pop("wait", ""), started_at=None,
                  updated_at=updated, tool="", summary="", detail=f"상세 {key}", unread=False, **kw)


# 1) 저장소: get/put/invalidate, updated_at 이 바뀌면 무효, 보냄 표시
st = od.ProposalStore()
row = mkrow("a", "waiting")
assert st.get("a") is None and st.valid(row) is None and od.needs_proposal(row, st)
p = od.Proposal("a", "본문", ["goal"], 1.0, 1000.0, "ready")
assert p.error == "" and p.attempts == 1 and od.Proposal("a", "t", [], 1.0, None).status == "ready"
st.put(p)
assert st.get("a") is p and st.valid(row) is p and st.current(row) is p and not od.needs_proposal(row, st)
moved = mkrow("a", "waiting", updated=2000.0)
assert st.valid(moved) is None and st.current(moved) is None and od.needs_proposal(moved, st)   # 행이 바뀌면 무효
assert st.sync([row, mkrow("zz", "waiting")]) == [] and st.get("a") is p
assert st.sync([moved]) == ["a"] and st.get("a") is None
st.put(p); assert st.sync([]) == [] and st.get("a") is p          # 조회에서 잠깐 빠진 행의 제안은 남긴다
st.invalidate("a"); st.invalidate("a"); assert st.get("a") is None
st.put(od.Proposal("a", "  ", ["goal"], 1.0, 1000.0, "ready")); assert st.valid(row) is None   # 빈 본문은 쓸 수 없음
st.put(od.Proposal("a", "", ["goal"], 1.0, 1000.0, "drafting"))
assert st.valid(row) is None and not od.needs_proposal(row, st)   # 작성 중이면 다시 넣지 않음
st.put(od.Proposal("a", "", ["goal"], 1.0, 1000.0, "error", error="x", attempts=1)); assert od.needs_proposal(row, st)
st.get("a").attempts = od.PROPOSAL_MAX_ATTEMPTS; assert not od.needs_proposal(row, st) and st.valid(row) is None
st.invalidate("a"); st.mark_sent(row)
assert st.get("a").status == "sent" and st.valid(row) is None and not od.needs_proposal(row, st)
assert od.needs_proposal(moved, st)                               # 보낸 뒤 행이 갱신되면 다시 대상
# 대상 상태: 사람 개입이 필요한 것만, 에이전트 터미널이 있는 행만
empty = od.ProposalStore()
want = {s: od.needs_proposal(mkrow("x", s), empty) for s in
        ["blocked", "waiting", "permission", "waiting_input", "waiting_permission", "working", "done", "idle", None]}
assert want == {"blocked": True, "waiting": True, "permission": True, "waiting_input": True,
                "waiting_permission": True, "working": False, "done": False, "idle": False, None: False}, want
assert not od.needs_proposal(mkrow("x", "waiting", pane=None), empty)
print("ok: store")

# 2) 설정: auto_draft 기본 꺼짐, 저장·읽기, 타입 맞춤
s = od.Settings(); assert s.auto_draft is False and "auto_draft" in od.Settings.FIELDS
s.auto_draft = 1; assert s.validate() == [] and s.auto_draft is True
s.save(cfg); assert od.Settings.load(cfg).auto_draft is True
s.auto_draft = False; s.save(cfg)
print("ok: settings")

# 3) 앱: 큐·표 표시·모달·재시도. 조회와 초안 작성, 전송은 가짜로 바꾼다.
ROWS: list = []
calls: list = []          # (행 키, 에이전트 id 들, 메모, currents, cwd, repo_dir)
fail_keys: set = set()
state = {"active": 0, "max": 0, "delay": 0.05, "sent": []}
async def fake_fetch(src): return list(ROWS), None
async def fake_each(cfg_, agents, row, note, currents, cwd, repo_dir=None, on_step=None, drafts=""):
    calls.append((row.key, [a.id for a in agents], note, dict(currents), cwd, repo_dir))
    state["active"] += 1; state["max"] = max(state["max"], state["active"])
    try:
        await asyncio.sleep(state["delay"])
    finally:
        state["active"] -= 1
    if row.key in fail_keys:
        raise od.DraftError("가짜 실패")
    n = sum(1 for c in calls if c[0] == row.key)
    text = f"제안({row.key}#{n})" if not currents else f"다듬음({row.key})"
    if on_step:
        on_step(len(agents) - 1, agents[-1], text)
    return text
async def fake_send(src, pane_key, text):
    state["sent"].append(text); return "전송됨"
od.fetch = fake_fetch; od.draft_each = fake_each; od.send_prompt = fake_send
ai = od.AIConfig(provider="claude")
keys_called = lambda: [c[0] for c in calls]


def cell(app, key):
    return str(app.query_one(DataTable).get_cell(key, "state"))


async def settle(pilot, app, limit=3.0):
    """제안 워커가 큐를 다 비울 때까지 기다린다."""
    for _ in range(int(limit / 0.02)):
        await pilot.pause(0.02)
        w = app._proposal_worker
        if not app._proposal_queue and not (w and w.is_running):
            return
    raise AssertionError("제안 워커가 끝나지 않음")


async def flow_off():
    """auto_draft 가 꺼져 있거나 AI 가 꺼져 있으면 아무것도 만들지 않는다."""
    ROWS[:] = [mkrow("w1", "waiting")]
    for settings, cfg_ai in [(od.Settings(), ai), (od.Settings(auto_draft=True), od.AIConfig(provider="off"))]:
        app = od.OrcaDash(settings, cfg_ai, config_path=cfg)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause(0.1); app.input_source.available = False
            assert calls == [] and app._proposal_worker is None and app.proposals.get("w1") is None
            assert "제안" not in cell(app, "w1")
            if not settings.auto_draft:   # 옵션 화면의 체크박스로 켜면 저장되고 바로 만들기 시작
                await pilot.press("o"); await pilot.pause()
                box = app.screen.query_one("#auto_draft", Checkbox); assert box.value is False
                box.value = True; await pilot.press("enter"); await pilot.pause(0.1)
                await settle(pilot, app)
                assert app.settings.auto_draft and od.Settings.load(cfg).auto_draft is True
                assert keys_called() == ["w1"] and cell(app, "w1").endswith("제안 ✓")
                calls.clear()
            app.exit()
asyncio.run(flow_off())


async def flow_file():
    """파일 소스(--file)의 행은 보낼 수 없으니 제안도 만들지 않는다."""
    fx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "sample.json")
    ROWS[:] = [dataclasses.replace(mkrow("f1", "waiting"), source="file")]
    app = od.OrcaDash(od.Settings(auto_draft=True), ai, config_path=cfg, files=[od.Source(label="file", file=fx)])
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause(0.1); app.input_source.available = False
        assert calls == [] and app._proposal_worker is None and app.proposals.get("f1") is None
        app.exit()
asyncio.run(flow_file())
print("ok: off / settings switch")


async def flow():
    ROWS[:] = [mkrow("work", "working"), mkrow("done", "done"), mkrow("idle", "idle"),
               mkrow("wait", "waiting", updated=3000.0, wait="질문", path=tmp),
               mkrow("perm", "waiting_permission", updated=2000.0), mkrow("block", "blocked", updated=1000.0),
               mkrow("nopane", "waiting", pane=None), mkrow("none", None, pane=None)]
    settings = od.Settings(auto_draft=True); settings.ai_agents = ["goal", "review", "final"]
    state.update(max=0, delay=0.15); calls.clear()
    app = od.OrcaDash(settings, ai, config_path=cfg)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.05); app.input_source.available = False
        # 첫 행을 쓰는 동안: 그 행만 '제안 …', 큐에 나머지가 순서대로(막힘 → 대기는 최근 갱신 먼저) 기다린다
        assert keys_called() == ["block"] and app._proposal_queue == ["wait", "perm"], (calls, app._proposal_queue)
        assert app.proposals.get("block").status == "drafting" and app.proposals.get("block").attempts == 1
        assert cell(app, "block") == "막힘 · 제안 …" and "제안" not in cell(app, "wait"), cell(app, "block")
        await app.action_refresh()   # 작성 중에 새로고침이 와도 워커를 새로 띄우거나 중복으로 넣지 않는다
        assert app._proposal_queue == ["wait", "perm"] and state["active"] == 1
        await settle(pilot, app)
        assert keys_called() == ["block", "wait", "perm"] and state["max"] == 1, (calls, state)   # 한 번에 하나, 조건에 맞는 행만
        # 설정의 조합 그대로, 메모는 빈 문자열, 다듬기 아님. 로컬 저장소 경로는 action_send_prompt 와 같은 기준
        assert all(c[1] == ["goal", "review", "final"] and c[2] == "" and c[3] == {} for c in calls), calls
        assert calls[1][4] == tmp and calls[1][5] == tmp, calls[1]
        assert calls[0][4] == tempfile.gettempdir() and calls[0][5] is None, calls[0]
        pw = app.proposals.get("wait")
        assert pw.status == "ready" and pw.text == "제안(wait#1)" and pw.agent_ids == ["goal", "review", "final"]
        assert pw.row_updated_at == 3000.0 and pw.row_key == "wait" and pw.created_at > 0
        assert cell(app, "wait") == "입력 대기 · 질문 · 제안 ✓" and cell(app, "perm").endswith("제안 ✓")
        assert "제안" not in cell(app, "work") and app.proposals.get("work") is None and app.proposals.get("nopane") is None
        assert od.ProposalStore.valid(app.proposals, ROWS[3]) is pw
        # 유효한 제안이 있으면 새로고침해도 다시 만들지 않는다
        calls.clear(); await app.action_refresh(); await settle(pilot, app); assert calls == []
        # 상세 창에 제안 본문이 보인다
        table = app.query_one(DataTable); table.move_cursor(row=table.get_row_index("wait")); await pilot.pause()
        assert "제안(wait#1)" in str(app.query_one("#detail").render())

        # --- 모달 미리 채움: p 로 열면 입력창에 제안이 들어 있고 Ctrl+G 는 (메모 없이) 다듬기
        await pilot.press("p"); await pilot.pause()
        scr = app.screen; assert isinstance(scr, od.PromptScreen) and scr.row.key == "wait"
        assert scr.query_one(TextArea).text == "제안(wait#1)" and scr.last_draft == "제안(wait#1)" and scr.note == ""
        status = str(scr.query_one("#ai-status").render())
        assert "백그라운드 제안(목표 지향 → 문제 발견 ⇒ 최종 결정" in status and "Ctrl+G 로 다듬기" in status, status
        await pilot.press("ctrl+g"); await pilot.pause(0.4)
        assert calls == [("wait", ["final"], "", {"final": "제안(wait#1)"}, tmp, tmp)], calls   # 결정 에이전트만 다듬기
        assert scr.query_one(TextArea).text == "다듬음(wait)"
        # 모달에서 만든 결과도 저장소에 들어간다
        pm = app.proposals.get("wait")
        assert pm is not pw and pm.text == "다듬음(wait)" and pm.status == "ready" and pm.row_updated_at == 3000.0
        assert pm.agent_ids == ["goal", "review", "final"]
        await pilot.press("escape"); await pilot.pause()
        # 다시 열면 그 결과가 들어 있고, 지우고 메모를 쓰면 새 초안으로 동작해 그것도 저장된다
        await pilot.press("p"); await pilot.pause(); scr = app.screen
        assert scr.query_one(TextArea).text == "다듬음(wait)"
        scr.query_one(TextArea).load_text("전혀 다른 새 메모"); calls.clear()
        await pilot.press("ctrl+g"); await pilot.pause(0.4)
        assert calls == [("wait", ["goal", "review", "final"], "전혀 다른 새 메모", {}, tmp, tmp)], calls
        pn = app.proposals.get("wait")
        assert pn is not pm and pn.text == "제안(wait#1)" and scr.query_one(TextArea).text == "제안(wait#1)", pn
        # Enter 로 보내면 '보냄'이 되어 표시가 사라지고, 조회가 아직 옛 상태여도 다시 만들지 않는다
        calls.clear(); await pilot.press("enter"); await pilot.pause(0.2)
        assert state["sent"] == ["제안(wait#1)"] and app.proposals.get("wait").status == "sent"
        assert "제안" not in cell(app, "wait")
        await app.action_refresh(); await settle(pilot, app); assert calls == []
        await pilot.press("p"); await pilot.pause()
        assert app.screen.query_one(TextArea).text == "" and app.screen.last_draft is None   # 보낸 제안은 다시 채우지 않음
        await pilot.press("escape"); await pilot.pause()

        # --- 행이 바뀌면(updated_at) 버리고 다시 만든다. 상태가 작업 중으로 가면 만들지 않는다
        ROWS[3] = mkrow("wait", "waiting", updated=4000.0, path=tmp); ROWS[4] = mkrow("perm", "working", updated=2500.0)
        await app.action_refresh(); await settle(pilot, app)
        assert keys_called() == ["wait"] and app.proposals.get("wait").row_updated_at == 4000.0, calls
        assert app.proposals.get("wait").status == "ready" and app.proposals.get("perm") is None
        assert "제안" not in cell(app, "perm")

        # --- 실패: status="error" 와 사유, 다음 새로고침에 재시도하되 같은 updated_at 에 2번까지만
        fail_keys.add("block"); ROWS[5] = mkrow("block", "blocked", updated=1500.0); calls.clear()
        await app.action_refresh(); await settle(pilot, app)
        pe = app.proposals.get("block")
        assert keys_called() == ["block"] and pe.status == "error" and pe.error == "가짜 실패" and pe.attempts == 1, pe
        assert cell(app, "block") == "막힘 · 제안 ✗" and app.proposals.valid(ROWS[5]) is None
        await app.action_refresh(); await settle(pilot, app)
        assert keys_called() == ["block", "block"] and app.proposals.get("block").attempts == 2
        for _ in range(3):
            await app.action_refresh(); await settle(pilot, app)
        assert keys_called() == ["block", "block"], calls          # 상한 뒤에는 더 시도하지 않음
        table.move_cursor(row=table.get_row_index("block")); await pilot.pause()
        assert "실패 (2/2회 시도): 가짜 실패" in str(app.query_one("#detail").render())
        await pilot.press("p"); await pilot.pause()                # 실패한 제안은 채우지 않고 사유만 알린다
        assert app.screen.query_one(TextArea).text == "" and "백그라운드 제안 실패: 가짜 실패" in str(app.screen.query_one("#ai-status").render())
        await pilot.press("escape"); await pilot.pause()
        ROWS[5] = mkrow("block", "blocked", updated=1600.0)        # 행이 갱신되면 횟수가 초기화되어 다시 시도
        await app.action_refresh(); await settle(pilot, app)
        assert keys_called() == ["block"] * 3 and app.proposals.get("block").attempts == 1
        fail_keys.clear()
        await app.action_refresh(); await settle(pilot, app)
        assert app.proposals.get("block").status == "ready" and app.proposals.get("block").attempts == 2

        # --- 만드는 사이 행이 바뀌면 결과를 버린다
        ROWS[5] = mkrow("block", "blocked", updated=1700.0); calls.clear()
        await app.action_refresh(); await pilot.pause(0.05)
        assert app.proposals.get("block").status == "drafting"
        ROWS[5] = mkrow("block", "blocked", updated=1800.0)
        await app.action_refresh(); await settle(pilot, app)
        assert keys_called() == ["block", "block"] and app.proposals.get("block").row_updated_at == 1800.0
        assert app.proposals.get("block").text == "제안(block#2)" and state["max"] == 1

        # --- _propose 는 직접 불러도 Proposal 을 돌려준다 (자동 전송이 쓰는 길)
        got = await app._propose(ROWS[4])
        assert isinstance(got, od.Proposal) and got.status == "ready" and app.proposals.get("perm") is got
        app.exit()
asyncio.run(flow())
print("ok: queue / table / modal / retry")
print("ALL OK")
