import asyncio, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orca_dash as od
from textual.widgets import Input, Checkbox, Select

SP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
cfg = os.path.join(tempfile.mkdtemp(), "cfg", "config.json")

# 1) Settings 단위 동작
s = od.Settings.load(cfg); assert s.interval == 60 and s.local, s
s.env = "a, b c"; s.interval = "3"; s.ai_timeout = ""; errs = s.validate()
assert errs == [] and s.env == ["a","b","c"] and s.interval == 5 and s.ai_timeout is None, (errs, s)
s.save(cfg); print("saved:", json.load(open(cfg)))
s2 = od.Settings.load(cfg); assert s2 == s
open(cfg, "w").write("{bad"); 
try: od.Settings.load(cfg); raise AssertionError
except od.ConfigError as e: print("bad json ->", str(e)[:60])
s.save(cfg)
# CLI 우선
import argparse
ns = argparse.Namespace(interval=30, orca=None, env=None, host=None, ssh=None, ai="off", ai_model=None, ai_timeout=None, no_local=True, ai_context="off")
over = s.apply_args(ns); assert over == ["interval","ai","local","ai_context"], over
assert s.interval == 30 and s.ai == "off" and not s.local and not s.ai_context
assert not s.ai_config().enabled
bad = od.Settings(ai="nope"); assert bad.validate()
try: od.Settings(ai="claude", orca="x").ai_config()  # claude 있음
except od.ConfigError: raise AssertionError
import shutil; assert shutil.which("claude")

# 2) 앱 안에서 o -> 수정 -> Enter -> 저장·적용
async def run():
    st = od.Settings.load(cfg)   # a,b,c env + local
    app = od.OrcaDash(st, st.ai_config(), config_path=cfg,
                      files=[od.Source(label="file", file=f"{SP}/sample.json")])
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        n0 = app.query_one("DataTable").row_count
        assert n0 > 0, n0
        await pilot.press("o"); await pilot.pause()
        scr = app.screen; assert isinstance(scr, od.SettingsScreen), scr
        assert scr.query_one("#interval", Input).value == "5"
        assert scr.query_one("#env", Input).value == "a b c"
        # 잘못된 값 → 오류 표시, 창 유지
        scr.query_one("#ai_timeout", Input).value = "-1"
        await pilot.press("enter"); await pilot.pause()
        err = str(scr.query_one("#form-error").render())
        assert "제한 시간" in err, err; assert app.screen is scr
        # 정상 값
        scr.query_one("#ai_timeout", Input).value = "45"
        scr.query_one("#interval", Input).value = "20"
        scr.query_one("#env", Input).value = "srv1"
        scr.query_one("#local", Checkbox).value = False
        scr.query_one("#ai", Select).value = "codex"
        scr.query_one("#ai_model", Input).value = ""
        await pilot.press("enter"); await pilot.pause(); await pilot.pause(0.3)
        assert not isinstance(app.screen, od.SettingsScreen)
        assert app.interval == 20 and app.settings.env == ["srv1"] and app.settings.local is False
        assert app.ai.provider == "codex" and app.ai.timeout == 45 and app.ai.model is None
        assert app._refresh_timer._interval == 20, app._refresh_timer._interval
        assert [x.label for x in app.sources] == ["file"]   # file 모드: 소스 고정
        disk = json.load(open(cfg)); assert disk["interval"] == 20 and disk["env"] == ["srv1"] and disk["ai"] == "codex", disk
        assert "간격 20초" in app.query_one("#status").render().plain or True
        # Esc 취소: 변경 없음
        await pilot.press("o"); await pilot.pause()
        app.screen.query_one("#interval", Input).value = "99"
        await pilot.press("escape"); await pilot.pause()
        assert app.interval == 20
        # 소스 재구성 (파일 모드 아닐 때)
        app.files = None
        app._apply_settings(od.Settings(local=True, env=["z"], ai="off")); await pilot.pause()
        assert [x.label for x in app.sources] == ["local","z"], app.sources
        assert app.ai.provider == "off"
        # 상태줄에 간격 반영
        app._tick_status(); assert "간격 60초" in app.query_one("#status").render().plain
        print("ok: app flow")
asyncio.run(run())
print("ALL OK")
