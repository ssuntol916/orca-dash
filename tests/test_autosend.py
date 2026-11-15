"""자동 전송: 기록 파일 쓰기/읽기 · 정책 최소 구현 · tick(거부·일시 정지·제안 없음·허용·실패 후 재시도 안 함) 헤드리스."""
import asyncio, dataclasses, json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import DataTable

tmp = tempfile.mkdtemp(); cdir = os.path.join(tmp, "cfg"); cfg = os.path.join(cdir, "config.json")
log = os.path.join(cdir, od.SEND_LOG_NAME)

def mkrow(key, updated=1000.0, **kw):
    base = dict(key=key, source="local", pane_key="tab:leaf-" + key, host="local", path="", repo="repo1",
                worktree="wt-" + key, branch="b", agent_type="claude", state="waiting_input", main_state=None,
                wait="질문", started_at=None, updated_at=updated, tool="", summary="", detail="상세", unread=False)
    base.update(kw)
    return od.Row(**base)

# 1) 기록 파일 쓰기/읽기
assert od.load_send_history(cdir, "k1") == []            # 파일·디렉터리 없음
for i in range(25):
    od.append_send_record(cdir, {"at": float(i), "row_key": "k1" if i % 5 else "k2", "text": f"한글 {i}", "auto": True})
with open(log, "a") as f: f.write("{깨진 줄\n[1, 2]\n")
od.append_send_record(cdir, {"at": 99.0, "row_key": "k1", "text": "끝", "auto": False})
lines = open(log, encoding="utf-8").read().splitlines()
assert len(lines) == 28 and "한글 1" in lines[1] and json.loads(lines[0])["row_key"] == "k2", lines[:2]
h = od.load_send_history(cdir, "k1")
assert len(h) == 20 and h[-1]["text"] == "끝" and h[-1]["auto"] is False and all(x["row_key"] == "k1" for x in h)
assert [x["at"] for x in h] == sorted(x["at"] for x in h)            # 오래된 것부터
assert len(od.load_send_history(cdir, "k1", limit=3)) == 3 and len(od.load_send_history(cdir, "k2")) == 5
assert od.load_send_history(cdir, "없는 행") == []
os.remove(log)
print("ok: send log")

# 2) 정책 (계약의 최소 구현)
S = lambda **kw: od.Settings(**{"ai_agents": ["goal", "final"], **kw}); row = mkrow("a"); now = time.time()   # 최종 결정 에이전트 포함
assert S().auto_send is False and S().auto_send_states == ["waiting_input"] and S().auto_send_waits == ["질문"]
assert S().auto_send_max_streak == 3 and S().auto_send_cooldown == 120 and S().auto_send_require_final is True
ok, why = od.auto_send_allowed(S(), row, []); assert not ok and why == "자동 전송 꺼짐", why
on = S(auto_send=True)
ok, why = od.auto_send_allowed(on, row, []); assert ok and "허용" in why, why
assert not od.auto_send_allowed(S(auto_send=True, auto_send_repos={"repo1": False}), row, [])[0]
assert od.auto_send_allowed(S(auto_send_repos={"repo1": True}), row, [])[0]            # 저장소 설정이 전체 설정보다 우선
assert not od.auto_send_allowed(on, mkrow("a", state="working"), [])[0]
assert not od.auto_send_allowed(on, mkrow("a", wait="권한"), [])[0]
assert not od.auto_send_allowed(S(auto_send=True, auto_send_waits=["권한"]), mkrow("a", wait="권한"), [])[0]   # 권한은 설정해도 항상 거부
old = lambda n, auto=True, **kw: dict({"at": now - 1000 + n, "text": "t", "auto": auto}, **kw)
ok, why = od.auto_send_allowed(on, row, [old(1), old(2), old(3)]); assert not ok and "연속" in why, why
assert od.auto_send_allowed(on, row, [old(1), old(2), old(3), old(4, auto=False)])[0]            # 사람이 보내면 다시 시작
assert od.auto_send_allowed(on, row, [old(1), old(2), old(3, result="실패")])[0]            # 실패한 전송은 세지 않음
ok, why = od.auto_send_allowed(on, row, [{"at": now - 10, "text": "t", "auto": True}]); assert not ok and "초 미만" in why, why
assert od.auto_send_allowed(S(auto_send=True, auto_send_cooldown=0), row, [{"at": now - 10, "text": "t", "auto": True}])[0]
s = S(auto_send=True, auto_send_states="waiting_input waiting", auto_send_repos={"r": 1}, auto_send_cooldown="30")
assert s.validate() == [] and s.auto_send_states == ["waiting_input", "waiting"] and s.auto_send_repos == {"r": True}
assert S(auto_send_states="waiting_input blocked").validate()   # 막힘·권한 대기는 허용 상태에 넣을 수 없음 (정책 규칙)
s.save(cfg); assert od.Settings.load(cfg) == s and json.load(open(cfg))["auto_send_cooldown"] == 30
assert S(auto_send_repos=[1]).validate() and S(auto_send_max_streak="x").validate()
st = od.ProposalStore(); p = od.Proposal("a", "제안", ["goal", "final"], now, 1000.0, "ready")
st.put(p); assert st.get("a") is p and od.proposal_ready(p, row) and st.get("b") is None
assert not od.proposal_ready(None, row) and not od.proposal_ready(p, mkrow("a", updated=2000.0))
assert not od.proposal_ready(dataclasses.replace(p, status="pending"), row)
assert not od.proposal_ready(dataclasses.replace(p, text="  "), row)
st.invalidate("a"); st.invalidate("a"); assert st.get("a") is None
print("ok: policy")

# 3) 앱: 새로고침 뒤 tick
ROWS: list = []; sent: list = []; fail_keys: set = set()
async def fake_fetch(src): return list(ROWS), None
async def fake_send(src, pane_key, text):
    sent.append((pane_key, text))
    if pane_key in fail_keys: raise od.OrcaError("라이브 터미널을 찾지 못함")
    return "전송됨"
od.fetch = fake_fetch; od.send_prompt = fake_send
records = lambda: [json.loads(l) for l in open(log, encoding="utf-8")] if os.path.exists(log) else []
prop = lambda r, text="제안", ids=("goal", "final"), **kw: od.Proposal(r.key, text, list(ids), time.time(), r.updated_at, **kw)

async def flow():
    settings = od.Settings(auto_send_cooldown=0, ai_agents=["goal", "final"])
    app = od.OrcaDash(settings, od.AIConfig(provider="off"), config_path=cfg)
    app.input_source.available = False
    a = mkrow("a"); ROWS[:] = [a]
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        status = lambda: (app._tick_status(), app.query_one("#status").render().plain)[1]
        assert app.auto_paused is False and isinstance(app.proposals, od.ProposalStore)
        assert "자동 전송 OFF · 오늘 0회" in status(), status()
        # 꺼져 있음 → 제안이 있어도 보내지 않음
        app.proposals.put(prop(a))
        assert app._auto_send_tick() is None and "자동 전송 꺼짐" in app._auto_reasons["a"]
        settings.auto_send = True
        assert "자동 전송 ON" in status()
        # 제안 없음 · 낡은 제안 · 준비 안 된 제안 → 보내지 않음 (초안 체인도 돌리지 않음)
        app.proposals.invalidate("a"); assert app._auto_send_tick() is None
        app.proposals.put(od.Proposal("a", "낡음", ["final"], time.time(), 999.0)); assert app._auto_send_tick() is None
        app.proposals.put(prop(a, status="pending")); assert app._auto_send_tick() is None
        # 최종 결정 에이전트를 거치지 않은 제안 → 정책 거부
        app.proposals.put(prop(a, ids=("goal",)))
        assert app._auto_send_tick() is None and "최종 결정" in app._auto_reasons["a"]
        # 정책 거부 (상태가 대상이 아님)
        app.proposals.put(prop(a)); ROWS[:] = [mkrow("a", state="working")]; await app.action_refresh(); await pilot.pause()
        assert "상태 working" in app._auto_reasons["a"], app._auto_reasons
        # 일시 정지: a 키 (한글 자판 ㅁ 도)
        ROWS[:] = [a]; await pilot.press("a"); await pilot.pause()
        assert app.auto_paused and "자동 전송 일시 정지" in status()
        await app.action_refresh(); await pilot.pause()
        assert sent == [] and records() == [], (sent, records())
        await pilot.press("ㅁ"); await pilot.pause()
        assert not app.auto_paused and "자동 전송 ON" in status()
        # 허용: 새로고침 한 번에 한 번만 보내고 기록
        await app.action_refresh()
        assert app._auto_send_tick() is None            # 전송이 진행 중이면 겹쳐 보내지 않음
        await pilot.pause(); await pilot.pause()
        assert sent == [("tab:leaf-a", "제안")], sent
        rec = records(); assert len(rec) == 1, rec
        r = rec[0]
        assert r["auto"] is True and r["result"] == "ok" and r["text"] == "제안" and r["row_key"] == "a"
        assert (r["repo"], r["worktree"], r["branch"], r["state"], r["wait"]) == ("repo1", "wt-a", "b", "waiting_input", "질문")
        assert r["agent_ids"] == ["goal", "final"] and "질문" in r["policy"] and abs(r["at"] - time.time()) < 5, r
        assert app.proposals.get("a").status == "sent" and "오늘 1회" in status(), status()   # 보낸 제안은 지우지 않고 보냄으로 남김
        app._render_table(); assert str(app.query_one(DataTable).get_cell("a", "auto")).startswith("1회 ")
        # 같은 턴(updated_at)에는 새 제안이 와도 다시 보내지 않음 — 재시작해 메모리가 비어도 기록으로 막음
        app.proposals.put(prop(a, "또")); assert app._auto_send_tick() is None
        app._auto_tried.clear(); assert app._auto_send_tick() is None and len(sent) == 1
        # 두 행이 모두 허용이어도 한 tick 에 한 행만 (오래 기다린 행부터)
        a2 = mkrow("a", updated=2000.0); b = mkrow("b", updated=1500.0); ROWS[:] = [a2, b]
        app.proposals.put(prop(a2, "A2")); p_b = prop(b, "B"); p_b.drafts = {"goal": "초안"}; app.proposals.put(p_b)
        await app.action_refresh(); await pilot.pause(); await pilot.pause()
        assert [t for _, t in sent] == ["제안", "B"], sent
        assert records()[-1]["drafts"] == {"goal": "초안"}
        await app.action_refresh(); await pilot.pause(); await pilot.pause()
        assert [t for _, t in sent] == ["제안", "B", "A2"], sent
        await app.action_refresh(); await pilot.pause(); assert len(sent) == 3
        # 실패: 기록하고, 그 updated_at 동안은 새 제안이 와도 다시 시도하지 않음
        c = mkrow("c", updated=3000.0); ROWS[:] = [c]; fail_keys.add(c.pane_key)
        app.proposals.put(prop(c, "C"))
        await app.action_refresh(); await pilot.pause(); await pilot.pause()
        r = records()[-1]
        assert len(sent) == 4 and r["auto"] is True and r["row_key"] == "c" and "라이브 터미널" in r["result"], r
        assert app.proposals.get("c") is not None and "c" not in app._auto_times
        for _ in range(2):
            app.proposals.put(prop(c, "C 다시")); await app.action_refresh(); await pilot.pause()
        assert len(sent) == 4 and len(records()) == 4, sent
        assert "이미 자동 전송을 시도" in app._auto_reasons["c"]
        fail_keys.clear(); c2 = mkrow("c", updated=3500.0); ROWS[:] = [c2]; app.proposals.put(prop(c2, "C2"))
        await app.action_refresh(); await pilot.pause(); await pilot.pause()
        assert sent[-1][1] == "C2" and records()[-1]["result"] == "ok"            # 행이 갱신되면 다시 대상
        # 사람이 Enter 로 보낸 것도 auto=False 로 기록되고 남은 제안은 버림
        app.proposals.put(od.Proposal("c", "남은 제안", ["final"], time.time(), 9.0))
        assert await app._send_prompt(app.source_by_label["local"], c2, "사람이 씀", agent_ids=["goal"]) is True
        r = records()[-1]
        assert r["auto"] is False and r["text"] == "사람이 씀" and r["policy"] == "사람이 직접 전송" and r["agent_ids"] == ["goal"], r
        assert app.proposals.get("c").status == "sent" and "오늘 4회" in status(), status()
        # 연속 한도: a 는 자동 2회(제안, A2) → 한 번 더 보내면 3회, 그 뒤에는 사람이 보낼 때까지 거부
        a3 = mkrow("a", updated=4000.0); ROWS[:] = [a3]; app.proposals.put(prop(a3, "A3"))
        await app.action_refresh(); await pilot.pause(); await pilot.pause(); assert sent[-1][1] == "A3"
        a4 = mkrow("a", updated=5000.0); ROWS[:] = [a4]; app.proposals.put(prop(a4, "A4"))
        await app.action_refresh(); await pilot.pause()
        assert sent[-1][1] == "A3" and "연속 3회" in app._auto_reasons["a"], app._auto_reasons
        # 파일 소스·에이전트 없는 행은 대상이 아님
        d = mkrow("d", pane_key=None); ROWS[:] = [d]; app.proposals.put(prop(d)); n = len(sent)
        await app.action_refresh(); await pilot.pause(); assert len(sent) == n
        # 다시 띄우면 기록에서 횟수를 이어받음
        app2 = od.OrcaDash(settings, od.AIConfig(provider="off"), config_path=cfg)
        assert len(app2._auto_times["a"]) == 3 and "c" in app2._auto_times and "오늘 5회" in app2._auto_status_text()
        app.exit()
asyncio.run(flow())
print("ok: tick")
print("ALL OK")
