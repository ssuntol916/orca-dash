#!/usr/bin/env python3
"""Orca 에이전트 상태 TUI 대시보드.

`orca worktree ps --json` 결과를 주기적으로 읽어 표로 보여준다.
Orca 1.4.230 출력 구조 기준으로 작성.

키:
  p / Enter  선택한 에이전트에게 프롬프트 보내기
             (모달에서 Enter 전송 · Ctrl+J 또는 Shift+Enter 줄바꿈 · Esc 취소)
  Ctrl+G     프롬프트 창에서 AI(로컬 claude -p 또는 codex exec)가 초안 작성.
             메모를 적고 누르면 초안 생성, 다시 누르면 현재 내용을 다듬기. --ai 옵션 참고
  r 새로고침 · f 필터 · e 빈 워크트리 · q 종료

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
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual import events
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static, TextArea
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
            raise SystemExit(f"--ai {provider}: 실행 파일을 PATH 에서 찾을 수 없습니다")
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


class OrcaDash(App):
    TITLE = "Orca 에이전트 대시보드"
    CSS = """
    #status { height: 1; padding: 0 1; background: $panel; }
    #errors { height: auto; max-height: 4; padding: 0 1; color: $error; }
    DataTable { height: 1fr; }
    #detail-box { height: 12; border-top: solid $primary; }
    #detail { padding: 0 1; }
    """
    BINDINGS = [
        Binding("p", "send_prompt", "프롬프트 보내기"),
        Binding("r", "refresh", "새로고침"),
        Binding("f", "cycle_filter", "필터"),
        Binding("e", "toggle_empty", "빈 워크트리"),
        Binding("q", "quit", "종료"),
    ]

    def __init__(self, sources: list[Source], interval: int, ai: AIConfig | None = None):
        super().__init__()
        self.sources = sources
        self.ai = ai or AIConfig(provider="off")
        self.source_by_label = {s.label: s for s in sources}
        self.interval = interval
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
        await self.action_refresh()
        self.set_interval(self.interval, self.action_refresh)
        self.set_interval(1, self._tick_status)

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
        self.push_screen(PromptScreen(row, self.ai, cwd), on_result)

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


def build_sources(args: argparse.Namespace) -> list[Source]:
    sources: list[Source] = []
    if args.file:
        return [Source(label=f if len(args.file) > 1 else "file", file=f) for f in args.file]
    if not args.no_local:
        sources.append(Source(label="local", orca=args.orca))
    for env in args.env or []:
        sources.append(Source(label=env, orca=args.orca, env=env))
    for host in args.host or []:
        sources.append(Source(label=host, orca=args.orca, host=host))
    for target in args.ssh or []:
        sources.append(Source(label=target, ssh=target))
    return sources


def main() -> None:
    p = argparse.ArgumentParser(description="Orca 에이전트 상태 TUI 대시보드")
    p.add_argument("--interval", type=int, default=60, help="조회 간격(초), 기본 60")
    p.add_argument("--orca", default="orca", help="orca 실행 파일 경로")
    p.add_argument("--env", action="append", help="페어링된 Remote Orca Server 이름 (반복 가능)")
    p.add_argument("--host", action="append", help="orca --host 선택자, 예: ssh:<id> (반복 가능)")
    p.add_argument("--ssh", action="append", help="ssh 접속 대상, 원격에서 orca 직접 실행 (반복 가능)")
    p.add_argument("--no-local", action="store_true", help="로컬 Orca 조회 안 함")
    p.add_argument("--file", action="append", help="저장된 JSON 파일로 표시 (테스트용)")
    g = p.add_argument_group("AI 초안 (프롬프트 창에서 Ctrl+G)")
    g.add_argument("--ai", choices=["auto", "claude", "codex", "off"], default="auto",
                   help="초안 작성에 쓸 로컬 CLI. auto: claude → codex → off 순 자동 감지 (기본)")
    g.add_argument("--ai-model", help="모델 지정. claude 기본 haiku, codex 기본은 CLI 설정값")
    g.add_argument("--ai-timeout", type=float, help="초안 생성 제한 시간(초). 기본 claude 60, codex 90")
    g.add_argument("--ai-context", choices=["on", "off"], default="on",
                   help="에이전트의 지시·마지막 응답을 초안 모델에 전달할지 (기본 on)")
    args = p.parse_args()
    ai = AIConfig.from_args(args.ai, args.ai_model, args.ai_timeout, args.ai_context == "on")
    OrcaDash(build_sources(args), max(5, args.interval), ai).run()


if __name__ == "__main__":
    main()
