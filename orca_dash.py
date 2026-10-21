#!/usr/bin/env python3
"""Orca 에이전트 상태 TUI 대시보드.

`orca worktree ps --json` 결과를 주기적으로 읽어 표로 보여준다.
Orca 1.4.230 출력 구조 기준으로 작성.

키:
  p / Enter  선택한 에이전트에게 프롬프트 보내기
             (모달에서 Enter 전송 · Ctrl+J 또는 Shift+Enter 줄바꿈 · Esc 취소)
  Ctrl+G     프롬프트 창에서 AI(로컬 claude -p 또는 codex exec)가 초안 작성.
             메모를 적고 누르면 초안 생성, 다시 누르면 현재 내용을 다듬기. --ai 옵션 참고
  o          옵션 보기/수정 (조회 간격·소스·AI). 저장하면 설정 파일에 쓰고 바로 적용
  r 새로고침 · f 필터 · e 빈 워크트리 · q 종료
  macOS 에서는 메인 화면이 앞에 있을 때 입력 소스를 영문(ABC)으로 자동 전환하고, 프롬프트·옵션 창을
  열거나 다른 앱으로 가거나 종료하면 원래 입력 소스로 되돌린다 (옵션에서 끌 수 있음). 메인 화면에서 Caps Lock·
  ⌃Space 로 한글로 바꿔도 1초 안에 다시 영문이 된다. 그래서 한글 상태에서도 단축키가 바로 듣는다. 자동 전환이 꺼져 있거나 안 되는 환경에서는 같은 자리의 두벌식 자모(ㅔ=p · ㅐ=o ·
  ㄱ=r · ㄹ=f · ㄷ=e · ㅂ=q)로도 동작하되, IME 가 자모를 조합 중 상태로 붙잡으면 Space/Enter 로 확정해야 한다.

설정 파일: ~/.config/orca-dash/config.json (--config 로 변경). 명령줄 인자가 있으면 그 값이 우선.

사용:
  python3 orca_dash.py                         # 로컬, 60초 간격
  python3 orca_dash.py --interval 30
  python3 orca_dash.py --ssh macmini-1         # 원격: ssh 로 원격 orca 실행 (미검증)
  python3 orca_dash.py --env <서버명>          # 원격: 페어링 서버 (미검증)
  python3 orca_dash.py --file sample.json      # 저장된 JSON 으로 화면 확인
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual import events
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (Button, Checkbox, DataTable, Footer, Header, Input, Label, Select,
                             Static, TextArea)
from textual.worker import Worker, WorkerState

# 상태 표시: (라벨, 색, 정렬 우선순위 — 작을수록 위)
STATE_STYLE = {
    "blocked": ("막힘", "bold red", 0),
    "waiting": ("입력 대기", "bold yellow", 1),
    "permission": ("권한 대기", "bold yellow", 1),
    "working": ("작업 중", "cyan", 2),
    "done": ("완료", "green", 3),
    "idle": ("유휴", "dim", 4),
    None: ("에이전트 없음", "dim", 5),
}
FILTERS = ["전체", "주의 필요", "진행 중"]

# 두벌식 자판에서 영문 키와 같은 자리의 자모. 한글 입력 상태에서는 터미널이 키코드가 아니라
# 조합된 글자를 넘기므로, 단축키마다 같은 자리의 자모를 함께 묶어 어느 입력 상태에서도 동작하게 한다.
HANGUL_2SET = dict(zip("qwertyuiopasdfghjklzxcvbnm",
                       "ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔㅁㄴㅇㄹㅎㅗㅓㅏㅣㅋㅌㅊㅍㅠㅜㅡ"))


def key_binding(letter: str, action: str, description: str, **kwargs) -> Binding:
    """영문 글자 + 같은 자리의 한글 자모를 한 바인딩으로. Footer 에는 영문만 표시."""
    keys = letter + ("," + HANGUL_2SET[letter] if letter in HANGUL_2SET else "")
    return Binding(keys, action, description, key_display=letter, **kwargs)


@dataclass
class Source:
    label: str
    orca: str = "orca"
    env: str | None = None   # --environment <selector>
    host: str | None = None  # --host <selector>
    ssh: str | None = None   # ssh 접속 대상에서 orca 직접 실행
    file: str | None = None  # 저장된 JSON (테스트용, 전송 불가)

    def cmd(self, *args: str) -> list[str]:
        """이 소스에 대해 `orca <args> --json` 을 실행할 명령줄."""
        if self.ssh:
            remote = " ".join(shlex.quote(x) for x in ["orca", *args, "--json"])
            return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", self.ssh, remote]
        c = [self.orca, *args]
        if self.env:
            c += ["--environment", self.env]
        if self.host:
            c += ["--host", self.host]
        return c + ["--json"]


class OrcaError(Exception):
    pass


@dataclass
class Row:
    key: str
    source: str          # Source.label
    pane_key: str | None  # 에이전트 터미널 식별자 (tabId:leafId), 없으면 전송 불가
    host: str
    path: str
    repo: str
    worktree: str
    branch: str
    agent_type: str
    state: str | None
    main_state: str | None
    wait: str
    started_at: float | None
    updated_at: float | None
    tool: str
    summary: str
    detail: str
    unread: bool
    prompt: str = ""        # 에이전트에게 준 원래 지시 (AI 초안 컨텍스트용)
    last_message: str = ""  # 마지막 응답
    tool_input: str = ""


def _first_line(text: str | None, limit: int = 80) -> str:
    if not text:
        return ""
    for line in text.splitlines():
        line = line.strip().lstrip("#*- ").strip()
        if line:
            return line[:limit] + ("…" if len(line) > limit else "")
    return ""


def _ago(ms: float | None) -> str:
    if not ms:
        return "-"
    sec = max(0, time.time() - ms / 1000)
    if sec < 60:
        return f"{int(sec)}초"
    if sec < 3600:
        return f"{int(sec // 60)}분"
    if sec < 86400:
        return f"{sec / 3600:.1f}시간"
    return f"{sec / 86400:.1f}일"


def _clock(ms: float | None) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime("%m-%d %H:%M") if ms else "-"


def _wait_text(agent: dict) -> str:
    w = agent.get("agentWait")
    if not w:
        return ""
    if isinstance(w, dict):
        return str(w.get("reason") or w.get("kind") or w.get("state") or "대기")
    return str(w)


def parse_ps(payload: dict, source_label: str) -> list[Row]:
    result = payload.get("result", payload)
    rows: list[Row] = []
    for wt in result.get("worktrees", []):
        host = wt.get("hostId") or source_label
        if host == "local" and source_label != "local":
            host = source_label
        base = dict(
            source=source_label,
            host=host,
            path=wt.get("path", ""),
            repo=wt.get("repo", ""),
            worktree=wt.get("displayName") or wt.get("path", "").rsplit("/", 1)[-1],
            branch=(wt.get("branch") or "(detached)").removeprefix("refs/heads/"),
            unread=bool(wt.get("unread")),
        )
        comment = wt.get("comment") or ""
        head = (
            f"[b]{base['repo']}[/] / {base['worktree']}  ({base['branch']})\n"
            f"경로: {wt.get('path', '')}\n"
            f"워크스페이스 상태: {wt.get('workspaceStatus', '-')} · 워크트리 상태: {wt.get('status', '-')}"
            + (f"\n코멘트: {comment}" if comment else "")
        )
        agents = wt.get("agents") or []
        if not agents:
            rows.append(Row(
                key=f"{source_label}|{wt.get('worktreeId')}", pane_key=None, agent_type="-", state=None,
                main_state=None, wait="", started_at=None,
                updated_at=wt.get("lastActivityAt"), tool="", summary=comment,
                detail=head, **base,
            ))
            continue
        for ag in agents:
            last = ag.get("lastAssistantMessage") or ""
            prompt = ag.get("prompt") or ""
            tool = ag.get("toolName") or ""
            detail = (
                head
                + f"\n\n[b]지시[/]\n{prompt or '-'}"
                + (f"\n\n[b]현재 도구[/] {tool}: {ag.get('toolInput') or ''}" if tool else "")
                + f"\n\n[b]마지막 응답[/]\n{last or '-'}"
            )
            rows.append(Row(
                key=f"{source_label}|{wt.get('worktreeId')}|{ag.get('paneKey')}",
                pane_key=ag.get("paneKey"),
                agent_type=ag.get("agentType", "?"),
                state=ag.get("state"),
                main_state=(ag.get("mainAgent") or {}).get("state"),
                wait=_wait_text(ag) or ("중단됨" if ag.get("interrupted") else ""),
                started_at=ag.get("stateStartedAt"),
                updated_at=ag.get("updatedAt"),
                tool=tool,
                summary=_first_line(last) or _first_line(prompt),
                detail=detail,
                prompt=prompt, last_message=last, tool_input=str(ag.get("toolInput") or ""),
                **base,
            ))
    return rows


async def run_orca(src: Source, *args: str, timeout: float = 30) -> dict:
    """소스에서 `orca <args> --json` 을 실행해 result 딕셔너리를 돌려준다. 실패 시 OrcaError."""
    if src.file:
        raise OrcaError(f"{src.label}: 파일 소스에서는 '{' '.join(args)}' 를 실행할 수 없음")
    try:
        proc = await asyncio.create_subprocess_exec(
            *src.cmd(*args), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except FileNotFoundError:
        raise OrcaError(f"{src.label}: orca 명령을 찾을 수 없음 (Settings에서 CLI 등록 필요)")
    except asyncio.TimeoutError:
        raise OrcaError(f"{src.label}: {int(timeout)}초 내 응답 없음")
    raw = out.decode(errors="replace")
    if proc.returncode != 0:
        msg = (err or out).decode(errors="replace").strip().splitlines()
        raise OrcaError(f"{src.label}: 실행 실패 — {msg[-1] if msg else proc.returncode}")
    try:
        payload = json.loads(raw[raw.index("{"):])  # 앞에 버전 줄 등이 있어도 허용
    except (json.JSONDecodeError, ValueError) as e:
        raise OrcaError(f"{src.label}: JSON 해석 실패 — {e}")
    if payload.get("ok") is False:
        raise OrcaError(f"{src.label}: Orca 오류 — {payload.get('error')}")
    return payload.get("result", payload)


async def fetch(src: Source) -> tuple[list[Row], str | None]:
    """한 소스 조회. (행 목록, 오류 메시지)"""
    try:
        if src.file:
            with open(src.file, encoding="utf-8") as f:
                raw = f.read()
            payload = json.loads(raw[raw.index("{"):])
            if payload.get("ok") is False:
                return [], f"{src.label}: Orca 오류 — {payload.get('error')}"
            result = payload.get("result", payload)
        else:
            result = await run_orca(src, "worktree", "ps")
        return parse_ps({"result": result}, src.label), None
    except OrcaError as e:
        return [], str(e)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        return [], f"{src.label}: 읽기 실패 — {e}"


async def find_terminal(src: Source, pane_key: str) -> str:
    """에이전트 paneKey(tabId:leafId)에 해당하는 라이브 터미널 핸들을 찾는다."""
    terminals = (await run_orca(src, "terminal", "list")).get("terminals", [])
    leaf = pane_key.rsplit(":", 1)[-1]
    exact = [t for t in terminals if f"{t.get('tabId')}:{t.get('leafId')}" == pane_key]
    hit = exact or [t for t in terminals if t.get("leafId") == leaf]
    if not hit:
        raise OrcaError("라이브 터미널을 찾지 못함 (잠든 워크스페이스이거나 채팅 UI 에이전트)")
    t = hit[0]
    if t.get("writable") is False:
        raise OrcaError(f"터미널 {t.get('handle')} 에 쓸 수 없음 (connected={t.get('connected')})")
    return t["handle"]


async def send_prompt(src: Source, pane_key: str, text: str) -> str:
    """선택한 에이전트 터미널에 프롬프트 + Enter 를 보낸다. 결과 요약 문자열 반환."""
    handle = await find_terminal(src, pane_key)
    result = await run_orca(src, "terminal", "send", "--terminal", handle, "--text", text,
                            "--enter", "--wait-submit", "5", timeout=40)
    send = result.get("send") or {}
    if not send.get("accepted"):
        raise OrcaError(f"입력이 수락되지 않음: {result}")
    stages = (send.get("prompt") or {}).get("stages") or []
    if "turn_started" in stages:
        return "전송됨 · 에이전트 턴 시작 확인"
    warn = (result.get("warnings") or [""])[0]
    return "입력 수락됨 (제출 확인은 안 됨)" + (f" — {warn}" if warn else "")


# ---------------------------------------------------------------------------
# AI 초안 작성: 로컬 claude -p / codex exec 로 프롬프트를 대신 써 준다.
# ---------------------------------------------------------------------------
@dataclass
class AIConfig:
    provider: str                 # "claude" | "codex" | "off"
    model: str | None = None
    timeout: float = 60
    include_context: bool = True  # 에이전트 상황(지시/마지막 응답 등)을 초안 모델에 전달할지

    @property
    def enabled(self) -> bool:
        return self.provider in ("claude", "codex")

    @classmethod
    def from_args(cls, provider: str, model: str | None, timeout: float | None, context: bool) -> "AIConfig":
        if provider == "auto":
            provider = "claude" if shutil.which("claude") else "codex" if shutil.which("codex") else "off"
        elif provider != "off" and not shutil.which(provider):
            raise ConfigError(f"AI 공급자 {provider}: 실행 파일을 PATH 에서 찾을 수 없습니다")
        if model is None and provider == "claude":
            model = "haiku"  # 5초 안팎, 회당 약 $0.003
        if timeout is None:
            timeout = 90 if provider == "codex" else 60
        return cls(provider=provider, model=model, timeout=timeout, include_context=context)


class DraftError(Exception):
    pass


DRAFT_SYSTEM = """\
너는 코딩 에이전트(Claude Code, Codex 등)에게 보낼 프롬프트를 대신 작성하는 도우미다.
아래 '에이전트 상황'과 '사용자 메모'를 바탕으로, 에이전트에게 그대로 보낼 프롬프트 본문만 한국어로 출력한다.

규칙:
- 서문, 설명, 제목, 코드 펜스, 따옴표 없이 프롬프트 본문만 출력한다.
- 1~6문장으로 구체적이고 바로 실행 가능하게 쓴다. 파일 경로나 명령은 상황에 있는 것만 쓴다.
- 에이전트가 '입력 대기'나 '권한 대기' 상태면 마지막 응답의 질문이나 요청에 답하는 내용으로 쓴다.
- 사용자 메모가 비어 있으면 상황에 맞는 다음 지시를 제안한다.
- '기존 초안'이 있으면 그것을 사용자 메모의 의도대로 다듬어 완성본만 다시 출력한다.
"""


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "\n…(이하 생략)"


def build_draft_request(row: Row, note: str, current: str, include_context: bool) -> str:
    label = STATE_STYLE.get(row.state, (row.state or "?",))[0]
    lines = ["[에이전트 상황]",
             f"저장소/워크트리/브랜치: {row.repo} / {row.worktree} ({row.branch})",
             f"에이전트: {row.agent_type} · 상태: {label}" + (f" · 대기 사유: {row.wait}" if row.wait else "")]
    if include_context:
        if row.path:
            lines.append(f"경로: {row.path}")
        lines += ["", "[원래 지시]", _clip(row.prompt, 1500) or "-"]
        if row.tool:
            lines += ["", f"[현재 도구] {row.tool}", _clip(row.tool_input, 300)]
        lines += ["", "[마지막 응답]", _clip(row.last_message, 2000) or "-"]
    lines += ["", "[사용자 메모]", note.strip() or "(없음 — 상황에 맞는 다음 지시를 제안)"]
    if current.strip():
        lines += ["", "[기존 초안]", current.strip()]
    return "\n".join(lines)


def strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
    if t.rstrip().endswith("```"):
        t = t.rstrip()[:-3]
    return t.strip()


async def _run_cli(cmd: list[str], stdin: str, cwd: str | None, timeout: float) -> str:
    """서브프로세스를 실행하고 stdout 을 돌려준다.

    취소/타임아웃 시 CLI 가 띄운 하위 프로세스까지 함께 죽도록 새 세션(프로세스 그룹)으로
    실행하고 그룹 전체에 SIGKILL 을 보낸다.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=cwd, start_new_session=True,
        )
    except FileNotFoundError:
        raise DraftError(f"{cmd[0]} 실행 파일을 찾을 수 없음")
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin.encode()), timeout=timeout)
    except asyncio.TimeoutError:
        raise DraftError(f"{int(timeout)}초 내 응답 없음")
    finally:
        if proc.returncode is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
    if proc.returncode != 0:
        msg = (err or out).decode(errors="replace").strip().splitlines()
        raise DraftError(f"{cmd[0]} 실패 — {msg[-1] if msg else proc.returncode}")
    return out.decode(errors="replace")


async def draft_prompt(cfg: AIConfig, row: Row, note: str, current: str, cwd: str | None) -> str:
    """AI 로 프롬프트 초안을 만든다. 실패 시 DraftError."""
    request = build_draft_request(row, note, current, cfg.include_context)
    if cfg.provider == "claude":
        cmd = ["claude", "-p", "--no-session-persistence", "--tools", "", "--output-format", "json",
               "--system-prompt", DRAFT_SYSTEM]
        if cfg.model:
            cmd += ["--model", cfg.model]
        raw = await _run_cli(cmd, request, cwd, cfg.timeout)
        try:
            data = json.loads(raw[raw.index("{"):])
        except (ValueError, json.JSONDecodeError):
            raise DraftError(f"claude 응답 해석 실패: {raw[:200]}")
        if data.get("is_error"):
            raise DraftError(f"claude: {data.get('result') or data.get('error') or '오류'}")
        text = strip_fences(str(data.get("result") or ""))
    elif cfg.provider == "codex":
        fd, out_path = tempfile.mkstemp(prefix="orca-dash-draft-", suffix=".txt")
        os.close(fd)
        try:
            cmd = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
                   "-o", out_path]
            if cwd:
                cmd += ["-C", cwd]
            if cfg.model:
                cmd += ["-m", cfg.model]
            cmd.append("-")  # 프롬프트는 stdin
            await _run_cli(cmd, DRAFT_SYSTEM + "\n\n" + request, cwd, cfg.timeout)
            with open(out_path, encoding="utf-8", errors="replace") as f:
                text = strip_fences(f.read())
        finally:
            try:
                os.unlink(out_path)
            except OSError:
                pass
    else:
        raise DraftError("AI 초안 기능이 꺼져 있음 (--ai claude|codex)")
    if not text:
        raise DraftError("빈 응답")
    return text


class PromptArea(TextArea):
    """Enter 는 전송, Ctrl+J / Shift+Enter / Alt+Enter 는 줄바꿈.

    Ctrl+S 같은 조합은 터미널 앱이나 tmux 가 먼저 가로채는 경우가 많아
    어느 터미널에서나 확실히 전달되는 Enter 를 전송 키로 쓴다.
    """

    NEWLINE_KEYS = ("ctrl+j", "shift+enter", "alt+enter")

    class Submit(Message):
        pass

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.post_message(self.Submit())
            return
        if event.key in self.NEWLINE_KEYS:
            event.stop()
            event.prevent_default()
            start, end = self.selection
            self._replace_via_keyboard("\n", start, end)
            return
        await super()._on_key(event)


class PromptScreen(ModalScreen[str | None]):
    """선택한 에이전트에게 보낼 프롬프트를 입력받는 모달."""

    DEFAULT_CSS = """
    PromptScreen { align: center middle; }
    PromptScreen > Vertical {
        width: 90%; max-width: 120; height: auto;
        border: thick $primary; background: $surface; padding: 1 2;
    }
    PromptScreen #target { color: $text-muted; }
    PromptScreen #ai-status { color: $warning; height: 1; margin-bottom: 1; }
    PromptScreen TextArea { height: 10; }
    PromptScreen Horizontal { height: auto; margin-top: 1; align-horizontal: right; }
    PromptScreen Button { margin-left: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "취소"),
        Binding("ctrl+g", "draft", "AI 초안", priority=True),
        Binding("ctrl+s", "send", "보내기", show=False, priority=True),  # 터미널이 전달해 주는 경우에만
    ]

    def __init__(self, row: Row, ai: AIConfig | None = None, cwd: str | None = None):
        super().__init__()
        self.row = row
        self.ai = ai if ai and ai.enabled else None
        self.cwd = cwd
        self.note: str | None = None        # AI 에 준 사용자 메모 (다듬기 때 재사용)
        self.last_draft: str | None = None  # 마지막으로 받은 초안
        self.draft_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        r = self.row
        keys = "Enter 전송 · Ctrl+J 줄바꿈" + (" · Ctrl+G AI 초안" if self.ai else "") + " · Esc 취소"
        with Vertical():
            yield Label(f"프롬프트 보내기  ({keys})", id="title")
            yield Label(f"대상: [{r.host}] {r.repo} / {r.worktree} ({r.branch}) · {r.agent_type}"
                        + (f" · 현재 {r.tool}" if r.tool else ""), id="target")
            yield Label("", id="ai-status")
            yield PromptArea(id="prompt")
            with Horizontal():
                yield Button("취소 (Esc)", id="cancel")
                if self.ai:
                    yield Button(f"AI 작성 (Ctrl+G · {self.ai.provider})", id="draft")
                yield Button("보내기 (Enter)", id="send", variant="primary")

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "draft" and not self.ai:
            return False  # --ai off: Footer 에서도 Ctrl+G 안내를 숨긴다
        return True

    # --- AI 초안 ---------------------------------------------------------
    @property
    def drafting(self) -> bool:
        return self.draft_worker is not None and self.draft_worker.is_running

    def _set_ai_status(self, text: str) -> None:
        self.query_one("#ai-status", Label).update(text)

    def action_draft(self) -> None:
        if not self.ai:
            self.notify("AI 초안 기능이 꺼져 있습니다. --ai claude 또는 --ai codex 로 실행하세요.",
                        severity="warning")
            return
        text = self.query_one(TextArea).text
        if self._looks_like_draft(text):
            note, current, what = self.note or "", text, "다듬는 중"   # 받은 초안(또는 편집본)을 다듬기
        else:
            note, current, what = text, "", "초안 작성 중"              # 메모로 새 초안
            self.note = note
        self._set_ai_status(f"AI {what}… ({self.ai.provider}, Esc 중단 · Ctrl+G 다시 시작)")
        self.draft_worker = self.run_worker(
            self._draft(note, current), group="draft", exclusive=True, exit_on_error=False,
        )

    def _looks_like_draft(self, text: str) -> bool:
        """현재 입력이 마지막 AI 초안(또는 그 편집본)이면 True. 지우고 새로 쓴 메모면 False."""
        if not self.last_draft or not text.strip():
            return False
        if text.strip() == self.last_draft.strip():
            return True
        return difflib.SequenceMatcher(None, text, self.last_draft).ratio() >= 0.5

    async def _draft(self, note: str, current: str) -> str:
        assert self.ai is not None
        return await draft_prompt(self.ai, self.row, note, current, self.cwd)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.group != "draft" or event.worker is not self.draft_worker:
            return
        if event.state == WorkerState.SUCCESS:
            draft = str(event.worker.result or "")
            area = self.query_one(TextArea)
            area.load_text(draft)
            area.move_cursor(area.document.end)
            self.last_draft = draft
            self._set_ai_status("AI 초안을 넣었습니다. 수정 후 Enter 로 전송 · Ctrl+G 로 다듬기")
        elif event.state == WorkerState.ERROR:
            err = event.worker.error
            self._set_ai_status("")
            self.notify(f"{err}", title="AI 초안 실패", severity="error", timeout=10)
        elif event.state == WorkerState.CANCELLED:
            self._set_ai_status("AI 초안 중단됨")

    def _cancel_draft(self) -> bool:
        if self.drafting and self.draft_worker is not None:
            self.draft_worker.cancel()
            return True
        return False

    # --- 전송/취소 -------------------------------------------------------
    def action_send(self) -> None:
        if self.drafting:
            self.notify("AI 가 작성 중입니다. 기다리거나 Esc 로 중단하세요.", severity="warning")
            return
        text = self.query_one(TextArea).text.strip()
        if not text:
            self.notify("보낼 내용이 비어 있습니다.", severity="warning")
            return
        self.dismiss(text)

    def action_cancel(self) -> None:
        if self._cancel_draft():
            return  # 생성만 중단, 창은 유지
        self.dismiss(None)

    def on_prompt_area_submit(self, event: PromptArea.Submit) -> None:
        self.action_send()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            self.action_send()
        elif event.button.id == "draft":
            self.action_draft()
        else:
            self._cancel_draft()
            self.dismiss(None)


# ---------------------------------------------------------------------------
# 설정: ~/.config/orca-dash/config.json 에 저장하고, 대시보드에서 o 키로 보고 고친다.
# 명령줄 인자로 준 값은 파일 값보다 우선한다.
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".config", "orca-dash", "config.json")
AI_CHOICES = ["auto", "claude", "codex", "off"]


class ConfigError(Exception):
    pass


def _split_list(text: str) -> list[str]:
    """쉼표·공백으로 나열한 값을 리스트로."""
    return [t for t in text.replace(",", " ").split() if t]


@dataclass
class Settings:
    interval: int = 60                              # 조회 간격(초), 최소 5
    orca: str = "orca"                              # orca 실행 파일
    local: bool = True                              # 로컬 Orca 조회
    env: list[str] = field(default_factory=list)    # 페어링된 Remote Orca Server 이름들
    host: list[str] = field(default_factory=list)   # orca --host 선택자들
    ssh: list[str] = field(default_factory=list)    # ssh 대상들 (원격에서 orca 직접 실행)
    ai: str = "auto"                                # auto | claude | codex | off
    ai_model: str = ""                              # 빈 값이면 공급자 기본
    ai_timeout: float | None = None                 # None 이면 공급자 기본
    ai_context: bool = True                         # 에이전트 상황을 초안 모델에 전달
    auto_abc: bool = True                           # macOS: 메인 화면에서 입력 소스를 영문으로 자동 전환

    FIELDS = ("interval", "orca", "local", "env", "host", "ssh",
              "ai", "ai_model", "ai_timeout", "ai_context", "auto_abc")

    @classmethod
    def load(cls, path: str) -> "Settings":
        """파일이 없으면 기본값. 모르는 키는 무시한다."""
        s = cls()
        if not os.path.exists(path):
            return s
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            raise ConfigError(f"설정 파일을 읽을 수 없습니다 ({path}): {e}") from e
        if not isinstance(data, dict):
            raise ConfigError(f"설정 파일 형식이 잘못되었습니다 ({path}): 최상위가 객체가 아님")
        for k in cls.FIELDS:
            if k in data:
                setattr(s, k, data[k])
        errors = s.validate()
        if errors:
            raise ConfigError(f"설정 파일 값이 잘못되었습니다 ({path}): " + "; ".join(errors))
        return s

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({k: getattr(self, k) for k in self.FIELDS}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)

    def validate(self) -> list[str]:
        """값의 타입을 맞추고 문제 목록을 돌려준다. 비어 있으면 정상."""
        errs: list[str] = []
        try:
            self.interval = max(5, int(self.interval))
        except (TypeError, ValueError):
            errs.append("조회 간격은 정수(초)")
        self.orca = str(self.orca or "").strip() or "orca"
        self.local = bool(self.local)
        for k in ("env", "host", "ssh"):
            v = getattr(self, k)
            if isinstance(v, str):
                v = _split_list(v)
            setattr(self, k, [str(x).strip() for x in (v or []) if str(x).strip()])
        if self.ai not in AI_CHOICES:
            errs.append(f"AI 공급자는 {'/'.join(AI_CHOICES)} 중 하나")
        self.ai_model = str(self.ai_model or "").strip()
        if self.ai_timeout in (None, ""):
            self.ai_timeout = None
        else:
            try:
                self.ai_timeout = float(self.ai_timeout)
                if self.ai_timeout <= 0:
                    errs.append("AI 제한 시간은 0보다 큰 수(초)")
            except (TypeError, ValueError):
                errs.append("AI 제한 시간은 수(초) 또는 빈 값")
        self.ai_context = bool(self.ai_context)
        self.auto_abc = bool(self.auto_abc)
        if not self.local and not (self.env or self.host or self.ssh):
            errs.append("조회할 소스가 없음 (로컬을 끄면 env/host/ssh 중 하나 필요)")
        return errs

    def apply_args(self, args: argparse.Namespace) -> list[str]:
        """명령줄에서 준 값으로 덮어쓰고, 덮어쓴 항목 이름을 돌려준다."""
        over: list[str] = []
        for k, v in [("interval", args.interval), ("orca", args.orca), ("env", args.env),
                     ("host", args.host), ("ssh", args.ssh), ("ai", args.ai),
                     ("ai_model", args.ai_model), ("ai_timeout", args.ai_timeout)]:
            if v is not None:
                setattr(self, k, v)
                over.append(k)
        if args.no_local:
            self.local = False
            over.append("local")
        if args.ai_context is not None:
            self.ai_context = args.ai_context == "on"
            over.append("ai_context")
        return over

    def sources(self) -> list[Source]:
        out: list[Source] = []
        if self.local:
            out.append(Source(label="local", orca=self.orca))
        out += [Source(label=e, orca=self.orca, env=e) for e in self.env]
        out += [Source(label=h, orca=self.orca, host=h) for h in self.host]
        out += [Source(label=t, ssh=t) for t in self.ssh]
        return out

    def ai_config(self) -> AIConfig:
        return AIConfig.from_args(self.ai, self.ai_model or None, self.ai_timeout, self.ai_context)


class InputSource:
    """macOS 키보드 입력 소스(한글/영문) 조회·전환. Carbon TIS API 를 ctypes 로 호출한다.

    터미널 앱은 키코드를 받지 못하고 IME 가 조합한 글자만 받으므로, 한글 상태에서 q 같은 단축키는
    자모 조합 중 상태에 머물러 동작하지 않는다. 메인 화면이 앞에 있을 때만 영문으로 바꿔 두면 해결된다.
    macOS 가 아니거나 API 를 못 쓰면 available=False 로 조용히 비활성화된다.

    영문(키보드 레이아웃)으로의 전환은 TIS 호출만으로 되지만, 한글 같은 입력기(IM)로 되돌리는 것은
    메뉴바 아이콘만 바뀌고 적용되지 않는 macOS 버그가 있다. 그래서 보조 실행 파일(orca-dash-im,
    app/imselect.swift · macism 과 같은 인터페이스)이 있으면 그것으로 전환한다. 보조 도구는 전환 직후
    아주 작은 창을 잠깐 띄워 포커스를 가져갔다 돌려주는 방식으로 적용을 강제한다.
    """
    ENGLISH_LANG = "en"
    HELPER_NAMES = ("orca-dash-im", "macism")

    def __init__(self) -> None:
        self.available = False
        self.english: int | None = None
        self.helper: str | None = None
        if sys.platform != "darwin":
            return
        self.helper = self._find_helper()
        try:
            import ctypes
            import ctypes.util
            self._ct = ctypes
            cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
            tis = ctypes.CDLL(ctypes.util.find_library("Carbon"))
            cf.CFStringCreateWithCString.restype = ctypes.c_void_p
            cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
            cf.CFStringGetCString.restype = ctypes.c_bool
            cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
            cf.CFRelease.argtypes = [ctypes.c_void_p]
            cf.CFRunLoopRunInMode.restype = ctypes.c_int32
            cf.CFRunLoopRunInMode.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_bool]
            self._runloop_mode = ctypes.c_void_p.in_dll(cf, "kCFRunLoopDefaultMode")
            tis.TISCopyCurrentKeyboardInputSource.restype = ctypes.c_void_p
            tis.TISCopyInputSourceForLanguage.restype = ctypes.c_void_p
            tis.TISCopyInputSourceForLanguage.argtypes = [ctypes.c_void_p]
            tis.TISGetInputSourceProperty.restype = ctypes.c_void_p
            tis.TISGetInputSourceProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            tis.TISSelectInputSource.restype = ctypes.c_int32
            tis.TISSelectInputSource.argtypes = [ctypes.c_void_p]
            self._cf, self._tis = cf, tis
            self._utf8 = 0x08000100
            self._k_id = ctypes.c_void_p.in_dll(tis, "kTISPropertyInputSourceID")
            lang = cf.CFStringCreateWithCString(None, self.ENGLISH_LANG.encode(), self._utf8)
            self.english = tis.TISCopyInputSourceForLanguage(lang)  # 보통 com.apple.keylayout.ABC
            cf.CFRelease(lang)
            self.english_id = self._id_of(self.english) if self.english else None
            self.available = bool(self.english_id)
        except Exception:
            self.available = False

    @classmethod
    def _find_helper(cls) -> str | None:
        """ORCA_DASH_IM 환경 변수 → 저장소 bin/ → PATH 순으로 보조 도구를 찾는다."""
        cand = [os.environ.get("ORCA_DASH_IM", ""),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "orca-dash-im")]
        for c in cand:
            if c and os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        for name in cls.HELPER_NAMES:
            found = shutil.which(name)
            if found:
                return found
        return None

    def _id_of(self, ref: int) -> str | None:
        prop = self._tis.TISGetInputSourceProperty(ref, self._k_id)
        if not prop:
            return None
        buf = self._ct.create_string_buffer(256)
        return buf.value.decode() if self._cf.CFStringGetCString(prop, buf, 256, self._utf8) else None

    def current(self, *, fresh: bool = True) -> str | None:
        """현재 입력 소스 ID (예: com.apple.inputmethod.Korean.2SetKorean).

        TIS 의 '현재값'은 프로세스별 캐시라 다른 프로세스가 바꾼 것을 늦게 보거나 못 볼 수 있다.
        fresh 이면 보조 도구를 새 프로세스로 띄워 정확한 값을 읽는다(약 70ms). 1초마다 도는 감시처럼
        자주 부르는 곳은 fresh=False 로 프로세스 안에서 읽는다(런루프를 잠깐 돌리면 외부 변경도 들어옴, 약 10ms).
        """
        if not self.available:
            return None
        if fresh and self.helper:
            try:
                out = subprocess.run([self.helper], capture_output=True, text=True, timeout=2).stdout.strip()
                if out:
                    return out
            except (OSError, subprocess.SubprocessError):
                pass
        self._settle(0.01)
        try:
            ref = self._tis.TISCopyCurrentKeyboardInputSource()
            if not ref:
                return None
            try:
                return self._id_of(ref)
            finally:
                self._cf.CFRelease(ref)
        except Exception:
            return None

    def _settle(self, seconds: float = 0.05) -> None:
        """런루프를 잠깐 돌린다. 한글 같은 입력기(IM)로의 전환은 런루프가 돌아야 시스템에 반영되고,
        다른 프로세스가 바꾼 현재값 알림도 이때 들어온다."""
        try:
            self._cf.CFRunLoopRunInMode(self._runloop_mode, seconds, False)
        except Exception:
            pass

    def select_english(self) -> bool:
        if not self.available:
            return False
        ok = self._tis.TISSelectInputSource(self.english) == 0
        self._settle()
        return ok

    def select(self, source_id: str) -> bool:
        """ID 로 입력 소스를 고른다. 보조 도구가 있으면 그것으로(IM 전환이 실제 적용됨), 없으면 TIS 로."""
        if not self.available or not source_id:
            return False
        if source_id == self.english_id:
            return self.select_english()
        if self.helper:
            try:
                # 대시보드가 SIGHUP 으로 죽는 중에도 끝까지 돌도록 별도 세션으로 띄운다.
                subprocess.Popen([self.helper, source_id], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                return True
            except OSError:
                pass
        return self._select_tis(source_id)

    def _select_tis(self, source_id: str) -> bool:
        try:
            cf, tis, ct = self._cf, self._tis, self._ct
            tis.TISCreateInputSourceList.restype = ct.c_void_p
            tis.TISCreateInputSourceList.argtypes = [ct.c_void_p, ct.c_bool]
            cf.CFArrayGetCount.restype = ct.c_long
            cf.CFArrayGetCount.argtypes = [ct.c_void_p]
            cf.CFArrayGetValueAtIndex.restype = ct.c_void_p
            cf.CFArrayGetValueAtIndex.argtypes = [ct.c_void_p, ct.c_long]
            lst = tis.TISCreateInputSourceList(None, False)
            if not lst:
                return False
            try:
                for i in range(cf.CFArrayGetCount(lst)):
                    ref = cf.CFArrayGetValueAtIndex(lst, i)
                    if self._id_of(ref) == source_id:
                        ok = tis.TISSelectInputSource(ref) == 0
                        self._settle()
                        return ok
            finally:
                cf.CFRelease(lst)
        except Exception:
            pass
        return False


class SettingsScreen(ModalScreen[Settings | None]):
    """옵션을 보고 고치는 모달. 저장하면 설정 파일에 쓰고 바로 적용된다."""

    DEFAULT_CSS = """
    SettingsScreen { align: center middle; }
    SettingsScreen > Vertical {
        width: 90%; max-width: 100; height: 100%; max-height: 50;
        border: thick $primary; background: $surface; padding: 1 2;
    }
    SettingsScreen #path, SettingsScreen #override { color: $text-muted; height: auto; }
    SettingsScreen #form { height: 1fr; }
    SettingsScreen .section { color: $accent; text-style: bold; margin-top: 1; }
    SettingsScreen .row { height: 3; }
    SettingsScreen .row Label { width: 20; padding-top: 1; }
    SettingsScreen .row Input, SettingsScreen .row Select, SettingsScreen .row Checkbox { width: 1fr; }
    SettingsScreen #form-error { color: $error; height: auto; }
    SettingsScreen #buttons { height: auto; margin-top: 1; align-horizontal: right; }
    SettingsScreen Button { margin-left: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "취소"),
        Binding("ctrl+s", "save", "저장", show=False, priority=True),
    ]

    def __init__(self, settings: Settings, path: str, overrides: list[str] = (), file_mode: bool = False):
        super().__init__()
        self.settings = settings
        self.path = path
        self.overrides = list(overrides)
        self.file_mode = file_mode

    def compose(self) -> ComposeResult:
        s = self.settings

        def row(label: str, widget) -> ComposeResult:
            with Horizontal(classes="row"):
                yield Label(label)
                yield widget

        with Vertical():
            yield Label("옵션  (Enter 저장·적용 · Esc 취소)", id="title")
            yield Label(f"설정 파일: {self.path}", id="path")
            note = ""
            if self.overrides:
                note = ("명령줄 인자로 지정된 항목: " + ", ".join(self.overrides)
                        + " — 저장하면 지금은 적용되지만 다음 실행에서는 명령줄 값이 다시 우선합니다.")
            if self.file_mode:
                note += (" " if note else "") + "--file 모드라서 소스 설정은 저장만 되고 이번 실행에는 적용되지 않습니다."
            yield Label(note, id="override")
            with VerticalScroll(id="form"):
                yield Label("조회", classes="section")
                yield from row("조회 간격(초)", Input(str(s.interval), type="integer", id="interval"))
                yield from row("orca 실행 파일", Input(s.orca, id="orca"))
                yield from row("로컬 Orca", Checkbox("조회함", s.local, id="local"))
                yield from row("원격 서버 (--env)", Input(" ".join(s.env), placeholder="페어링 서버 이름, 공백으로 구분", id="env"))
                yield from row("호스트 (--host)", Input(" ".join(s.host), placeholder="예: ssh:<id>", id="host"))
                yield from row("ssh 대상 (--ssh)", Input(" ".join(s.ssh), placeholder="예: user@macmini-1", id="ssh"))
                yield Label("AI 초안 (프롬프트 창 Ctrl+G)", classes="section")
                yield from row("공급자", Select([(c, c) for c in AI_CHOICES], value=s.ai, allow_blank=False, id="ai"))
                yield from row("모델", Input(s.ai_model, placeholder="비우면 기본 (claude: haiku · codex: CLI 설정)", id="ai_model"))
                yield from row("제한 시간(초)", Input("" if s.ai_timeout is None else f"{s.ai_timeout:g}", type="number",
                                                 placeholder="비우면 기본 (claude 60 · codex 90)", id="ai_timeout"))
                yield from row("에이전트 상황 전달", Checkbox("지시·마지막 응답을 초안 모델에 전달", s.ai_context, id="ai_context"))
                yield Label("키보드", classes="section")
                yield from row("영문 자동 전환", Checkbox(
                    "메인 화면이 앞에 있을 때 입력 소스를 영문으로 바꿔 한글 상태에서도 단축키가 듣게 함 (macOS)",
                    s.auto_abc, id="auto_abc"))
            yield Label("", id="form-error")
            with Horizontal(id="buttons"):
                yield Button("취소 (Esc)", id="cancel")
                yield Button("저장·적용 (Enter)", id="save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#interval", Input).focus()

    def _collect(self) -> Settings:
        q = self.query_one
        return Settings(
            interval=q("#interval", Input).value,
            orca=q("#orca", Input).value,
            local=q("#local", Checkbox).value,
            env=q("#env", Input).value, host=q("#host", Input).value, ssh=q("#ssh", Input).value,
            ai=str(q("#ai", Select).value),
            ai_model=q("#ai_model", Input).value,
            ai_timeout=q("#ai_timeout", Input).value,
            ai_context=q("#ai_context", Checkbox).value,
            auto_abc=q("#auto_abc", Checkbox).value,
        )

    def action_save(self) -> None:
        new = self._collect()
        errs = new.validate()
        if not errs:
            try:
                new.ai_config()  # 공급자 실행 파일 존재 여부까지 확인
            except ConfigError as e:
                errs.append(str(e))
        if errs:
            self.query_one("#form-error", Label).update("\n".join(f"• {e}" for e in errs))
            return
        self.dismiss(new)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        else:
            self.dismiss(None)


class OrcaDash(App):
    TITLE = "Orca 에이전트 대시보드"
    CSS = """
    #status { height: 1; padding: 0 1; background: $panel; }
    #errors { height: auto; max-height: 4; padding: 0 1; color: $error; }
    DataTable { height: 1fr; }
    #detail-box { height: 12; border-top: solid $primary; }
    #detail { padding: 0 1; }
    """
    BINDINGS = [  # 한글 입력 상태에서는 같은 자리의 자모(ㅔ ㅐ ㄱ ㄹ ㄷ ㅂ)로도 동작
        key_binding("p", "send_prompt", "프롬프트 보내기"),
        key_binding("o", "settings", "옵션"),
        key_binding("r", "refresh", "새로고침"),
        key_binding("f", "cycle_filter", "필터"),
        key_binding("e", "toggle_empty", "빈 워크트리"),
        key_binding("q", "quit", "종료"),
    ]

    def __init__(self, settings: Settings, ai: AIConfig | None = None, *,
                 config_path: str = DEFAULT_CONFIG, files: list[Source] | None = None,
                 cli_overrides: list[str] = ()):
        super().__init__()
        self.settings = settings
        self.config_path = config_path
        self.files = files            # --file 모드: 소스는 파일로 고정
        self.cli_overrides = list(cli_overrides)
        self.ai = ai or AIConfig(provider="off")
        self._set_sources(files or settings.sources())
        self.interval = settings.interval
        self._refresh_timer = None
        self.input_source = InputSource()
        self._saved_source: str | None = None  # 영문으로 바꾸기 전의 입력 소스
        # 전환 전 소스를 파일에도 남긴다. 신호조차 못 받고 죽었을 때 다음 실행이 이어받아 되돌리기 위함.
        self._source_state_file = os.path.join(os.path.dirname(config_path) or ".", "input-source")
        self.rows: list[Row] = []
        self.filter_idx = 0
        self.show_empty = False
        self.last_fetch: float | None = None
        self.errors: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="status")
        yield Static(id="errors")
        yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
        with VerticalScroll(id="detail-box"):
            yield Static("행을 선택하면 상세 내용이 표시됩니다.", id="detail")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for label, key in [("상태", "state"), ("상태 지속", "age"), ("호스트", "host"),
                           ("저장소", "repo"), ("워크트리", "wt"), ("브랜치", "branch"),
                           ("에이전트", "agent"), ("도구", "tool"), ("갱신", "upd"),
                           ("요약", "summary")]:
            table.add_column(label, key=key)
        self._adopt_stale_source()  # 첫 조회(_tick_status 의 감시 포함)보다 먼저 지난 기록을 이어받는다
        self._sync_input_source()
        await self.action_refresh()
        self._refresh_timer = self.set_interval(self.interval, self.action_refresh)
        self.set_interval(1, self._tick_status)
        self._install_signal_handlers()

    # --- 입력 소스 자동 전환 (macOS) ------------------------------------------
    def _sync_input_source(self, *, fresh: bool = True) -> None:
        """메인 화면이 앞에 있고 포커스가 있으면 영문으로, 아니면 원래 입력 소스로."""
        if not self.input_source.available:
            return
        want_english = (self.settings.auto_abc and self.app_focus
                        and not isinstance(self.screen, ModalScreen))
        if want_english:
            cur = self.input_source.current(fresh=fresh)
            if cur and cur != self.input_source.english_id:
                if self.input_source.select_english():
                    self._saved_source = cur
                    self._write_source_state(cur)
        else:
            self.restore_input_source()

    def _keep_input_source(self) -> None:
        """1초마다: 메인 화면에 있는데 사용자가 Caps Lock·⌃Space 로 한글로 바꿨으면 다시 영문으로.

        포커스 이벤트는 창을 오갈 때만 오므로, 창 안에서 직접 바꾼 경우는 이렇게 감시해야 잡힌다.
        모달 안이거나 포커스가 없으면 아무것도 하지 않는다(그때는 한글이 맞음).
        """
        if (self.input_source.available and self.settings.auto_abc and self.app_focus
                and not isinstance(self.screen, ModalScreen)):
            self._sync_input_source(fresh=False)

    def restore_input_source(self) -> None:
        if self._saved_source:
            self.input_source.select(self._saved_source)
            self._saved_source = None
        self._write_source_state(None)

    def _write_source_state(self, source: str | None) -> None:
        try:
            if source:
                os.makedirs(os.path.dirname(self._source_state_file), exist_ok=True)
                with open(self._source_state_file, "w", encoding="utf-8") as f:
                    f.write(source)
            elif os.path.exists(self._source_state_file):
                os.remove(self._source_state_file)
        except OSError:
            pass

    def _adopt_stale_source(self) -> None:
        """지난 실행이 되돌리지 못하고 죽었으면(파일이 남아 있음) 그 소스를 이어받아 종료 때 되돌린다."""
        if not self.input_source.available:
            return
        try:
            with open(self._source_state_file, encoding="utf-8") as f:
                stale = f.read().strip()
        except OSError:
            return
        if stale and stale != self.input_source.english_id \
                and self.input_source.current() == self.input_source.english_id:
            self._saved_source = stale
        else:
            self._write_source_state(None)  # 사용자가 이미 직접 바꿔 둔 상태 → 잊는다

    def _install_signal_handlers(self) -> None:
        """창 닫기 버튼·Cmd+Q(SIGHUP)나 kill(SIGTERM)로 끝나도 입력 소스를 되돌리고 종료한다."""
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGHUP, signal.SIGTERM):
                loop.add_signal_handler(sig, self._on_terminate_signal, sig)
        except (NotImplementedError, RuntimeError, ValueError):
            pass

    def _on_terminate_signal(self, sig: int) -> None:
        self.restore_input_source()
        # 정상 종료를 시도하되, 신호로 끝나는 상황에서는 이벤트 루프가 막혀 끝나지 않을 수 있다.
        # 루프와 무관한 스레드 타이머로 1초 뒤 강제 종료한다. (복원 보조 도구는 별도 세션이라 영향 없음)
        threading.Timer(1.0, os._exit, args=(0,)).start()
        self.exit(return_code=0)

    def watch_app_focus(self, focus: bool) -> None:
        """터미널 창이 포커스를 얻거나 잃을 때 (Textual 의 app_focus 반응값)."""
        if self.is_mounted:
            self._sync_input_source()

    def _open_modal(self, screen: ModalScreen, callback) -> None:
        """모달을 열기 전 입력 소스를 되돌리고, 닫히면 다시 맞춘다."""
        def done(result) -> None:
            callback(result)
            self._sync_input_source()
        self.push_screen(screen, done)
        self._sync_input_source()

    async def action_quit(self) -> None:
        self.restore_input_source()
        await super().action_quit()

    def _set_sources(self, sources: list[Source]) -> None:
        self.sources = sources
        self.source_by_label = {s.label: s for s in sources}

    # --- 옵션 ---------------------------------------------------------------
    def action_settings(self) -> None:
        self._open_modal(
            SettingsScreen(self.settings, self.config_path, self.cli_overrides, file_mode=bool(self.files)),
            self._apply_settings)

    def _apply_settings(self, new: Settings | None) -> None:
        if new is None:
            return
        try:
            ai = new.ai_config()
        except ConfigError as e:
            self.notify(str(e), title="옵션 적용 실패", severity="error", timeout=10)
            return
        saved = True
        try:
            new.save(self.config_path)
        except OSError as e:
            saved = False
            self.notify(f"설정 파일에 쓰지 못했습니다: {e}", title="저장 실패", severity="error", timeout=10)
        self.settings = new
        self.ai = ai
        self.interval = new.interval
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        self._refresh_timer = self.set_interval(self.interval, self.action_refresh)
        if not self.files:
            self._set_sources(new.sources())
        self.call_later(self.action_refresh)
        ai_txt = f"{ai.provider}" + (f"/{ai.model}" if ai.model else "")
        self.notify(("저장·적용: " if saved else "이번 실행에만 적용: ")
                    + f"간격 {new.interval}초 · 소스 {len(self.sources)}개 · AI {ai_txt}",
                    title="옵션", timeout=6)

    async def action_refresh(self) -> None:
        results = await asyncio.gather(*(fetch(s) for s in self.sources))
        self.rows = [r for rows, _ in results for r in rows]
        self.errors = [e for _, e in results if e]
        self.last_fetch = time.time()
        self.query_one("#errors", Static).update("\n".join(self.errors))
        self._render_table()

    def action_cycle_filter(self) -> None:
        self.filter_idx = (self.filter_idx + 1) % len(FILTERS)
        self._render_table()

    def action_toggle_empty(self) -> None:
        self.show_empty = not self.show_empty
        self._render_table()

    def _visible(self) -> list[Row]:
        rows = self.rows
        if not self.show_empty:
            rows = [r for r in rows if r.state is not None]
        f = FILTERS[self.filter_idx]
        if f == "주의 필요":
            rows = [r for r in rows if STATE_STYLE.get(r.state, STATE_STYLE[None])[2] <= 1 or r.wait]
        elif f == "진행 중":
            rows = [r for r in rows if r.state in ("blocked", "waiting", "permission", "working")]
        return sorted(rows, key=lambda r: (STATE_STYLE.get(r.state, ("", "", 9))[2],
                                           -(r.updated_at or 0)))

    def _render_table(self) -> None:
        table = self.query_one(DataTable)
        cur = None
        if table.row_count and table.cursor_row is not None:
            try:
                cur = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value
            except Exception:
                cur = None
        # DataTable.clear() 가 스크롤 위치를 0으로 되돌리므로 미리 저장해 둔다.
        scroll_x = table.scroll_x
        table.clear()
        for r in self._visible():
            label, style, _ = STATE_STYLE.get(r.state, (r.state or "?", "white", 9))
            state_txt = Text(label, style=style)
            if r.main_state and r.state and r.main_state != r.state:
                state_txt.append(f" (주:{STATE_STYLE.get(r.main_state, (r.main_state,))[0]})", style="dim")
            if r.wait:
                state_txt.append(f" · {r.wait}", style="yellow")
            wt = Text(("● " if r.unread else "") + r.worktree)
            table.add_row(state_txt, _ago(r.started_at), r.host, r.repo, wt, r.branch,
                          r.agent_type, r.tool, _clock(r.updated_at), r.summary, key=r.key)
        if cur:
            try:
                table.move_cursor(row=table.get_row_index(cur))
            except Exception:
                pass
        self._restore_scroll_x(table, scroll_x)
        self._tick_status()

    def _restore_scroll_x(self, table: DataTable, x: float) -> None:
        """새로고침 전 좌우 스크롤 위치를 복원한다. (세로는 커서 복원이 처리)

        clear() 직후에는 표 크기가 아직 재계산되지 않아 값이 잘릴 수 있으므로
        즉시 한 번, 화면 갱신 뒤 한 번 더 적용한다.
        """
        if not x:
            return

        def apply() -> None:
            table.scroll_to(x=x, animate=False, force=True)

        apply()
        self.call_after_refresh(apply)

    def _tick_status(self) -> None:
        self._keep_input_source()
        vis = self._visible()
        counts: dict[str, int] = {}
        for r in self.rows:
            counts[STATE_STYLE.get(r.state, (r.state,))[0]] = counts.get(
                STATE_STYLE.get(r.state, (r.state,))[0], 0) + 1
        summary = " · ".join(f"{k} {v}" for k, v in counts.items())
        since = f"{int(time.time() - self.last_fetch)}초 전" if self.last_fetch else "-"
        self.query_one("#status", Static).update(
            f"필터: {FILTERS[self.filter_idx]} | 빈 워크트리: {'표시' if self.show_empty else '숨김'} | "
            f"표시 {len(vis)}행 | {summary} | 마지막 조회 {since} (간격 {self.interval}초)"
        )

    def _current_row(self) -> Row | None:
        table = self.query_one(DataTable)
        if not table.row_count or table.cursor_row is None:
            return None
        try:
            key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value
        except Exception:
            return None
        return next((r for r in self.rows if r.key == key), None)

    def action_send_prompt(self) -> None:
        row = self._current_row()
        if row is None:
            self.notify("선택된 행이 없습니다.", severity="warning")
            return
        if not row.pane_key:
            self.notify("이 워크트리에는 에이전트가 없습니다.", severity="warning")
            return
        src = self.source_by_label.get(row.source)
        if src is None or src.file:
            self.notify("파일 소스에서는 프롬프트를 보낼 수 없습니다.", severity="warning")
            return

        def on_result(text: str | None) -> None:
            if text:
                self.run_worker(self._send_prompt(src, row, text), exclusive=False)

        cwd = row.path if (src.label == "local" and row.path and os.path.isdir(row.path)) \
            else tempfile.gettempdir()
        self._open_modal(PromptScreen(row, self.ai, cwd), on_result)

    async def _send_prompt(self, src: Source, row: Row, text: str) -> None:
        target = f"{row.repo}/{row.worktree}"
        self.notify(f"{target} 에 전송 중…", timeout=3)
        try:
            msg = await send_prompt(src, row.pane_key or "", text)
        except OrcaError as e:
            self.notify(f"{target}: {e}", title="전송 실패", severity="error", timeout=10)
            return
        self.notify(f"{target}: {msg}", title="프롬프트 전송", timeout=6)
        self.set_timer(2, self.action_refresh)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_send_prompt()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        key = event.row_key.value if event.row_key else None
        row = next((r for r in self.rows if r.key == key), None)
        if row:
            self.query_one("#detail", Static).update(row.detail)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Orca 에이전트 상태 TUI 대시보드",
        epilog=f"옵션은 설정 파일({DEFAULT_CONFIG})에 저장되며 대시보드에서 o 키로 보고 고칠 수 있다. "
               "명령줄 인자는 파일 값보다 우선한다.")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="설정 파일 경로")
    p.add_argument("--interval", type=int, help="조회 간격(초), 기본 60")
    p.add_argument("--orca", help="orca 실행 파일 경로, 기본 orca")
    p.add_argument("--env", action="append", help="페어링된 Remote Orca Server 이름 (반복 가능)")
    p.add_argument("--host", action="append", help="orca --host 선택자, 예: ssh:<id> (반복 가능)")
    p.add_argument("--ssh", action="append", help="ssh 접속 대상, 원격에서 orca 직접 실행 (반복 가능)")
    p.add_argument("--no-local", action="store_true", help="로컬 Orca 조회 안 함")
    p.add_argument("--file", action="append", help="저장된 JSON 파일로 표시 (테스트용)")
    g = p.add_argument_group("AI 초안 (프롬프트 창에서 Ctrl+G)")
    g.add_argument("--ai", choices=AI_CHOICES,
                   help="초안 작성에 쓸 로컬 CLI. auto: claude → codex → off 순 자동 감지 (기본)")
    g.add_argument("--ai-model", help="모델 지정. claude 기본 haiku, codex 기본은 CLI 설정값")
    g.add_argument("--ai-timeout", type=float, help="초안 생성 제한 시간(초). 기본 claude 60, codex 90")
    g.add_argument("--ai-context", choices=["on", "off"],
                   help="에이전트의 지시·마지막 응답을 초안 모델에 전달할지 (기본 on)")
    args = p.parse_args()
    try:
        settings = Settings.load(args.config)
        overrides = settings.apply_args(args)
        errs = settings.validate()
        if errs:
            raise ConfigError("옵션 오류: " + "; ".join(errs))
        ai = settings.ai_config()
    except ConfigError as e:
        raise SystemExit(str(e))
    files = None
    if args.file:
        files = [Source(label=f if len(args.file) > 1 else "file", file=f) for f in args.file]
    app = OrcaDash(settings, ai, config_path=args.config, files=files, cli_overrides=overrides)
    try:
        app.run()
    finally:
        app.restore_input_source()

if __name__ == "__main__":
    main()
