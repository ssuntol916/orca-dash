"""자동 전송 정책: auto_send_allowed 의 거부 사유, 설정 저장·로드·검증·호환, 「자동 전송」 탭 헤드리스 테스트."""
import argparse, asyncio, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import Button, Input, Switch, TabbedContent

tmp = tempfile.mkdtemp()
cfg = os.path.join(tmp, "cfg", "config.json")
NOW = 1_000_000.0


def mkrow(**kw):
    base = dict(key="local|wt|pane", source="local", pane_key="tab:leaf", host="h", path="", repo="repo1",
                worktree="w", branch="b", agent_type="claude", state="waiting_input", main_state=None, wait="질문",
                started_at=None, updated_at=None, tool="", summary="", detail="", unread=False)
    base.update(kw)
    return od.Row(**base)


def on(**kw):
    s = od.Settings(auto_send=True, ai_agents=["goal", "final"], **kw)
    assert s.validate() == [], s.validate()
    return s


def sent(ago, auto=True):
    return {"at": NOW - ago, "text": "x", "auto": auto}


def check(settings, row, history=(), **kw):
    return od.auto_send_allowed(settings, row, list(history), now=NOW, **kw)


# 1) 기본값과 계약
d = od.Settings()
assert (d.auto_send, d.auto_send_states, d.auto_send_waits, d.auto_send_max_streak, d.auto_send_cooldown,
        d.auto_send_repos, d.auto_send_require_final) == (False, ["waiting_input"], ["질문"], 3, 120, {}, True)
assert od.auto_send_allowed(d, mkrow(), []) == (False, "자동 전송 꺼짐")   # 계약의 3인자 호출
print("ok: defaults")

# 2) 거부 사유 하나씩
row = mkrow()
assert check(on(), row) == (True, "허용 (상태 waiting_input · 대기 사유 질문 · 연속 0/3회)")
assert check(od.Settings(), row) == (False, "자동 전송 꺼짐")
assert check(on(auto_send_repos={"repo1": False}), row) == (False, "저장소 repo1 는 꺼짐")
assert check(on(auto_send_repos={"other": False}), row)[0]                       # 다른 저장소 설정은 무관
only = od.Settings(auto_send=False, auto_send_repos="repo1:on", ai_agents=["final"]); assert only.validate() == []
assert check(only, row)[0] and check(only, mkrow(repo="repo2")) == (False, "자동 전송 꺼짐")  # 저장소 설정이 전체보다 우선
assert check(on(), mkrow(pane_key=None)) == (False, "에이전트 터미널 없음")
assert check(on(), mkrow(state="working", wait="")) == (False, "상태 working 은 허용 안 됨")
assert check(on(), mkrow(state=None, wait="")) == (False, "상태 없음 은 허용 안 됨")
assert check(on(), mkrow(state="waiting", wait="")) [0]                           # waiting = waiting_input, 빈 사유 = 질문
assert check(on(auto_send_states=["waiting"]), row)[0]
assert check(on(), mkrow(wait="권한")) == (False, "대기 사유 권한 은 허용 안 됨")
assert check(on(), mkrow(wait="permission_prompt")) == (False, "대기 사유 권한 은 허용 안 됨")
assert check(on(), mkrow(wait="중단됨")) == (False, "대기 사유 중단 은 허용 안 됨")
assert check(on(auto_send_waits=["질문", "중단"]), mkrow(wait="중단됨"))[0]
assert check(on(), mkrow(wait="rate_limit")) == (False, "대기 사유 rate_limit 은 허용 안 됨")
assert check(on(auto_send_waits=["rate_limit"]), mkrow(wait="rate_limit"))[0]     # 분류에 없는 사유는 글 그대로 비교
assert check(on(auto_send_states=["waiting_input", "done"]), mkrow(state="done", wait="")) == \
    (False, "대기 사유 없음 은 허용 안 됨")
assert check(on(auto_send_states=["done"], auto_send_waits=["없음"]), mkrow(state="done", wait=""))[0]
# 권한 대기·막힘은 설정을 손으로 고쳐 넣어도 항상 거부
forced = on(); forced.auto_send_states = ["waiting_input", "permission", "blocked"]; forced.auto_send_waits = ["질문", "권한"]
assert check(forced, mkrow(state="permission", wait="")) == (False, "상태 permission 은 허용 안 됨")
assert check(forced, mkrow(state="blocked", wait="")) == (False, "상태 blocked 은 허용 안 됨")
assert check(forced, mkrow(wait="권한")) == (False, "대기 사유 권한 은 허용 안 됨")
# 최종 결정 에이전트
nofinal = od.Settings(auto_send=True, ai_agents=["goal", "review"]); assert nofinal.validate() == []
assert check(nofinal, row) == (False, "작성 에이전트에 최종 결정 에이전트 없음")
nofinal.auto_send_require_final = False; assert check(nofinal, row)[0]
adir = od.agents_dir(cfg); os.makedirs(adir)
open(os.path.join(adir, "judge.md"), "w").write("---\nname: 심판\nfinal: on\n---\n역할: 하나로 정한다.\n")
agents, errs = od.load_agents(cfg); assert errs == []
custom = od.Settings(auto_send=True, ai_agents=["goal", "judge"]); assert custom.validate() == []
assert not check(custom, row)[0] and check(custom, row, agents=agents)[0]        # 사용자 정의 final: on 은 agents 를 줄 때
assert od.has_final_agent(on()) and not od.has_final_agent(nofinal)
# 연속 상한: 최근부터 auto 가 이어지는 수, 사람이 보내면 끊김, 순서는 가리지 않음
three = [sent(900), sent(600), sent(300)]
assert od.auto_send_streak(three) == 3 and od.auto_send_streak(three[::-1]) == 3
assert check(on(), row, three) == (False, "연속 3회 상한")
assert check(on(), row, three[::-1]) == (False, "연속 3회 상한")
assert check(on(auto_send_max_streak=4), row, three) == (True, "허용 (상태 waiting_input · 대기 사유 질문 · 연속 3/4회)")
broken = [sent(900), sent(600), sent(450, auto=False), sent(300)]
assert od.auto_send_streak(broken) == 1 and check(on(), row, broken)[0]
assert od.auto_send_streak([]) == 0 and od.auto_send_streak([sent(10, auto=False), sent(20)]) == 0
assert od.auto_send_streak(["junk", {"auto": True}, None]) == 1                   # 깨진 항목은 건너뜀
# 최소 간격: 사람이 보낸 것도 마지막 전송
assert check(on(), row, [sent(85)]) == (False, "마지막 전송 후 85초 (120초 미만)")
assert check(on(), row, [sent(85, auto=False)]) == (False, "마지막 전송 후 85초 (120초 미만)")
assert check(on(), row, [sent(120)])[0] and check(on(auto_send_cooldown=0), row, [sent(1)])[0]
assert check(on(), row, [sent(-30)]) == (False, "마지막 전송 후 0초 (120초 미만)")  # 시계가 뒤로 가도 음수 없음
assert check(on(), row, [sent(900), sent(600), sent(10)]) == (False, "연속 3회 상한")   # 상한을 간격보다 먼저 알림
assert od.wait_kind(mkrow(wait="")) == "질문" and od.wait_kind(mkrow(state="idle", wait="")) == "없음"
assert od.wait_kind(mkrow(state="permission", wait="")) == "권한"
print("ok: auto_send_allowed")

# 3) 설정 검증·저장·로드·호환
s = od.Settings(auto_send="on", auto_send_states="waiting, done", auto_send_waits="", auto_send_max_streak="5",
                auto_send_cooldown="0", auto_send_repos="a:on, b:off", auto_send_require_final="off")
assert s.validate() == [], s.validate()
assert (s.auto_send, s.auto_send_states, s.auto_send_waits, s.auto_send_max_streak, s.auto_send_cooldown,
        s.auto_send_repos, s.auto_send_require_final) == (True, ["waiting", "done"], ["질문"], 5, 0,
                                                          {"a": True, "b": False}, False)
s.save(cfg); disk = json.load(open(cfg))
assert disk["auto_send"] is True and disk["auto_send_repos"] == {"a": True, "b": False} and disk["auto_send_max_streak"] == 5
assert od.Settings.load(cfg) == s
assert od.format_repo_flags(s.auto_send_repos) == "a:on b:off" and od.parse_repo_flags("") == {}
# 필드가 없는 기존 설정 파일 → 기본값(꺼짐)
old = {k: v for k, v in disk.items() if not k.startswith("auto_send")}
json.dump(old, open(cfg, "w")); o = od.Settings.load(cfg)
assert o.auto_send is False and o.auto_send_states == ["waiting_input"] and o.auto_send_cooldown == 120 and o.interval == s.interval
# 잘못된 값
def errs_of(**kw): return od.Settings(**kw).validate()
assert any("자동 전송은 on 또는 off" in e for e in errs_of(auto_send="maybe"))
assert any("상한" in e for e in errs_of(auto_send_max_streak=0)) and any("상한" in e for e in errs_of(auto_send_max_streak="x"))
assert any("간격" in e for e in errs_of(auto_send_cooldown=-1))
assert any("저장소별" in e for e in errs_of(auto_send_repos="repo1")) and any("저장소별" in e for e in errs_of(auto_send_repos="r:maybe"))
assert any("저장소별" in e for e in errs_of(auto_send_repos=["r"]))
assert any("permission" in e for e in errs_of(auto_send_states=["waiting_input", "permission"]))
assert any("blocked" in e for e in errs_of(auto_send_states="blocked"))
assert any("권한" in e for e in errs_of(auto_send_waits=["질문", "권한"]))
assert any("auto_send_states" in e for e in errs_of(auto_send_states=5))
bad = od.Settings(auto_send="maybe"); bad.validate(); assert bad.auto_send is False   # 알 수 없는 값은 꺼짐으로
json.dump({"auto_send": "maybe"}, open(cfg, "w"))
try: od.Settings.load(cfg); raise AssertionError
except od.ConfigError as e: assert "자동 전송" in str(e)
# 명령줄 --auto-send
ns = argparse.Namespace(interval=None, orca=None, env=None, host=None, ssh=None, ai=None, ai_model=None,
                        ai_timeout=None, no_local=False, ai_context=None, auto_send="on")
a = od.Settings(); assert a.apply_args(ns) == ["auto_send"] and a.auto_send is True
ns.auto_send = "off"; a.apply_args(ns); assert a.auto_send is False
ns.auto_send = None; assert od.Settings(auto_send=True).apply_args(ns) == []
del ns.auto_send; assert od.Settings().apply_args(ns) == []                         # 인자가 없는 이전 Namespace 호환
print("ok: settings")

# 4) 「자동 전송」 탭: 24줄 터미널에서 편집 → 오류 표시 → 저장·적용
async def flow():
    od.Settings(ai="off").save(cfg)
    settings = od.Settings.load(cfg)
    app = od.OrcaDash(settings, settings.ai_config(), config_path=cfg,
                      files=[od.Source(label="file", file="/dev/null")])
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); app.input_source.available = False
        await pilot.press("o"); await pilot.pause()
        scr = app.screen; assert isinstance(scr, od.SettingsScreen)
        scr.query_one(TabbedContent).active = "tab-auto"; await pilot.pause()
        q = scr.query_one
        assert q("#auto_send", Switch).value is False and q("#auto_send_require_final", Switch).value is True
        assert q("#auto_send_states", Input).value == "waiting_input" and q("#auto_send_waits", Input).value == "질문"
        assert q("#auto_send_max_streak", Input).value == "3" and q("#auto_send_cooldown", Input).value == "120"
        assert q("#auto_send_repos", Input).value == ""
        # 24줄에서도 저장·취소 버튼이 화면 안에 있고, 탭 내용은 스크롤 영역에 들어 있다
        for bid in ("#save", "#cancel"):
            r = q(bid, Button).region
            assert r.height > 0 and r.y >= 0 and r.bottom <= 24, (bid, r)
        assert q("#auto-form").region.height >= 3, q("#auto-form").region
        # 스위치는 클릭으로 토글
        q("#auto_send", Switch).scroll_visible(animate=False); await pilot.pause()
        await pilot.click("#auto_send"); await pilot.pause()
        assert q("#auto_send", Switch).value is True
        # 잘못된 값 → 오류 표시, 창 유지
        q("#auto_send_repos", Input).value = "repo1"
        q("#auto_send_states", Input).value = "waiting_input permission"
        q("#auto_send_states", Input).focus(); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        err = str(q("#form-error").render())
        assert "저장소별" in err and "permission" in err and app.screen is scr, err
        # 정상 값 → Enter 로 저장·적용
        q("#auto_send_states", Input).value = "waiting_input done"
        q("#auto_send_waits", Input).value = "질문 없음"
        q("#auto_send_max_streak", Input).value = "5"
        q("#auto_send_cooldown", Input).value = "30"
        q("#auto_send_repos", Input).value = "repo1:on repo2:off"
        q("#auto_send_require_final", Switch).value = False
        await pilot.press("enter"); await pilot.pause(); await pilot.pause(0.3)
        assert not isinstance(app.screen, od.SettingsScreen)
        st = app.settings
        assert st.auto_send is True and st.auto_send_states == ["waiting_input", "done"]
        assert st.auto_send_waits == ["질문", "없음"] and st.auto_send_max_streak == 5 and st.auto_send_cooldown == 30
        assert st.auto_send_repos == {"repo1": True, "repo2": False} and st.auto_send_require_final is False
        disk = json.load(open(cfg))
        assert disk["auto_send"] is True and disk["auto_send_repos"] == {"repo1": True, "repo2": False}, disk
        assert od.Settings.load(cfg) == st
        assert od.auto_send_allowed(st, mkrow(repo="repo2"), []) == (False, "저장소 repo2 는 꺼짐")
        assert od.auto_send_allowed(st, mkrow(), [])[0]
        # 다시 열면 저장한 값이 보이고, Esc 는 바꾸지 않는다
        await pilot.press("o"); await pilot.pause()
        scr = app.screen
        assert scr.query_one("#auto_send", Switch).value is True
        assert scr.query_one("#auto_send_repos", Input).value == "repo1:on repo2:off"
        scr.query_one("#auto_send", Switch).value = False
        await pilot.press("escape"); await pilot.pause()
        assert app.settings.auto_send is True
        app.exit()
asyncio.run(flow())
print("ok: auto tab")
print("ALL OK")
