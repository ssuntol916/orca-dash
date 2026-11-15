"""자동 전송 루프의 진행 판정: 막힘·달성이면 보내지 않고 알림·기록, 계속이면 보내고 head 를 기록."""
import asyncio, json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od

tmp = tempfile.mkdtemp(); cdir = os.path.join(tmp, "cfg"); cfg = os.path.join(cdir, "config.json")
log = os.path.join(cdir, od.SEND_LOG_NAME)
records = lambda: [json.loads(l) for l in open(log, encoding="utf-8")] if os.path.exists(log) else []

def mkrow(key, updated=1000.0, **kw):
    base = dict(key=key, source="local", pane_key="tab:" + key, host="local", path=tmp, repo="repo1",
                worktree="wt-" + key, branch="b", agent_type="claude", state="waiting_input", main_state=None,
                wait="질문", started_at=None, updated_at=updated, tool="", summary="", detail="상세", unread=False)
    base.update(kw); return od.Row(**base)

ROWS: list = []; sent: list = []; judged: list = []; notified: list = []
VERDICT = od.Verdict("continue", "할 일이 남음")
async def fake_fetch(src): return list(ROWS), None
async def fake_send(src, pane_key, text): sent.append(text); return "전송됨"
async def fake_judge(cfg, row, repo_dir, history, *, agent=None, cwd=None):
    judged.append((row.key, len(history), agent.id if agent else None)); return VERDICT
async def fake_head(repo_dir): return "abc123"
od.fetch = fake_fetch; od.send_prompt = fake_send; od.judge_progress = fake_judge; od.repo_head = fake_head
od.notify_user = lambda title, text: notified.append((title, text))

async def flow():
    global VERDICT
    settings = od.Settings(auto_send=True, auto_send_cooldown=0, ai_agents=["goal", "final"])
    app = od.OrcaDash(settings, od.AIConfig(provider="claude"), config_path=cfg)
    app.input_source.available = False
    a = mkrow("a"); ROWS[:] = [a]
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        # 1) 막힘 → 보내지 않고 알림·기록·사유
        VERDICT = od.Verdict("stuck", "같은 오류 반복")
        app.proposals.put(od.Proposal(a.key, "제안1", ["goal", "final"], time.time(), a.updated_at))
        assert app._auto_send_tick() is a
        await pilot.pause(0.3)
        assert sent == [] and judged == [("a", 0, "verdict")], (sent, judged)
        assert notified and "막힘" in notified[0][0], notified
        assert "진행 판정 막힘" in app._auto_reasons["a"], app._auto_reasons
        recs = records(); assert len(recs) == 1 and recs[0]["result"].startswith("보류: 진행 판정 막힘") and recs[0]["head"] == "abc123", recs
        assert app.verdicts[a.key][0].verdict == "stuck"
        assert app._auto_send_tick() is None   # 같은 턴에는 다시 시도하지 않음
        # 2) 새 턴, 계속 → 보내고 head 기록. 보류 기록은 연속 횟수에 세지 않음
        a2 = mkrow("a", updated=2000.0); ROWS[:] = [a2]; await app.action_refresh(); await pilot.pause(0.3)
        VERDICT = od.Verdict("continue", "다음 단계 있음"); notified.clear()
        app.proposals.put(od.Proposal(a2.key, "제안2", ["goal", "final"], time.time(), a2.updated_at))
        assert app._auto_send_tick() is a2
        await pilot.pause(0.3)
        assert sent == ["제안2"] and judged[-1] == ("a", 1, "verdict") and notified == [], (sent, judged, notified)
        recs = records(); assert recs[-1]["result"] == "ok" and recs[-1]["head"] == "abc123" and recs[-1]["auto"]
        # 3) 판정 실패 → 정책대로 보내되 policy 에 사유
        a3 = mkrow("a", updated=3000.0); ROWS[:] = [a3]; await app.action_refresh(); await pilot.pause(0.3)
        VERDICT = od.Verdict("continue", f"{od.VERDICT_FAILED}: 빈 응답")
        app.proposals.put(od.Proposal(a3.key, "제안3", ["goal", "final"], time.time(), a3.updated_at))
        assert app._auto_send_tick() is a3; await pilot.pause(0.3)
        assert sent == ["제안2", "제안3"] and od.VERDICT_FAILED in records()[-1]["policy"], records()[-1]
        # 4) 달성 → 보내지 않음
        a4 = mkrow("a", updated=4000.0); ROWS[:] = [a4]; await app.action_refresh(); await pilot.pause(0.3)
        VERDICT = od.Verdict("done", "지시가 끝남")
        app.proposals.put(od.Proposal(a4.key, "제안4", ["goal", "final"], time.time(), a4.updated_at))
        assert app._auto_send_tick() is a4; await pilot.pause(0.3)
        assert sent == ["제안2", "제안3"] and "달성" in notified[-1][0] and records()[-1]["result"].startswith("보류: 진행 판정 달성")
        app.exit()
asyncio.run(flow())
print("ok: loop verdict")
print("ALL OK")
