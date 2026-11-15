#!/usr/bin/env python3
"""Orca 에이전트 상태 TUI 대시보드.

`orca worktree ps --json` 결과를 주기적으로 읽어 표로 보여준다.
Orca 1.4.230 출력 구조 기준으로 작성.

키:
  p / Enter  선택한 에이전트에게 프롬프트 보내기
             (모달에서 Enter 전송 · Ctrl+J 또는 Shift+Enter 줄바꿈 · Esc 취소)
  Ctrl+G     프롬프트 창에서 AI(로컬 claude -p 또는 codex exec)가 초안 작성.
             메모를 적고 누르면 초안 생성, 다시 누르면 현재 내용을 다듬기. --ai 옵션 참고
             프롬프트 창의 '작성 에이전트'에서 관점을 체크한다: 목표 지향(goal, 프로젝트 목표 문서 기준, 메모는 받지 않음) ·
             문제 발견(review, git 변경분에서 문제를 찾음) · 최종 결정(final, 다른 초안들을 받아 하나로 정함).
             여러 개를 체크하면 각자 독립적으로 초안을 쓰고 체크한 순서로 '[이름]' 머리말을 붙여 묶으며,
             최종 결정을 함께 체크하면 그 묶음을 받아 프롬프트 하나로 정한다. ~/.config/orca-dash/agents/<id>.md 로 추가 가능
             하고, 저장소 안 .orca-dash/agents/<id>.md 가 있으면 그 저장소의 에이전트에 한해 같은 id 를 덮어쓴다.
             문제 발견·최종 결정은 읽기 전용 도구(Read·Grep·Glob)로 저장소 파일을 직접 읽고 쓴다 (claude: --tools 로
             그 도구만 남기고 권한이 필요한 것은 묻지 않고 거절, codex: 원래 읽기 전용 샌드박스). md frontmatter 의
             tools · model · timeout 으로 에이전트별 도구·모델·제한 시간을 정하며 쓰기·실행 도구는 거절한다
             옵션의 「백그라운드 제안」을 켜면 입력 대기·권한 대기·막힘 행이 생기거나 바뀔 때 창을 열지 않아도 뒤에서
             작성 에이전트 체인이 (메모 없이) 한 번에 하나씩 돌아 제안을 준비한다. 상태 열에 '제안 …'(작성 중) ·
             '제안 ✓'(준비됨) · '제안 ✗'(실패)로 보이고, 프롬프트 창을 열면 입력창에 들어와 있어 Enter 만 누르면 된다
             (Ctrl+G 는 다듬기). 행의 갱신 시각이 바뀌면 버리고 다시 만들며, 실패는 같은 갱신 시각에 2번까지만 시도한다
  Ctrl+T     프롬프트 창에서 진행 판정: 판정 에이전트(verdict, 「진행 판정」)가 원래 지시·목표 문서·마지막 응답·
             변경분·최근 커밋·최근 전송 기록을 보고 달성/계속/막힘과 사유 한 문장을 낸다. 결과는 창의 상태 줄과
             표의 상태 칸(「판정 달성」「판정 막힘」)·상세·상태 줄에 남고 입력창은 건드리지 않는다. 최근 자동 전송
             3회가 거의 같거나 그 사이 저장소 변경이 없으면 AI 를 부르지 않고 막힘으로 판정한다
  o          옵션 보기/수정 (조회 간격·소스·AI). 저장하면 설정 파일에 쓰고 바로 적용.
             「에이전트」 탭에서 작성 에이전트별 '생각의 흐름'(답을 쓰기 전에 거치는 생각 단계)을 +/- 로 편집
             「자동 전송」 탭에서 자동 전송 정책(켬/끔 · 허용 상태·대기 사유 · 연속 상한 · 최소 간격 · 저장소별 켬/끔 ·
             최종 결정 에이전트 필수)을 편집. 기본은 꺼짐이고 --auto-send on|off 로 이번 실행만 바꿀 수 있다
  a          자동 전송 일시 정지/재개. 설정의 auto_send 가 켜져 있으면 새로고침 때마다 정책이 허용하고
             준비된 제안이 있는 행 하나에 그 제안을 사람 없이 보낸다 (제안이 없으면 보내지 않음).
             보내기 직전에 진행 판정을 거쳐 달성·막힘이면 보내지 않고 macOS 알림으로 사람을 부른다.
             사람이 보낸 것과 자동으로 보낸 것 모두 <설정 디렉터리>/send-log.jsonl 에 한 줄씩 기록한다
  r 새로고침 · f 필터 · e 빈 워크트리 · q 종료
  macOS 에서는 메인 화면이 앞에 있을 때 입력 소스를 영문(ABC)으로 자동 전환하고, 프롬프트·옵션 창을
  열거나 다른 앱으로 가거나 종료하면 원래 입력 소스로 되돌린다 (옵션에서 끌 수 있음). 메인 화면에서 Caps Lock·
  ⌃Space 로 한글로 바꿔도 1초 안에 다시 영문이 된다. 그래서 한글 상태에서도 단축키가 바로 듣는다. 자동 전환이 꺼져 있거나 안 되는 환경에서는 같은 자리의 두벌식 자모(ㅔ=p · ㅐ=o ·
  ㄱ=r · ㄹ=f · ㄷ=e · ㅁ=a · ㅂ=q)로도 동작하되, IME 가 자모를 조합 중 상태로 붙잡으면 Space/Enter 로 확정해야 한다.

설정 파일: ~/.config/orca-dash/config.json (--config 로 변경). 명령줄 인자가 있으면 그 값이 우선.

자동 전송 정책: 사람 없이 초안을 보내도 되는지는 auto_send_allowed(settings, row, history) 가 (허용 여부, 한국어 사유)
로 판정한다. 순서대로 켬/끔(저장소별 설정이 전체 설정보다 우선) → 에이전트 터미널 → 허용 상태(기본 입력 대기) →
허용 대기 사유(기본 질문) → 최종 결정 에이전트 → 연속 자동 전송 상한(기본 3회, 사람이 직접 보내면 0으로) →
마지막 전송 뒤 최소 간격(기본 120초)을 본다. 권한 대기와 막힘은 설정과 무관하게 항상 사람에게 남긴다.

사용:
  python3 orca_dash.py                         # 로컬, 60초 간격
  python3 orca_dash.py --interval 30
  python3 orca_dash.py --ssh macmini-1         # 원격: ssh 로 원격 orca 실행 (미검증)
  python3 orca_dash.py --env <서버명>          # 원격: 페어링 서버 (미검증)
  python3 orca_dash.py --file sample.json      # 저장된 JSON 으로 화면 확인
  python3 orca_dash.py --auto-send on          # 이번 실행만 자동 전송 정책 켬 (조건은 옵션의 「자동 전송」 탭)
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime

from rich.markup import escape
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual import events
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (Button, Checkbox, DataTable, Footer, Header, Input, Label, Select, SelectionList,
                             Static, Switch, TabbedContent, TabPane, TextArea)
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
아래 '에이전트 상황'(그리고 있으면 '사용자 메모')을 바탕으로, 에이전트에게 그대로 보낼 프롬프트 본문만 한국어로 출력한다.

요청에는 [에이전트] JSON 이 함께 온다. "agent.character" 는 네 역할 id 이고 그 역할의 지시문은 아래 [역할]에 있다.
"agent.think_steps" 는 답을 쓰기 전에 번호 순서대로 거치는 생각 단계다. 그 순서로 생각한 뒤, 생각 과정은
출력하지 않고 최종 프롬프트만 출력한다.

규칙:
- 서문, 설명, 제목, 코드 펜스, 따옴표 없이 프롬프트 본문만 출력한다.
- 보통 1~6문장으로 구체적이고 바로 실행 가능하게 쓴다. 지적할 항목이 여럿이면 '- '로 시작하는 목록을 써도 된다.
- 파일 경로나 명령은 상황에 있는 것만 쓴다. 추측한 파일·코드는 적지 않는다.
- 에이전트가 '입력 대기'나 '권한 대기' 상태면 마지막 응답의 질문이나 요청에 답하는 내용으로 쓴다.
- '사용자 메모' 절이 없거나 비어 있으면 상황에 맞는 다음 지시를 제안한다 (메모 절이 없는 역할은 메모를 받지 않는 역할이다).
- '기존 초안'이 있으면 그것을 사용자 메모의 의도대로(메모가 없으면 더 구체적이고 짧게) 다듬어 완성본만 다시 출력한다.
- '[에이전트 초안]' 절이 있으면 다른 작성 에이전트들이 '[이름]' 머리말로 구분해 쓴 초안이다. [역할]의 지시대로 그것을
  평가해 에이전트에게 보낼 최종 프롬프트 하나만 쓴다. 머리말이나 출처 표시는 남기지 않는다.
"""

# 컨텍스트 제공자 id. status 는 항상 들어가고, 나머지는 작성 에이전트가 고른다.
CONTEXT_PROVIDERS = {
    "instruction": "에이전트에게 준 원래 지시",
    "last_message": "마지막 응답과 현재 도구",
    "goal": "프로젝트 목표 문서 (GOAL.md · docs/GOAL.md · .orca-dash/goal.md, 없으면 README 앞부분)",
    "diff": "작업 중 변경분과 main 대비 변경분 (git diff)",
    "log": "최근 커밋 10개 (git log)",
}
GOAL_FILES = ("GOAL.md", "docs/GOAL.md", ".orca-dash/goal.md")
# 작성 에이전트에게 줄 수 있는 도구. 저장소를 읽기만 하는 것으로 한정한다 — 초안이 사람 검토 없이 전송될 수 있으므로
# 쓰기·실행 도구(Edit, Write, Bash 등)는 정의 단계(md)와 명령줄 조립 단계 양쪽에서 ConfigError 로 거절한다.
READ_TOOLS = ("Read", "Grep", "Glob")
PROJECT_AGENTS_DIR = os.path.join(".orca-dash", "agents")  # 저장소 안 프로젝트별 에이전트 정의


@dataclass
class DraftAgent:
    """AI 초안을 쓰는 '작성 에이전트': 역할 지시문 + 필요한 컨텍스트 목록.

    공급자(claude/codex)는 전역 설정이고, 에이전트는 '무엇을 보고 어떤 관점으로 쓸지'를 정한다. model·timeout 을
    적으면 그 에이전트만 전역 모델·제한 시간 대신 그 값을 쓰고, tools 를 적으면 저장소를 직접 읽는다.
    내장 에이전트 외에 <설정 디렉터리>/agents/<id>.md 와 저장소 안 .orca-dash/agents/<id>.md 로 추가할 수 있다
    (load_agents 참고).
    """
    id: str
    name: str
    description: str
    instructions: str
    context: tuple[str, ...]
    builtin: bool = True
    path: str = ""  # 사용자 정의 파일 경로
    steps: tuple[str, ...] = ()  # 생각의 흐름: 답을 쓰기 전에 순서대로 거치는 생각 단계 (옵션 > 에이전트 탭에서 편집)
    memo: bool = True  # 사용자 메모를 요청에 넣을지. 메모가 방향을 흐리는 역할(목표 지향)은 끈다 — md 의 'memo: off'
    final: bool = False  # 최종 결정 에이전트: 다른 에이전트들의 초안을 [에이전트 초안]으로 받아 하나로 정한다 — md 의 'final: on'
    tools: tuple[str, ...] = ()  # 저장소를 직접 읽는 도구 (READ_TOOLS 중에서) — md 의 'tools: Read, Grep, Glob'. claude 에서만 쓰임
    model: str | None = None     # 이 에이전트만 쓸 모델. None 이면 전역 설정 — md 의 'model: sonnet'
    timeout: float | None = None  # 이 에이전트만 쓸 제한 시간(초). None 이면 전역 설정 — md 의 'timeout: 120'

    @property
    def label(self) -> str:
        text = f"{self.name} — {self.description}" if self.description else self.name
        notes = (["다른 초안을 받아 하나로"] if self.final else []) + ([] if self.memo else ["메모 안 받음"])
        return f"{text} ({' · '.join(notes)})" if notes else text


BUILTIN_AGENTS: list[DraftAgent] = [
    DraftAgent(
        id="goal", name="목표 지향",
        description="프로젝트 목표 문서에 비추어 다음 지시를 쓴다",
        context=("instruction", "last_message", "goal"),
        memo=False,  # 메모가 있으면 목표 대신 메모를 좇아 억지로 목표에 끼워 맞추므로 받지 않는다
        steps=("프로젝트 목표(없으면 원래 지시)에서 이번 작업과 관련된 항목을 찾는다",
               "마지막 응답이 그 항목에 얼마나 다가갔는지, 벗어난 부분은 없는지 판단한다",
               "목표에 가장 가까워지는 다음 한 단계를 정한다",
               "그 단계를 바로 실행할 수 있는 지시로 쓴다"),
        instructions="""\
역할: 프로젝트의 목표를 향해 작업을 이끄는 리드.
- '프로젝트 목표'가 있으면 이번 작업이 그중 어느 항목에 기여하는지 한 문장으로 짚고, 목표에서 벗어난 작업은 되돌리거나 범위를 좁히도록 지시한다.
- 마지막 응답이 질문이나 선택지를 담고 있으면 목표에 가장 부합하는 쪽으로 답한다.
- 다음 단계는 목표 달성에 가장 가까운 한 가지로 좁혀 구체적으로 지시한다.
- 목표 문서가 없으면 원래 지시를 목표로 삼는다.
"""),
    DraftAgent(
        id="review", name="문제 발견",
        description="변경분에서 버그·누락·테스트 공백을 찾아 수정 지시를 쓴다",
        context=("instruction", "last_message", "diff", "log"),
        tools=READ_TOOLS,  # 잘린 diff 만으로 단정하지 않도록 저장소를 직접 읽는다
        steps=("변경분에서 바뀐 파일과 함수를 파악한다",
               "각 변경의 입력·경계 조건·실패 경로를 따라가며 문제를 찾는다",
               "테스트가 그 변경을 덮는지 확인한다",
               "찾은 문제를 파일·함수와 함께 정리하고 수정 지시로 마무리한다"),
        instructions="""\
역할: 변경된 코드에서 문제를 찾는 리뷰어.
- '변경분'을 읽고 버그, 빠진 예외 처리, 경계 조건, 동시성·자원 누수, 테스트 공백, 원래 지시와 어긋난 구현을 찾는다.
- 찾은 문제는 파일 경로(가능하면 함수명)와 함께 무엇이 왜 문제인지 한 줄씩 적고, 고치라는 지시로 마무리한다.
- 문제가 없으면 테스트나 확인 절차를 추가하라는 지시를 쓴다. 변경분이 없으면 마지막 응답을 바탕으로 검증을 요청한다.
- 변경분에서 의심되는 곳은 파일을 직접 읽어 확인한 뒤 쓴다. 읽지 못한 것은 추측하지 않는다.
"""),
    DraftAgent(
        id="final", name="최종 결정",
        description="다른 에이전트들의 초안을 평가해 보낼 프롬프트 하나로 정한다",
        context=("instruction", "last_message"),
        final=True,  # 작성 에이전트들이 끝난 뒤 마지막에 한 번 실행된다
        tools=READ_TOOLS,  # 초안이 말하는 파일·함수가 실제로 그런지 확인하고 정한다
        steps=("각 초안이 마지막 응답의 질문·대기 사유에 답하는지, 원래 지시와 사용자 메모에 맞는지 평가한다",
               "초안끼리 충돌하는 지시를 찾아 어느 쪽을 택할지 정한다 (사용자 메모가 있으면 그 의도를 우선)",
               "택한 내용을 중복 없이 하나의 지시로 합치고, 상황에 없는 파일·명령은 뺀다",
               "에이전트가 바로 실행할 수 있는 순서로 다듬는다"),
        instructions="""\
역할: 여러 작성 에이전트의 초안을 읽고 에이전트에게 보낼 최종 프롬프트 하나를 결정하는 편집자.
- '에이전트 초안'의 각 초안을 상황·원래 지시·사용자 메모에 비추어 평가하고, 가장 적절한 초안을 고르거나 좋은 부분만 합쳐 하나로 만든다.
- 초안끼리 충돌하면 마지막 응답의 질문에 직접 답하는 쪽, 사용자 메모의 의도에 가까운 쪽을 택한다. 양쪽을 다 하라고 늘어놓지 않는다.
- 결과는 가장 긴 초안보다 길지 않게 하고, 초안에 없는 새 작업은 더하지 않는다.
- '에이전트 초안' 절이 없으면 상황과 메모로 직접 쓴다.
- 변경분이나 초안에서 의심되는 곳은 파일을 직접 읽어 확인한 뒤 쓴다. 읽지 못한 것은 추측하지 않는다.
"""),
]
DEFAULT_AGENT = BUILTIN_AGENTS[0].id


def agents_dir(config_path: str) -> str:
    return os.path.join(os.path.dirname(config_path) or ".", "agents")


_MACHINE_KEYS = ("context", "memo", "final", "tools", "model", "timeout")  # 값이 정해진 형식인 frontmatter 키


def check_tools(tools) -> tuple[str, ...]:
    """도구 이름을 READ_TOOLS 표기로 맞춘다(대소문자 무시, 중복 제거). 읽기 전용이 아닌 도구가 있으면 ConfigError."""
    canon = {t.lower(): t for t in READ_TOOLS}
    out: list[str] = []
    bad: list[str] = []
    for t in tools or ():
        name = canon.get(str(t).strip().lower())
        if name is None:
            bad.append(str(t).strip())
        elif name not in out:
            out.append(name)
    if bad:
        raise ConfigError(f"tools 에 쓸 수 없는 도구 — {', '.join(bad)} "
                          f"(읽기 전용 {', '.join(READ_TOOLS)} 만 가능, 쓰기·실행 도구는 허용하지 않음)")
    return tuple(out)


def check_model(raw) -> str | None:
    """빈 값은 None(전역 설정). 명령줄 인자로 그대로 넘기므로 공백이 있거나 '-' 로 시작하면 ConfigError."""
    model = str(raw or "").strip()
    if not model:
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]@-]*", model):
        raise ConfigError(f"model 은 모델 이름 하나 — {model}")
    return model


def check_timeout(raw) -> float | None:
    """빈 값은 None(전역 설정). 0보다 큰 수(초)가 아니면 ConfigError."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        timeout = float(str(raw).strip())
    except ValueError:
        timeout = 0.0
    if not (0 < timeout < float("inf")):
        raise ConfigError(f"timeout 은 0보다 큰 수(초) — {str(raw).strip()}")
    return timeout


def parse_agent_file(path: str) -> DraftAgent:
    """agents/<id>.md 를 읽는다. 형식:

        ---
        name: 테스트 작성                 (필수)
        description: 변경분에 맞는 테스트  (선택)
        context: diff, log               (선택, 기본 instruction, last_message)
        step: 바뀐 함수를 파악한다          (선택, 반복 가능 — 생각의 흐름 기본값. 옵션 > 에이전트 탭에서 덮어씀)
        memo: off                        (선택, 기본 on — off 면 사용자 메모를 요청에 넣지 않음)
        final: on                        (선택, 기본 off — on 이면 최종 결정 에이전트: 다른 초안을 받아 하나로 정함)
        tools: Read, Grep, Glob          (선택, 기본 없음 — 저장소를 직접 읽는 도구. Read·Grep·Glob 만 가능)
        model: sonnet                    (선택 — 이 에이전트만 전역 모델 대신 쓸 모델)
        timeout: 120                     (선택 — 이 에이전트만 전역 제한 시간 대신 쓸 초)
        ---
        역할 지시문 본문…

    잘못되면 ConfigError.
    """
    agent_id = os.path.splitext(os.path.basename(path))[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", agent_id):
        raise ConfigError(f"{path}: 파일 이름(id)은 영문·숫자·-_ 만")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    meta: dict[str, str] = {}
    steps: list[str] = []
    body = text
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        # 닫는 줄은 정확히 '---' 인 줄 (본문의 '----' 구분선 등과 혼동하지 않도록)
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if close is None:
            raise ConfigError(f"{path}: frontmatter 를 닫는 --- 가 없음")
        for line in lines[1:close]:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if ":" not in line:
                raise ConfigError(f"{path}: frontmatter 줄 형식 오류 — {line.strip()}")
            k, v = line.split(":", 1)
            if k.strip().lower() in ("step", "steps"):
                steps.append(v.strip())
            elif k.strip().lower() in _MACHINE_KEYS:
                meta[k.strip().lower()] = re.sub(r"(^|\s)#.*$", "", v).strip()  # 값 뒤 '# 설명' 주석 허용
            else:
                meta[k.strip().lower()] = v.strip()
        body = "\n".join(lines[close + 1:])
    name = meta.get("name", "").strip()
    if not name:
        raise ConfigError(f"{path}: frontmatter 에 name 이 필요함")
    ctx = tuple(_split_list(meta["context"])) if "context" in meta else ("instruction", "last_message")
    bad = [c for c in ctx if c not in CONTEXT_PROVIDERS]
    if bad:
        raise ConfigError(f"{path}: 모르는 context — {', '.join(bad)} (가능: {', '.join(CONTEXT_PROVIDERS)})")
    flags = {}
    for key, default in (("memo", "on"), ("final", "off")):
        raw = meta.get(key, default).strip().lower()
        if raw not in ("on", "off", "yes", "no", "true", "false", "1", "0"):
            raise ConfigError(f"{path}: {key} 는 on 또는 off — {raw}")
        flags[key] = raw in ("on", "yes", "true", "1")
    try:
        tools = check_tools(_split_list(meta.get("tools", "")))
        model = check_model(meta.get("model"))
        timeout = check_timeout(meta.get("timeout"))
    except ConfigError as e:
        raise ConfigError(f"{path}: {e}") from None
    if not body.strip():
        raise ConfigError(f"{path}: 지시문 본문이 비어 있음")
    return DraftAgent(id=agent_id, name=name, description=meta.get("description", "").strip(),
                      instructions=body.strip() + "\n", context=ctx, builtin=False, path=path,
                      steps=tuple(x for x in steps if x), memo=flags["memo"], final=flags["final"],
                      tools=tools, model=model, timeout=timeout)


def load_agents(config_path: str, step_overrides: dict[str, list[str]] | None = None,
                include_hidden: bool = False, repo_dir: str | None = None) -> tuple[list[DraftAgent], list[str]]:
    """내장 에이전트에 사용자 정의(<설정 디렉터리>/agents/*.md)를 합치고, repo_dir 가 있으면 그 저장소의
    프로젝트별 정의(.orca-dash/agents/*.md)를 그 뒤에 읽는다. 같은 id 면 뒤에 읽은 것이 덮는다
    (내장 < 사용자 < 프로젝트). step_overrides(설정의 agent_steps)에 있는 id 는 생각의 흐름을 그 값으로 바꾼다.
    잘못된 파일은 건너뛰고(그 id 는 앞 단계 정의가 남는다) 오류 메시지 목록으로 돌려준다.
    프롬프트 초안을 쓰지 않는 숨은 에이전트(HIDDEN_AGENT_IDS — 진행 판정)는 include_hidden 일 때만 넣는다."""
    agents = {a.id: a for a in BUILTIN_AGENTS + SYSTEM_AGENTS}
    errors: list[str] = []
    dirs = [agents_dir(config_path)] + ([os.path.join(repo_dir, PROJECT_AGENTS_DIR)] if repo_dir else [])
    for d in dirs:
        try:
            names = sorted(n for n in os.listdir(d) if n.endswith(".md"))
        except OSError:
            names = []
        for n in names:
            try:
                a = parse_agent_file(os.path.join(d, n))
            except (ConfigError, OSError) as e:
                errors.append(str(e))
                continue
            agents[a.id] = a
    for aid, steps in (step_overrides or {}).items():
        if aid in agents:
            agents[aid] = dataclasses.replace(agents[aid], steps=tuple(steps))
    return [a for a in agents.values() if include_hidden or a.id not in HIDDEN_AGENT_IDS], errors


def pick_agent(agents: list[DraftAgent], agent_id: str | None) -> DraftAgent:
    for a in agents:
        if a.id == agent_id:
            return a
    return agents[0]


def pick_agents(agents: list[DraftAgent], ids: list[str] | None) -> list[DraftAgent]:
    """설정의 id 목록을 순서대로 에이전트로 바꾼다. 모르는 id 는 버리고, 하나도 없으면 첫 에이전트."""
    by_id = {a.id: a for a in agents}
    out = [by_id[i] for i in dict.fromkeys(ids or []) if i in by_id]
    return out or [agents[0]]


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "\n…(이하 생략)"


async def _git(repo_dir: str, *args: str, timeout: float = 10) -> str:
    """git 명령 stdout. 실패·시간 초과면 빈 문자열."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", repo_dir, *args, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except (OSError, asyncio.TimeoutError):
        return ""
    return out.decode(errors="replace") if proc.returncode == 0 else ""


def _read_goal(repo_dir: str) -> tuple[str, str] | None:
    """(파일 이름, 내용). 목표 문서가 없으면 README 앞부분, 그것도 없으면 None."""
    for rel in GOAL_FILES:
        fp = os.path.join(repo_dir, rel)
        if os.path.isfile(fp):
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    return rel, _clip(f.read(), 4000)
            except OSError:
                pass
    fp = os.path.join(repo_dir, "README.md")
    if os.path.isfile(fp):
        try:
            with open(fp, encoding="utf-8", errors="replace") as f:
                head = "".join(f.readlines()[:40])
            return "README.md 앞부분 (목표 문서 없음)", _clip(head, 2500)
        except OSError:
            pass
    return None


async def _repo_context(provider: str, repo_dir: str | None) -> list[str]:
    """저장소를 읽는 제공자(goal·diff·log). 원격 호스트라 경로가 없으면 생략 사유를 적는다."""
    title = {"goal": "[프로젝트 목표]", "diff": "[변경분]", "log": "[최근 커밋]"}[provider]
    if not repo_dir or not os.path.isdir(repo_dir):
        return ["", title, "(원격 호스트라 로컬에서 읽을 수 없어 생략)"]
    if provider == "goal":
        g = _read_goal(repo_dir)
        return ["", f"[프로젝트 목표] ({g[0]})", g[1]] if g else ["", title, "(목표 문서·README 없음)"]
    if provider == "log":
        log = await _git(repo_dir, "log", "--oneline", "-n", "10")
        return ["", title, _clip(log, 1500) or "(없음)"]
    # diff: 작업 중 변경(스테이지 포함) + 추적 안 된 파일 + main 대비 브랜치 변경
    out = ["", title]
    stat = await _git(repo_dir, "diff", "HEAD", "--stat")
    body = await _git(repo_dir, "diff", "HEAD")
    untracked = await _git(repo_dir, "ls-files", "--others", "--exclude-standard")
    if stat.strip() or untracked.strip():
        out += ["(작업 중, 커밋 전)", _clip(stat, 800)]
        if untracked.strip():
            out += ["추적 안 된 파일: " + _clip(" ".join(untracked.split()), 500)]
        out += [_clip(body, 6000)]
    else:
        out += ["(커밋 전 변경 없음)"]
    base = None
    for b in ("main", "master"):
        if (await _git(repo_dir, "rev-parse", "--verify", "-q", b)).strip():
            base = b
            break
    cur = (await _git(repo_dir, "rev-parse", "--abbrev-ref", "HEAD")).strip()
    if base and cur and cur != base:
        bstat = await _git(repo_dir, "diff", f"{base}...HEAD", "--stat")
        if bstat.strip():
            out += ["", f"({base} 대비 이 브랜치의 커밋된 변경)", _clip(bstat, 800),
                    _clip(await _git(repo_dir, "diff", f"{base}...HEAD"), 4000)]
    return out


async def build_draft_request(agent: DraftAgent, row: Row, note: str, current: str,
                              include_context: bool, repo_dir: str | None, drafts: str = "") -> str:
    """에이전트가 고른 제공자로 요청 본문을 조립한다. include_context 가 꺼져 있으면 상태만 보낸다.
    drafts 는 최종 결정 에이전트가 받는 다른 에이전트들의 초안(머리말 포함). 다듬기(current 있음)에는 넣지 않는다."""
    label = STATE_STYLE.get(row.state, (row.state or "?",))[0]
    lines = ["[에이전트 상황]",
             f"저장소/워크트리/브랜치: {row.repo} / {row.worktree} ({row.branch})",
             f"에이전트: {row.agent_type} · 상태: {label}" + (f" · 대기 사유: {row.wait}" if row.wait else ""),
             "", "[에이전트]", agent_json(agent)]
    if include_context:
        if row.path:
            lines.append(f"경로: {row.path}")
        for prov in agent.context:
            if prov == "instruction":
                lines += ["", "[원래 지시]", _clip(row.prompt, 1500) or "-"]
            elif prov == "last_message":
                if row.tool:
                    lines += ["", f"[현재 도구] {row.tool}", _clip(row.tool_input, 300)]
                lines += ["", "[마지막 응답]", _clip(row.last_message, 2000) or "-"]
            elif prov in ("goal", "diff", "log"):
                lines += await _repo_context(prov, repo_dir)
    if agent.final and drafts.strip() and not current.strip():  # 받을 초안이 없으면(단독 실행) 절을 넣지 않는다
        lines += ["", "[에이전트 초안]", drafts.strip()]
    if agent.memo:  # 메모를 받지 않는 에이전트(goal)는 절 자체를 넣지 않는다
        lines += ["", "[사용자 메모]", note.strip() or "(없음 — 상황에 맞는 다음 지시를 제안)"]
    elif agent.id == VERDICT_AGENT_ID and include_context and note.strip():
        lines += ["", "[최근 전송 기록]", note.strip()]  # judge_progress 가 note 자리로 넘긴 전송 기록
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


def agent_json(agent: DraftAgent) -> str:
    """요청에 함께 보내는 에이전트 명세. character 는 역할 id, think_steps 는 번호 키의 생각 단계."""
    spec = {"agent": {"character": agent.id,
                      "think_steps": {str(i): t for i, t in enumerate(agent.steps, 1)}}}
    return json.dumps(spec, ensure_ascii=False, indent=2)


TOOLS_SYSTEM = """[도구]
이번 호출에서는 {tools} 도구로 에이전트가 작업 중인 저장소(현재 작업 디렉터리)를 읽을 수 있다. 읽기 전용이다.
- 프롬프트를 쓰기 전에 반드시 도구를 써서, 상황의 변경분·마지막 응답이 말하는 파일과 함수를 직접 열어 확인한다.
  변경분은 길면 잘려서 오므로 잘린 부분과 변경된 함수의 주변 코드는 파일에서 읽는다. 경로는 저장소 기준 상대 경로로 쓴다.
- 확인한 사실만 근거로 쓰고, 읽지 못했거나 읽기가 거절된 것은 추측하지 않는다.
- 도구 사용 과정이나 읽은 내용의 요약은 출력하지 않는다. 마지막 출력은 프롬프트 본문뿐이다.
"""


def draft_system_prompt(agent: DraftAgent, tools: tuple[str, ...] = ()) -> str:
    """시스템 프롬프트. tools 는 이번 호출에서 실제로 준 도구 — 있으면 쓰라는 [도구] 절을 붙인다
    (없으면 작은 모델은 도구를 받아도 쓰지 않고 바로 답한다)."""
    base = VERDICT_SYSTEM if agent.id == VERDICT_AGENT_ID else DRAFT_SYSTEM
    return (base + f"\n[역할] (character: {agent.id})\n" + agent.instructions.strip() + "\n"
            + ("\n" + TOOLS_SYSTEM.format(tools="·".join(tools)) if tools else ""))


def agent_tools(cfg: AIConfig, agent: DraftAgent, repo_dir: str | None) -> tuple[str, ...]:
    """이번 호출에서 실제로 줄 도구. 읽을 로컬 저장소가 없거나(원격), 「에이전트 상황 전달」이 꺼져 있으면
    (상태 한 줄 외에는 보내지 않는다는 약속) 도구를 주지 않는다. 읽기 전용이 아닌 도구가 있으면 ConfigError."""
    tools = check_tools(agent.tools)
    if not tools or not cfg.include_context or not repo_dir or not os.path.isdir(repo_dir):
        return ()
    return tools


def claude_command(cfg: AIConfig, agent: DraftAgent, system: str, repo_dir: str | None = None) -> list[str]:
    """claude -p 명령줄. 도구가 있으면 내장 도구를 그 목록으로 한정하고(--tools), 권한 질문이 필요한 것은 묻지 않고
    거절하게 하며(--permission-mode dontAsk: 작업 디렉터리 안 읽기는 질문 없이 되고 밖은 거절된다), 사용자 MCP
    서버의 도구가 끼어들지 않게 한다(--strict-mcp-config). --allowedTools 로 미리 승인하면 저장소 밖 파일까지
    읽히므로 쓰지 않는다. 에이전트의 model 이 있으면 전역 모델보다 우선한다."""
    tools = agent_tools(cfg, agent, repo_dir)
    cmd = ["claude", "-p", "--no-session-persistence", "--tools", ",".join(tools)]
    if tools:
        cmd += ["--permission-mode", "dontAsk", "--strict-mcp-config"]
    cmd += ["--output-format", "json", "--system-prompt", system]
    model = agent.model or cfg.model
    if model:
        cmd += ["--model", model]
    return cmd


async def draft_prompt(cfg: AIConfig, agent: DraftAgent, row: Row, note: str, current: str,
                       cwd: str | None, repo_dir: str | None = None, drafts: str = "") -> str:
    """AI 로 프롬프트 초안을 만든다. 실패 시 DraftError. 에이전트의 model·timeout 이 있으면 전역 설정보다
    우선하고, tools 가 있으면(claude) 저장소를 작업 디렉터리로 두어 상대 경로로 읽게 한다."""
    request = await build_draft_request(agent, row, note, current, cfg.include_context, repo_dir, drafts)
    system = draft_system_prompt(agent)
    model = agent.model or cfg.model
    timeout = agent.timeout or cfg.timeout
    if cfg.provider == "claude":
        try:
            tools = agent_tools(cfg, agent, repo_dir)
            cmd = claude_command(cfg, agent, draft_system_prompt(agent, tools), repo_dir)
        except ConfigError as e:
            raise DraftError(f"{agent.name}: {e}") from None
        if tools:
            cwd = repo_dir  # 상대 경로 읽기가 저장소 기준이 되고, 권한 없이 읽히는 범위도 저장소로 한정된다
        raw = await _run_cli(cmd, request, cwd, timeout)
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
            if model:
                cmd += ["-m", model]
            cmd.append("-")  # 프롬프트는 stdin. 도구 설정은 쓰지 않는다 — 이미 읽기 전용 샌드박스(-s read-only)
            await _run_cli(cmd, system + "\n\n" + request, cwd, timeout)
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


def section_header(agent: DraftAgent) -> str:
    return f"[{agent.name}]"


def combine_drafts(parts: list[tuple[DraftAgent, str]]) -> str:
    """에이전트별 초안을 하나의 프롬프트로 묶는다. 하나면 그대로, 여럿이면 '[이름]' 머리말로 구분."""
    if len(parts) == 1:
        return parts[0][1].strip()
    return "\n\n".join(f"{section_header(a)}\n{t.strip()}" for a, t in parts)


def split_draft(text: str, agents: list[DraftAgent]) -> dict[str, str]:
    """묶인 초안을 '[이름]' 머리말로 나눠 에이전트 id 별 본문으로. 머리말이 없으면(에이전트 하나이거나
    사용자가 지웠으면) 모든 에이전트에 전체 본문을 준다."""
    by_header = {section_header(a): a.id for a in agents}
    found: dict[str, list[str]] = {}
    cur: str | None = None
    for line in text.splitlines():
        if line.strip() in by_header:
            cur = by_header[line.strip()]
            found.setdefault(cur, [])
        elif cur is not None:
            found[cur].append(line)
    if not found:
        return {a.id: text for a in agents}
    return {aid: "\n".join(lines).strip() for aid, lines in found.items()}


def has_section_headers(text: str, agents: list[DraftAgent]) -> bool:
    """본문에 작성 에이전트의 '[이름]' 머리말이 하나라도 있으면 True (split_draft 는 없을 때 전체를 돌려주므로 구분용)."""
    headers = {section_header(a) for a in agents}
    return any(line.strip() in headers for line in text.splitlines())


def split_run(agents: list[DraftAgent]) -> tuple[list[DraftAgent], DraftAgent | None]:
    """체크한 에이전트를 (작성 에이전트들, 최종 결정 에이전트) 로 나눈다. 결정 에이전트는 하나만 쓰며
    여럿 체크했으면 마지막으로 체크한 것."""
    writers = [a for a in agents if not a.final]
    decider = next((a for a in reversed(agents) if a.final), None)
    return writers, decider


def run_order(agents: list[DraftAgent]) -> list[DraftAgent]:
    """실제 실행 순서: 작성 에이전트들(체크 순서) 뒤에 최종 결정 에이전트."""
    writers, decider = split_run(agents)
    return writers + ([decider] if decider else [])


async def draft_each(cfg: AIConfig, agents: list[DraftAgent], row: Row, note: str, currents: dict[str, str],
                     cwd: str | None, repo_dir: str | None = None, on_step=None, drafts: str = "") -> str:
    """작성 에이전트들이 각자 독립적으로(같은 상황·메모로) 초안을 쓰고 순서대로 묶는다. 최종 결정 에이전트가
    있으면 그 묶음을 [에이전트 초안]으로 받아 프롬프트 하나로 정하고, 그것이 결과가 된다.
    currents 는 다듬기일 때 에이전트별 기존 초안. on_step(i, agent, text_so_far) 는 단계마다 호출.
    drafts 는 작성 에이전트를 돌리지 않을 때(입력창에 남아 있던 머리말 묶음을 다시 결정할 때) 결정 에이전트에게 줄 초안."""
    writers, decider = split_run(agents)
    parts: list[tuple[DraftAgent, str]] = []
    for i, agent in enumerate(writers):
        text = await draft_prompt(cfg, agent, row, note, currents.get(agent.id, ""), cwd, repo_dir)
        parts.append((agent, text))
        if on_step:
            on_step(i, agent, combine_drafts(parts))
    if decider is None:
        return combine_drafts(parts)
    # 결정 에이전트에게는 하나뿐이어도 누가 썼는지 보이도록 머리말을 붙인다
    if parts:
        drafts = "\n\n".join(f"{section_header(a)}\n{t.strip()}" for a, t in parts)
    final = await draft_prompt(cfg, decider, row, note, currents.get(decider.id, ""), cwd, repo_dir, drafts=drafts)
    if on_step:
        on_step(len(writers), decider, final)
    return final


# ---------------------------------------------------------------------------
# 백그라운드 제안: 사람이 프롬프트 창을 열기 전에 작성 에이전트 체인을 미리 돌려 둔 결과.
# 메모리에만 두고 행 키로 찾는다. 행의 updated_at 이 바뀌면(에이전트가 다시 움직였으면) 무효다.
# ---------------------------------------------------------------------------
# 사람의 다음 지시가 필요한 상태: STATE_STYLE 에서 '작업 중'보다 앞에 오는 것(막힘·입력 대기·권한 대기)과
# Orca 가 긴 이름으로 주는 같은 뜻의 상태.
PROPOSAL_STATES = frozenset({s for s, style in STATE_STYLE.items() if s and style[2] <= 1}
                            | {"waiting_input", "waiting_permission"})
PROPOSAL_MAX_ATTEMPTS = 2  # 같은 updated_at 에 대해 실패한 제안을 다시 시도하는 상한 (첫 시도 포함)


@dataclass
class Proposal:
    row_key: str
    text: str
    agent_ids: list[str]
    created_at: float                 # epoch 초
    row_updated_at: float | None      # 만들 때 그 행의 updated_at — 행의 값과 다르면 무효
    status: str = "ready"             # drafting(작성 중) | ready(준비됨) | error(실패) | sent(이미 보냄)
    error: str = ""                   # status 가 error 일 때 사유
    attempts: int = 1                 # 이 updated_at 에 대해 시도한 횟수


class ProposalStore:
    """행 키별 제안 하나. get/put/invalidate 는 계약된 이름이고, 나머지는 유효성 판단을 한곳에 모은 것."""

    def __init__(self) -> None:
        self._items: dict[str, Proposal] = {}

    def get(self, row_key: str) -> Proposal | None:
        return self._items.get(row_key)

    def put(self, proposal: Proposal) -> None:
        self._items[proposal.row_key] = proposal

    def invalidate(self, row_key: str) -> None:
        self._items.pop(row_key, None)

    def current(self, row: Row) -> Proposal | None:
        """그 행의 지금 updated_at 에 대해 만든 제안 (상태 무관). 행이 그 뒤 바뀌었으면 None."""
        p = self._items.get(row.key)
        return p if p is not None and p.row_updated_at == row.updated_at else None

    def valid(self, row: Row) -> Proposal | None:
        """바로 쓸 수 있는 제안: 준비됐고 본문이 있으며 행이 그 뒤로 바뀌지 않았다."""
        p = self.current(row)
        return p if p is not None and p.status == "ready" and p.text.strip() else None

    def sync(self, rows: list[Row]) -> list[str]:
        """새로 조회한 행들과 맞춘다: updated_at 이 달라진 행의 제안을 버리고 그 키들을 돌려준다.
        조회에서 잠깐 빠진 행(소스 오류 등)의 제안은 그대로 둔다."""
        stale = [r.key for r in rows if r.key in self._items and self._items[r.key].row_updated_at != r.updated_at]
        for k in stale:
            del self._items[k]
        return stale

    def mark_sent(self, row: Row) -> None:
        """그 행에 프롬프트를 보냈다. 조회가 아직 옛 상태를 돌려주는 동안 같은 제안을 다시 만들지 않도록
        지우지 않고 '보냄'으로 남긴다 (행이 갱신되면 sync 가 버린다)."""
        p = self.current(row)
        if p is None:
            p = Proposal(row.key, "", [], time.time(), row.updated_at)
            self.put(p)
        p.status = "sent"


def needs_proposal(row: Row, store: ProposalStore) -> bool:
    """이 행의 제안을 (다시) 만들어야 하는가: 사람 개입이 필요한 상태의 에이전트이고, 지금 updated_at 에 대한
    제안이 없거나 실패한 제안이 재시도 상한에 못 미쳤을 때."""
    if row.state not in PROPOSAL_STATES or not row.pane_key:
        return False
    p = store.current(row)
    if p is None:
        return True
    return p.status == "error" and p.attempts < PROPOSAL_MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# 진행 판정: 자동 전송 루프가 멈출 조건. 판정 에이전트(verdict)가 달성/계속/막힘을 정하고,
# is_stalled 가 AI 없이 반복을 감지하며, notify_user 가 사람을 부른다. 루프 자체는 여기 없다.
# ---------------------------------------------------------------------------
VERDICT_AGENT_ID = "verdict"
HIDDEN_AGENT_IDS = frozenset({VERDICT_AGENT_ID})  # 프롬프트 초안을 쓰지 않아 작성 에이전트 목록·설정에서 빼는 id

VERDICT_SYSTEM = """\
너는 코딩 에이전트(Claude Code, Codex 등)의 작업 진행을 판정하는 심사자다. 프롬프트를 쓰지 않는다.
아래 '에이전트 상황'(원래 지시, 마지막 응답, 프로젝트 목표, 변경분, 최근 커밋, 최근 전송 기록 중 주어진 것)만 근거로
이 작업을 끝낼지, 다음 지시를 이어서 보낼지, 사람을 불러야 할지 정한다.

요청에는 [에이전트] JSON 이 함께 온다. "agent.character" 는 네 역할 id 이고 그 역할의 지시문은 아래 [역할]에 있다.
"agent.think_steps" 는 답을 쓰기 전에 번호 순서대로 거치는 생각 단계다. 그 순서로 생각한 뒤, 생각 과정은
출력하지 않고 판정만 출력한다.

출력 규칙:
- 아래 형태의 JSON 객체 하나만 출력한다. 서문, 설명, 코드 펜스, 다른 키는 쓰지 않는다.
  {"verdict": "done" | "continue" | "stuck", "reason": "<한국어 한 문장>"}
- done: 원래 지시(와 그것이 기여하는 목표 항목)가 달성되었고 남은 일이 없다.
- continue: 아직 할 일이 남았고, 다음 지시나 질문에 대한 답을 보내면 더 나아갈 수 있다.
- stuck: 같은 오류·같은 질문이 되풀이되거나, 전송은 이어지는데 변경분에 진전이 없거나, 사람만 정할 수 있는 결정·권한·
  외부 자원이 필요하다.
- reason 에는 판정의 근거를 상황에 있는 사실로 한 문장만 적는다. 추측한 파일·명령은 적지 않는다.
- 근거가 부족하면 continue 로 하되 무엇이 부족한지 reason 에 적는다.
"""

VERDICT_AGENT = DraftAgent(
    id=VERDICT_AGENT_ID, name="진행 판정",
    description="목표와 최근 진행을 보고 달성·계속·막힘을 판정한다",
    context=("instruction", "last_message", "goal", "diff", "log"),
    memo=False, final=False,
    steps=("원래 지시와 프로젝트 목표에서 이 작업이 끝났다고 볼 조건을 정하고, 변경분과 마지막 응답이 그 조건을 채웠는지 본다",
           "마지막 응답이 질문인지, 완료 보고인지, 오류·실패 보고인지 가린다",
           "변경분과 최근 커밋이 그 조건을 향한 진전인지, 최근 전송 기록에 같은 지시가 되풀이되는지 본다",
           "달성(done)·계속(continue)·막힘(stuck) 중 하나를 고르고 근거를 한 문장으로 적는다"),
    instructions="""\
역할: 작업이 끝났는지, 더 시킬 일이 남았는지, 사람이 봐야 하는지를 가르는 심사자.
- 완료 보고는 그대로 믿지 않고 변경분·최근 커밋이 원래 지시를 실제로 채웠는지 확인한다. 변경분을 볼 수 없으면 마지막 응답으로 판단하고 그 사실을 reason 에 적는다.
- 마지막 응답이 질문이면, 원래 지시와 목표로 답할 수 있는 질문은 continue, 사람의 선호·권한·비용이 걸린 선택은 stuck 이다.
- 마지막 응답이 오류 보고면, 처음 나온 오류는 continue, 최근 전송 기록의 지시가 이미 그 오류를 다뤘는데도 되풀이되면 stuck 이다.
- 목표의 「범위 밖」에 해당하는 작업을 계속 넓히고 있으면 stuck 이다.
- '최근 전송 기록'의 '(자동)' 표시는 사람 없이 보낸 지시다. 자동 지시가 이어지는데 변경분이 그대로면 stuck 쪽으로 본다.
""")
SYSTEM_AGENTS: list[DraftAgent] = [VERDICT_AGENT]

VERDICT_STYLE = {"done": ("달성", "bold green"), "continue": ("계속", "cyan"), "stuck": ("막힘", "bold red")}
VERDICT_ALIASES = {"달성": "done", "완료": "done", "계속": "continue", "막힘": "stuck"}
VERDICT_FAILED = "판정 실패"
STALL_WINDOW = 3     # 정지 감지에 보는 최근 자동 전송 횟수
STALL_RATIO = 0.8    # 이 이상 닮은 지시는 같은 지시로 본다 (difflib ratio)


@dataclass
class Verdict:
    verdict: str   # "done" | "continue" | "stuck"
    reason: str    # 한국어 한 문장. 판정을 못 했으면 "판정 실패: …" 로 시작하고 verdict 는 "continue"

    @property
    def failed(self) -> bool:
        return self.reason.startswith(VERDICT_FAILED)

    @property
    def label(self) -> str:
        return VERDICT_FAILED if self.failed else VERDICT_STYLE.get(self.verdict, (self.verdict,))[0]

    @property
    def style(self) -> str:
        return "dim" if self.failed else VERDICT_STYLE.get(self.verdict, ("", "white"))[1]


def load_verdict_agent(config_path: str, step_overrides: dict[str, list[str]] | None = None,
                       repo_dir: str | None = None) -> DraftAgent:
    """판정 에이전트 정의. 내장 정의를 <설정 디렉터리>/agents/verdict.md, 그다음 저장소의
    .orca-dash/agents/verdict.md 가 덮고(잘못된 파일은 무시), 설정의 agent_steps 가 생각의 흐름을 바꾼다.
    어떻게 정의하든 메모를 받지 않고 최종 결정 에이전트가 아니다."""
    agent = VERDICT_AGENT
    paths = [os.path.join(agents_dir(config_path), VERDICT_AGENT_ID + ".md")]
    if repo_dir:
        paths.append(os.path.join(repo_dir, ".orca-dash", "agents", VERDICT_AGENT_ID + ".md"))
    for path in paths:
        if os.path.isfile(path):
            try:
                agent = parse_agent_file(path)
            except (ConfigError, OSError):
                pass
    steps = (step_overrides or {}).get(VERDICT_AGENT_ID)
    if steps is not None:
        agent = dataclasses.replace(agent, steps=tuple(steps))
    return dataclasses.replace(agent, memo=False, final=False)


def parse_verdict(text: str) -> Verdict:
    """모델 출력에서 {"verdict", "reason"} 을 꺼낸다. 코드 펜스나 앞뒤 설명이 붙어 있어도 첫 번째로 해석되는
    객체를 쓴다. 해석하지 못하면 루프를 막지 않도록 Verdict("continue", "판정 실패: …")."""
    t = strip_fences(text or "")
    if not t:
        return Verdict("continue", f"{VERDICT_FAILED}: 빈 응답")
    data = None
    decoder = json.JSONDecoder()
    start = t.find("{")
    while start != -1:
        try:
            obj, _ = decoder.raw_decode(t[start:])
        except ValueError:
            obj = None
        if isinstance(obj, dict) and "verdict" in obj:
            data = obj
            break
        start = t.find("{", start + 1)
    if data is None:
        return Verdict("continue", f"{VERDICT_FAILED}: JSON 해석 실패 — {_first_line(t, 60)}")
    value = str(data.get("verdict") or "").strip().lower()
    value = VERDICT_ALIASES.get(value, value)
    if value not in VERDICT_STYLE:
        return Verdict("continue", f"{VERDICT_FAILED}: 모르는 판정 값 — {value or '(없음)'}")
    reason = " ".join(str(data.get("reason") or "").split())
    if reason.startswith(VERDICT_FAILED):
        reason = "사유: " + reason   # 모델이 쓴 문장이 실패 표식으로 읽히지 않게
    return Verdict(value, _clip(reason, 300) or "(사유 없음)")


def _auto_sends(history: list[dict] | None) -> list[dict]:
    """전송 기록에서 자동 전송만 시간순으로."""
    autos = [h for h in (history or []) if isinstance(h, dict) and h.get("auto")]
    return sorted(autos, key=lambda h: h.get("at") or 0)


def is_stalled(history: list[dict] | None, heads: list[str] | None = None) -> tuple[bool, str]:
    """AI 없이 자동 전송이 헛도는지 본다. (막혔는지, 한국어 사유)

    - 같은 지시 반복: 최근 자동 전송 3회의 text 가 서로 difflib ratio 0.8 이상.
    - 변경 없이 반복: 최근 자동 전송 3회 시점의 저장소 HEAD 가 모두 같음. heads 는 그 시점들의 HEAD
      (오래된 것부터, repo_head 의 값)이고, 주지 않으면 각 기록의 "head" 값을 쓴다. 값이 없으면 이 규칙은 건너뛴다.
    history 는 그 행의 전송 기록(at · text · auto). 사람이 보낸 것(auto=False)은 세지 않는다.
    """
    recent = _auto_sends(history)[-STALL_WINDOW:]
    if len(recent) == STALL_WINDOW:
        texts = [str(h.get("text") or "").strip()[:2000] for h in recent]
        if all(texts) and all(difflib.SequenceMatcher(None, a, b).ratio() >= STALL_RATIO
                              for i, a in enumerate(texts) for b in texts[i + 1:]):
            return True, f"같은 지시 반복: 최근 자동 전송 {STALL_WINDOW}회의 내용이 거의 같음"
    if heads is None:
        heads = [str(h.get("head") or "") for h in recent]
    last = [str(h or "").strip() for h in heads][-STALL_WINDOW:]
    if len(last) == STALL_WINDOW and all(last) and len(set(last)) == 1:
        return True, f"변경 없이 반복: 최근 자동 전송 {STALL_WINDOW}회 동안 저장소 변경이 없음"
    return False, ""


async def repo_head(repo_dir: str | None) -> str:
    """is_stalled 의 heads 에 넣을 저장소 상태 값: HEAD 커밋 + (커밋 전 변경이 있으면) 그 내용의 해시.
    커밋하지 않고 고치기만 해도 값이 달라진다. 저장소가 아니거나 읽지 못하면 빈 문자열."""
    if not repo_dir or not os.path.isdir(repo_dir):
        return ""
    import hashlib
    head = (await _git(repo_dir, "rev-parse", "HEAD")).strip()
    dirty = (await _git(repo_dir, "diff", "HEAD")) + (await _git(repo_dir, "status", "--porcelain"))
    if not head and not dirty.strip():
        return ""
    return head[:12] + ("+" + hashlib.sha1(dirty.encode()).hexdigest()[:8] if dirty.strip() else "")


def history_text(history: list[dict] | None, limit: int = 8) -> str:
    """판정 요청의 [최근 전송 기록] 절 본문. 오래된 것부터 한 줄씩, 자동 전송은 '(자동)' 표시."""
    items = sorted((h for h in (history or []) if isinstance(h, dict)), key=lambda h: h.get("at") or 0)[-limit:]
    lines = []
    for h in items:
        try:
            at = datetime.fromtimestamp(float(h.get("at") or 0)).strftime("%m-%d %H:%M")
        except (TypeError, ValueError, OverflowError, OSError):
            at = "-"
        text = " ".join(str(h.get("text") or "").split())
        lines.append(f"- {at} ({'자동' if h.get('auto') else '사람'}) {text[:300]}{'…' if len(text) > 300 else ''}")
    return "\n".join(lines)


async def judge_progress(cfg: AIConfig, row: Row, repo_dir: str | None, history: list[dict] | None, *,
                         agent: DraftAgent | None = None, cwd: str | None = None) -> Verdict:
    """이 행의 작업이 달성(done)·계속(continue)·막힘(stuck) 중 어디인지 판정한다. 예외를 내지 않는다.

    먼저 is_stalled(history) 로 반복을 보고, 걸리면 AI 를 부르지 않고 stuck. 아니면 판정 에이전트를 초안과 같은
    경로(draft_prompt)로 실행해 JSON 을 해석한다. AI 가 꺼져 있거나 실패·빈 응답·깨진 JSON 이면
    Verdict("continue", "판정 실패: …") — 호출하는 루프는 Verdict.failed 로 구분할 수 있다.
    history 는 그 행의 최근 전송 기록(at · text · auto), agent 는 load_verdict_agent 의 결과(없으면 내장)."""
    stalled, why = is_stalled(history)
    if stalled:
        return Verdict("stuck", why)
    if cfg is None or not cfg.enabled:
        return Verdict("continue", f"{VERDICT_FAILED}: AI 기능이 꺼져 있음")
    try:
        text = await draft_prompt(cfg, agent or VERDICT_AGENT, row, history_text(history), "",
                                  cwd or repo_dir or tempfile.gettempdir(), repo_dir)
    except Exception as e:  # DraftError 외의 오류도 루프를 죽이지 않는다 (취소는 BaseException 이라 그대로 전파)
        return Verdict("continue", f"{VERDICT_FAILED}: {_first_line(str(e), 120) or type(e).__name__}")
    return parse_verdict(text)


def notify_user(title: str, text: str) -> None:
    """macOS 알림 센터로 사람을 부른다. 다른 OS 이거나 실패하면 조용히 넘어간다. 끝나기를 기다리지 않는다."""
    if sys.platform != "darwin":
        return
    try:
        # 제목·본문은 스크립트에 끼워 넣지 않고 인자로 넘긴다 (따옴표·역슬래시 이스케이프 문제 없음)
        subprocess.Popen(
            ["osascript", "-e", "on run argv",
             "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
             "-e", "end run", str(title)[:120], str(text)[:400]],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except Exception:
        pass


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
    PromptScreen #agent-row { height: auto; margin-top: 0; align-horizontal: left; }
    PromptScreen #agent-row > Label { width: 16; padding: 0 1 0 0; }
    PromptScreen #agents { width: 1fr; height: auto; max-height: 6; border: none; padding: 0; background: $surface; }
    PromptScreen #agent-order { color: $text-muted; height: 1; }
    PromptScreen TextArea { height: 8; }
    PromptScreen Horizontal { height: auto; margin-top: 1; align-horizontal: right; }
    PromptScreen Button { margin-left: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "취소"),
        Binding("ctrl+g", "draft", "AI 초안", priority=True),
        Binding("ctrl+t", "judge", "진행 판정", priority=True),
        Binding("ctrl+s", "send", "보내기", show=False, priority=True),  # 터미널이 전달해 주는 경우에만
    ]

    def __init__(self, row: Row, ai: AIConfig | None = None, cwd: str | None = None, *,
                 repo_dir: str | None = None, agents: list[DraftAgent] | None = None,
                 agent_ids: list[str] | None = None, agent_errors: list[str] = ()):
        super().__init__()
        self.row = row
        self.ai = ai if ai and ai.enabled else None
        self.cwd = cwd
        self.repo_dir = repo_dir            # 로컬 저장소 경로 (goal·diff·log 제공자용), 원격이면 None
        self.agents = agents or list(BUILTIN_AGENTS)
        # 실행 순서 = 체크한 순서. 설정에서 받은 목록으로 시작한다.
        self.agent_ids: list[str] = [a.id for a in pick_agents(self.agents, agent_ids)]
        self.agent_errors = list(agent_errors)
        self.note: str | None = None        # AI 에 준 사용자 메모 (다듬기 때 재사용)
        self.last_draft: str | None = None  # 마지막으로 받은 초안
        self.draft_worker: Worker | None = None
        self.proposal: Proposal | None = None  # 백그라운드 제안: 있으면 열 때 입력창에 넣는다 (앱이 열기 전에 채움)
        self.on_draft = None                   # 초안이 끝나면 on_draft(본문, 에이전트 id 목록) — 앱이 제안 저장소에 넣는다

    def compose(self) -> ComposeResult:
        r = self.row
        keys = "Enter 전송 · Ctrl+J 줄바꿈" + (" · Ctrl+G AI 초안 · Ctrl+T 진행 판정" if self.ai else "") + " · Esc 취소"
        with Vertical():
            yield Label(f"프롬프트 보내기  ({keys})", id="title")
            yield Label(f"대상: [{r.host}] {r.repo} / {r.worktree} ({r.branch}) · {r.agent_type}"
                        + (f" · 현재 {r.tool}" if r.tool else ""), id="target")
            yield Label("", id="ai-status")
            if self.ai:
                with Horizontal(id="agent-row"):
                    yield Label("작성 에이전트\n(Space 토글)")
                    yield SelectionList[str](*[(a.label, a.id, a.id in self.agent_ids) for a in self.agents],
                                             id="agents")
                yield Label(self._order_text(), id="agent-order")
            yield PromptArea(id="prompt")
            with Horizontal():
                yield Button("취소 (Esc)", id="cancel")
                if self.ai:
                    yield Button(f"AI 작성 (Ctrl+G · {self.ai.provider})", id="draft")
                yield Button("보내기 (Enter)", id="send", variant="primary")

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()
        if self.ai and self.agent_errors:
            self._set_ai_status(f"에이전트 파일 오류 {len(self.agent_errors)}건 (건너뜀): {self.agent_errors[0]}")
        self._apply_proposal()

    def _apply_proposal(self) -> None:
        """백그라운드 제안이 준비돼 있으면 입력창에 넣고 last_draft 로 등록한다 — 다음 Ctrl+G 는 다듬기가 된다."""
        p = self.proposal
        if p is None:
            return
        if p.status == "ready" and p.text.strip():
            area = self.query_one(TextArea)
            area.load_text(p.text)
            area.move_cursor(area.document.end)
            self.last_draft = p.text
            self.note = ""   # 제안은 메모 없이 만든다
            writers, decider = split_run(pick_agents(self.agents, p.agent_ids))
            names = " → ".join(a.name for a in writers) + (f" ⇒ {decider.name}" if decider and writers
                                                           else decider.name if decider else "")
            self._set_ai_status(f"백그라운드 제안({names} · {_ago(p.created_at * 1000)} 전)을 넣었습니다. "
                                "수정 후 Enter 로 전송" + (" · Ctrl+G 로 다듬기" if self.ai else ""))
        elif p.status == "error":
            self._set_ai_status(f"백그라운드 제안 실패: {p.error}" + (" · Ctrl+G 로 직접 작성" if self.ai else ""))
        elif p.status == "drafting":
            self._set_ai_status("백그라운드 제안 작성 중 (기다리지 않고 Ctrl+G 로 직접 작성할 수 있음)")

    @property
    def chain(self) -> list[DraftAgent]:
        """실행할 에이전트들 (체크한 순서). 모두 해제했으면 첫 에이전트 하나."""
        return pick_agents(self.agents, self.agent_ids)

    def _order_text(self) -> str:
        writers, decider = split_run(self.chain)
        tag = lambda a: a.name + ("" if a.memo else "(메모 안 받음)")
        names = " → ".join(tag(a) for a in writers)
        if decider and writers:
            return f"실행 순서: {names} ⇒ {tag(decider)}  (각자 쓴 초안을 {decider.name}이 하나로 정함)"
        if decider:
            return f"실행 순서: {tag(decider)}  (받을 초안이 없어 직접 작성)"
        return f"실행 순서: {names}" + ("  (각자 독립적으로 쓰고 이 순서로 묶음)" if len(writers) > 1 else "")

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        """체크 상태가 바뀌면 순서 목록을 맞춘다: 해제된 것은 빼고, 새로 체크된 것은 뒤에 붙인다."""
        if event.selection_list.id != "agents":
            return
        now = [str(v) for v in event.selection_list.selected]
        self.agent_ids = [i for i in self.agent_ids if i in now] + [i for i in now if i not in self.agent_ids]
        self.query_one("#agent-order", Label).update(self._order_text())

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("draft", "judge") and not self.ai:
            return False  # --ai off: Footer 에서도 Ctrl+G · Ctrl+T 안내를 숨긴다
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
        self._set_ai_status(self._progress_text(self._run_agents(current), 0, what))
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

    def _run_agents(self, current: str) -> list[DraftAgent]:
        """이번에 실제로 실행할 에이전트들. 다듬기인데 최종 결정 에이전트가 있으면 그것만 다시 돌린다
        (결정된 프롬프트에는 머리말이 없어 작성 에이전트별로 나눌 수 없고, 결정 에이전트가 다듬는 것이 맞다)."""
        writers, decider = split_run(self.chain)
        if current.strip() and decider:
            return [decider]
        return run_order(self.chain)

    def _progress_text(self, order: list[DraftAgent], step: int, what: str) -> str:
        who = order[step].name if len(order) == 1 else f"{step + 1}/{len(order)} {order[step].name}"
        return f"AI {what}… ({who} · {self.ai.provider if self.ai else ''}, Esc 중단 · Ctrl+G 다시 시작)"

    async def _draft(self, note: str, current: str) -> str:
        assert self.ai is not None
        order = self._run_agents(current)
        currents: dict[str, str] = {}
        drafts = ""
        if not current.strip():
            pass
        elif len(order) == 1 and order[0].final:
            writers, _ = split_run(self.chain)
            if has_section_headers(current, writers):
                drafts = current   # 결정 전에 중단됐거나 사용자가 고친 작성 에이전트 초안 묶음 → 그것으로 결정
            else:
                currents = {order[0].id: current}   # 이미 결정된 프롬프트 → 다듬기
        else:
            currents = split_draft(current, order)

        def on_step(i: int, agent: DraftAgent, combined: str) -> None:
            # 끝난 에이전트의 초안을 바로 보여 주고 다음 단계 진행을 표시한다 (워커는 같은 이벤트 루프에서 돈다)
            area = self.query_one(TextArea)
            area.load_text(combined)
            area.move_cursor(area.document.end)
            self.last_draft = combined   # 중단·실패로 여기서 끝나도 다음 Ctrl+G 가 메모가 아닌 초안으로 본다
            if i + 1 < len(order):
                self._set_ai_status(self._progress_text(order, i + 1, "작성 중"))

        return await draft_each(self.ai, order, self.row, note, currents, self.cwd, self.repo_dir, on_step,
                                drafts=drafts)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.group != "draft" or event.worker is not self.draft_worker:
            return
        if event.state == WorkerState.SUCCESS:
            draft = str(event.worker.result or "")
            area = self.query_one(TextArea)
            area.load_text(draft)
            area.move_cursor(area.document.end)
            self.last_draft = draft
            writers, decider = split_run(self.chain)
            names = " → ".join(a.name for a in writers) + (f" ⇒ {decider.name}" if decider and writers
                                                           else decider.name if decider else "")
            self._set_ai_status(f"AI 초안({names})을 넣었습니다. 수정 후 Enter 로 전송 · Ctrl+G 로 다듬기")
            if self.on_draft and draft.strip():
                self.on_draft(draft, [a.id for a in self.chain])
        elif event.state == WorkerState.ERROR:
            err = event.worker.error
            self._set_ai_status("")
            self.notify(f"{err}", title="AI 초안 실패", severity="error", timeout=10)
        elif event.state == WorkerState.CANCELLED:
            self._set_ai_status("AI 초안 중단됨 (끝난 단계까지의 내용은 남겨 둠)")

    def _cancel_draft(self) -> bool:
        if self.drafting and self.draft_worker is not None:
            self.draft_worker.cancel()
            return True
        return False

    # --- 진행 판정 (Ctrl+T) ----------------------------------------------
    # 생성자 인자를 늘리지 않도록 앱이 화면을 만든 뒤 아래 속성을 채운다 (OrcaDash._attach_verdict).
    history: list[dict] | tuple = ()            # 이 행의 최근 전송 기록 (at · text · auto)
    verdict_agent: DraftAgent | None = None     # None 이면 내장 VERDICT_AGENT
    on_verdict = None                           # 판정이 나오면 호출 (Verdict) — 앱이 표에 기록
    verdict_worker: Worker | None = None
    last_verdict: Verdict | None = None

    @property
    def judging(self) -> bool:
        return self.verdict_worker is not None and self.verdict_worker.is_running

    def action_judge(self) -> None:
        """판정 에이전트에게 달성/계속/막힘을 묻는다. 입력창 내용은 건드리지 않고 상태 줄에만 결과를 적는다."""
        if not self.ai:
            self.notify("AI 기능이 꺼져 있어 진행 판정을 할 수 없습니다.", severity="warning")
            return
        if self.drafting:
            self.notify("AI 가 초안을 작성 중입니다. 끝난 뒤 판정하세요.", severity="warning")
            return
        name = (self.verdict_agent or VERDICT_AGENT).name
        self._set_ai_status(f"{name} 중… ({self.ai.provider}, Esc 중단)")
        self.verdict_worker = self.run_worker(self._judge(), group="verdict", exclusive=True, exit_on_error=False)

    async def _judge(self) -> Verdict:
        assert self.ai is not None
        try:
            verdict = await judge_progress(self.ai, self.row, self.repo_dir, list(self.history),
                                           agent=self.verdict_agent, cwd=self.cwd)
        except asyncio.CancelledError:
            try:
                self._set_ai_status("진행 판정 중단됨")
            except Exception:
                pass  # 창이 닫히는 중
            raise
        self.last_verdict = verdict
        self._set_ai_status(f"진행 판정: {verdict.label} — {verdict.reason}")
        if self.on_verdict:
            self.on_verdict(verdict)
        return verdict

    def _cancel_judge(self) -> bool:
        if self.judging and self.verdict_worker is not None:
            self.verdict_worker.cancel()
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
        if self._cancel_draft() or self._cancel_judge():
            return  # 생성·판정만 중단, 창은 유지
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
    ai_context: bool = True                         # 에이전트 상황·저장소 내용을 초안 모델에 전달
    ai_agents: list[str] = field(default_factory=lambda: [DEFAULT_AGENT])  # 작성 에이전트 id 들, 실행 순서 (마지막에 쓴 것으로 갱신)
    agent_steps: dict[str, list[str]] = field(default_factory=dict)  # 에이전트별 생각의 흐름 (없는 id 는 에이전트 기본값)
    auto_abc: bool = True                           # macOS: 메인 화면에서 입력 소스를 영문으로 자동 전환
    # 자동 전송 정책 (auto_send_allowed 가 읽는다). 기본은 꺼짐이고, 없는 필드는 이 기본값으로 읽힌다.
    auto_send: bool = False                         # 전체 켬/끔
    auto_send_states: list[str] = field(default_factory=lambda: list(AUTO_SEND_DEFAULT_STATES))  # 허용 상태
    auto_send_waits: list[str] = field(default_factory=lambda: list(AUTO_SEND_DEFAULT_WAITS))    # 허용 대기 사유
    auto_send_max_streak: int = 3                   # 사람 개입 없이 연속으로 보내는 상한(회)
    auto_send_cooldown: int = 120                   # 같은 행의 마지막 전송 뒤 최소 간격(초)
    auto_send_repos: dict[str, bool] = field(default_factory=dict)  # 저장소 이름별 켬/끔 (없으면 전체 설정)
    auto_send_require_final: bool = True            # 작성 에이전트에 최종 결정 에이전트가 있어야 함

    auto_draft: bool = False                        # 사람 개입이 필요한 행의 제안을 백그라운드로 미리 만든다

    FIELDS = ("interval", "orca", "local", "env", "host", "ssh",
              "ai", "ai_model", "ai_timeout", "ai_context", "ai_agents", "agent_steps", "auto_abc",
              "auto_draft")
    AUTO_SEND_FIELDS = ("auto_send", "auto_send_states", "auto_send_waits", "auto_send_max_streak",
                        "auto_send_cooldown", "auto_send_repos", "auto_send_require_final")
    FIELDS = FIELDS + AUTO_SEND_FIELDS

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
        if "ai_agents" not in data and data.get("ai_agent"):
            s.ai_agents = [data["ai_agent"]]  # 이전 형식(단일 id) 호환
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
        v = self.ai_agents
        if isinstance(v, str):
            v = _split_list(v)
        self.ai_agents = list(dict.fromkeys(str(x).strip() for x in (v or []) if str(x).strip())) or [DEFAULT_AGENT]
        if not isinstance(self.agent_steps, dict):
            errs.append("agent_steps 는 {에이전트 id: [단계, …]} 형태")
            self.agent_steps = {}
        else:
            self.agent_steps = {str(k): [str(x).strip() for x in (v if isinstance(v, (list, tuple)) else [v])
                                         if str(x).strip()]
                                for k, v in self.agent_steps.items() if str(k).strip()}
        self.auto_abc = bool(self.auto_abc)
        self.auto_draft = bool(self.auto_draft)
        self._validate_auto_send(errs)
        if not self.local and not (self.env or self.host or self.ssh):
            errs.append("조회할 소스가 없음 (로컬을 끄면 env/host/ssh 중 하나 필요)")
        return errs

    def _validate_auto_send(self, errs: list[str]) -> None:
        """auto_send_* 필드의 타입을 맞춘다. 화면에서 온 문자열(공백 구분 목록, "repo:on repo2:off")도 받는다."""
        for key, label in (("auto_send", "자동 전송"), ("auto_send_require_final", "최종 결정 필수")):
            b = _as_bool(getattr(self, key))
            if b is None:
                errs.append(f"{label}은 on 또는 off")
                b = type(self)().__dict__[key]
            setattr(self, key, b)
        for key, default in (("auto_send_states", AUTO_SEND_DEFAULT_STATES),
                             ("auto_send_waits", AUTO_SEND_DEFAULT_WAITS)):
            v = getattr(self, key)
            if isinstance(v, str):
                v = _split_list(v)
            if not isinstance(v, (list, tuple)):
                errs.append(f"{key} 는 문자열 목록")
                v = []
            setattr(self, key, list(dict.fromkeys(str(x).strip() for x in v if str(x).strip())) or list(default))
        bad = [x for x in self.auto_send_states if auto_state(x) in AUTO_SEND_NEVER_STATES]
        if bad:
            errs.append(f"자동 전송 허용 상태에 {', '.join(bad)} 은 넣을 수 없음 (권한 대기·막힘은 항상 사람에게 남김)")
        bad = [x for x in self.auto_send_waits if x in AUTO_SEND_NEVER_WAITS]
        if bad:
            errs.append(f"자동 전송 허용 대기 사유에 {', '.join(bad)} 은 넣을 수 없음 (권한 요청은 항상 사람이 답함)")
        for key, label, low in (("auto_send_max_streak", "연속 자동 전송 상한은 1 이상의 정수(회)", 1),
                                ("auto_send_cooldown", "자동 전송 최소 간격은 0 이상의 정수(초)", 0)):
            try:
                n = int(getattr(self, key))
                if n < low:
                    raise ValueError
                setattr(self, key, n)
            except (TypeError, ValueError):
                errs.append(label)
        try:
            self.auto_send_repos = parse_repo_flags(self.auto_send_repos)
        except ValueError as e:
            errs.append(f"저장소별 자동 전송: {e}")
            self.auto_send_repos = {}

    def apply_args(self, args: argparse.Namespace) -> list[str]:
        """명령줄에서 준 값으로 덮어쓰고, 덮어쓴 항목 이름을 돌려준다."""
        over: list[str] = []
        for k, v in [("interval", args.interval), ("orca", args.orca), ("env", args.env),
                     ("host", args.host), ("ssh", args.ssh), ("ai", args.ai),
                     ("ai_model", args.ai_model), ("ai_timeout", args.ai_timeout),
                     ("ai_agents", getattr(args, "ai_agent", None))]:
            if v is not None:
                setattr(self, k, v)
                over.append(k)
        if args.no_local:
            self.local = False
            over.append("local")
        if args.ai_context is not None:
            self.ai_context = args.ai_context == "on"
            over.append("ai_context")
        if getattr(args, "auto_send", None) is not None:
            self.auto_send = args.auto_send == "on"
            over.append("auto_send")
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


# ---------------------------------------------------------------------------
# 자동 전송 정책: 사람이 빠진 자리에서 "어떤 조건에서 스스로 보내도 되는가"를 판정한다 (GOAL.md 「자동 전송 정책」).
# 전송하는 쪽은 auto_send_allowed 만 부르면 된다. 이 절은 판정만 하고 전송·기록은 하지 않는다.
# ---------------------------------------------------------------------------
AUTO_SEND_DEFAULT_STATES = ("waiting_input",)
AUTO_SEND_DEFAULT_WAITS = ("질문",)
AUTO_SEND_NEVER_STATES = ("permission", "blocked")  # 설정과 무관하게 항상 사람에게 남기는 상태
AUTO_SEND_NEVER_WAITS = ("권한",)                    # 설정과 무관하게 항상 사람이 답하는 대기 사유
_AUTO_STATE_ALIAS = {"waiting": "waiting_input"}     # Orca 판에 따라 입력 대기가 waiting 또는 waiting_input 으로 온다
_WAIT_KINDS = (  # (분류, 대기 사유 글에서 찾는 패턴) — 위에서부터 먼저 맞는 것
    ("권한", r"권한|승인|허용|permission|approv"),
    ("중단", r"중단|interrupt"),
    ("질문", r"질문|입력|답|question|input|answer"),
)


def _as_bool(value) -> bool | None:
    """bool 또는 on/off 류 문자열을 bool 로. 알 수 없으면 None ("off" 를 참으로 읽지 않기 위함)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("on", "true", "yes", "1"):
        return True
    if text in ("off", "false", "no", "0"):
        return False
    return None


def parse_repo_flags(value) -> dict[str, bool]:
    """저장소별 켬/끔. dict 또는 "repo:on repo2:off"(공백·쉼표 구분) 문자열을 받는다. 잘못되면 ValueError."""
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        pairs = []
        for tok in _split_list(value):
            name, sep, flag = tok.rpartition(":")
            if not sep or not name:
                raise ValueError(f"'{tok}' 는 저장소:on 또는 저장소:off 형식이 아님")
            pairs.append((name, flag))
    elif isinstance(value, dict):
        pairs = list(value.items())
    else:
        raise ValueError("{저장소 이름: true/false} 형태가 아님")
    out: dict[str, bool] = {}
    for name, flag in pairs:
        b = _as_bool(flag)
        if b is None or not str(name).strip():
            raise ValueError(f"'{name}:{flag}' 의 값은 on 또는 off")
        out[str(name).strip()] = b
    return out


def format_repo_flags(repos: dict[str, bool]) -> str:
    return " ".join(f"{k}:{'on' if v else 'off'}" for k, v in (repos or {}).items())


def auto_state(state) -> str:
    """정책 비교용 상태 이름. waiting 과 waiting_input 을 같은 것으로 본다."""
    s = str(state or "").strip().lower()
    return _AUTO_STATE_ALIAS.get(s, s)


def wait_kind(row) -> str:
    """행의 대기 사유를 정책 분류(권한·중단·질문·없음)로 바꾼다. 어느 분류에도 안 맞으면 대기 사유 글 그대로.
    사유가 비어 있는 입력 대기는 에이전트가 턴을 끝내고 답을 기다리는 것이므로 '질문'으로 본다."""
    text = str(getattr(row, "wait", "") or "").strip()
    if auto_state(getattr(row, "state", None)) == "permission":
        return "권한"
    for kind, pattern in _WAIT_KINDS:
        if re.search(pattern, text, re.IGNORECASE):
            return kind
    if text:
        return text
    return "질문" if auto_state(getattr(row, "state", None)) == "waiting_input" else "없음"


def _history_newest_first(history) -> list[dict]:
    """전송 기록을 최근 것부터. 실패한 전송(result 가 ok 가 아님)은 보내진 것이 아니므로 세지 않는다."""
    items = [h for h in (history or []) if isinstance(h, dict) and h.get("result", "ok") == "ok"]
    def at(h: dict) -> float:
        try:
            return float(h.get("at") or 0)
        except (TypeError, ValueError):
            return 0.0
    return sorted(items, key=at, reverse=True)


def auto_send_streak(history) -> int:
    """가장 최근 전송부터 거슬러 올라가며 "auto" 가 참인 항목이 이어지는 수. 사람이 직접 보낸 기록에서 끊긴다."""
    n = 0
    for h in _history_newest_first(history):
        if not h.get("auto"):
            break
        n += 1
    return n


def has_final_agent(settings, agents: list[DraftAgent] | None = None) -> bool:
    """설정의 작성 에이전트(ai_agents)에 최종 결정 성격의 에이전트가 있는지. agents(load_agents 결과)를 주면
    사용자 정의 'final: on' 까지 보고, 없으면 내장 에이전트의 final 표시와 id "final" 로 판단한다."""
    final_ids = {a.id for a in (agents if agents is not None else BUILTIN_AGENTS) if a.final}
    if agents is None:
        final_ids.add("final")
    return any(i in final_ids for i in (settings.ai_agents or []))


def auto_send_allowed(settings, row, history, *, now: float | None = None,
                      agents: list[DraftAgent] | None = None) -> tuple[bool, str]:
    """이 행에 지금 사람 없이 초안을 보내도 되는지. (허용 여부, 한국어 사유)를 돌려준다.

    history 는 그 행의 최근 전송 기록(list[dict], 각 항목에 "at" epoch 초 · "text" · "auto")이고 순서는 가리지 않는다.
    검사 순서: 켬/끔(저장소별 설정이 전체 설정보다 우선) → 에이전트 터미널 → 허용 상태 → 허용 대기 사유 →
    최종 결정 에이전트 → 연속 상한 → 최소 간격. now·agents 는 시험과 사용자 정의 최종 결정 에이전트용 선택 인자.
    """
    repo = str(getattr(row, "repo", "") or "")
    repos = settings.auto_send_repos or {}
    if repo in repos:
        if not repos[repo]:
            return False, f"저장소 {repo} 는 꺼짐"
    elif not settings.auto_send:
        return False, "자동 전송 꺼짐"
    if not getattr(row, "pane_key", None):
        return False, "에이전트 터미널 없음"
    state = auto_state(row.state)
    if state in AUTO_SEND_NEVER_STATES or state not in {auto_state(x) for x in settings.auto_send_states}:
        return False, f"상태 {row.state or '없음'} 은 허용 안 됨"
    kind = wait_kind(row)
    waits = list(settings.auto_send_waits or [])
    if kind in AUTO_SEND_NEVER_WAITS or not (kind in waits or str(row.wait or "").strip() in waits):
        return False, f"대기 사유 {kind} 은 허용 안 됨"
    if settings.auto_send_require_final and not has_final_agent(settings, agents):
        return False, "작성 에이전트에 최종 결정 에이전트 없음"
    limit = int(settings.auto_send_max_streak)
    streak = auto_send_streak(history)
    if streak >= limit:
        return False, f"연속 {limit}회 상한"
    recent = _history_newest_first(history)
    cooldown = int(settings.auto_send_cooldown)
    if recent and cooldown > 0:
        try:
            last = float(recent[0].get("at") or 0)
        except (TypeError, ValueError):
            last = 0.0
        elapsed = max(0.0, (time.time() if now is None else now) - last)
        if elapsed < cooldown:
            return False, f"마지막 전송 후 {int(elapsed)}초 ({cooldown}초 미만)"
    return True, f"허용 (상태 {row.state} · 대기 사유 {kind} · 연속 {streak}/{limit}회)"   # 전송 기록의 policy 에 그대로 남는다


# ---------------------------------------------------------------------------
# 자동 전송: 정책이 허용하고 준비된 제안이 있는 행에 사람 없이 프롬프트를 보내고, 모든 전송을 기록한다.
# ---------------------------------------------------------------------------
SEND_LOG_NAME = "send-log.jsonl"
PROPOSAL_READY = "ready"   # Proposal.status: 보낼 수 있는 상태


def config_dir_of(config_path: str) -> str:
    return os.path.dirname(config_path) or "."


def append_send_record(config_dir: str, record: dict) -> None:
    """<설정 디렉터리>/send-log.jsonl 에 전송 기록 한 줄(JSON)을 덧붙인다. 쓰기 실패는 OSError."""
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, SEND_LOG_NAME), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _read_send_log(config_dir: str) -> list[dict]:
    """기록 전체를 쓴 순서(오래된 것 먼저)로. 파일이 없으면 빈 목록, 깨진 줄은 건너뛴다."""
    out: list[dict] = []
    try:
        with open(os.path.join(config_dir, SEND_LOG_NAME), encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    except OSError:
        pass
    return out


def load_send_history(config_dir: str, row_key: str, limit: int = 20) -> list[dict]:
    """그 행의 최근 전송 기록 limit 개를 오래된 것부터 (마지막 항목이 가장 최근)."""
    recs = [r for r in _read_send_log(config_dir) if r.get("row_key") == row_key]
    return recs[-limit:] if limit else recs


def _sent_ok(rec: dict) -> bool:
    return rec.get("result", "ok") == "ok"



def proposal_ready(proposal: Proposal | None, row: Row) -> bool:
    """자동 전송에 쓸 수 있는 제안인지: 준비 상태이고, 내용이 있고, 행의 지금 턴(updated_at)에 대해 만든 것."""
    return bool(proposal is not None and getattr(proposal, "status", "") == PROPOSAL_READY
                and (getattr(proposal, "text", "") or "").strip()
                and getattr(proposal, "row_updated_at", None) == row.updated_at)


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
    SettingsScreen TabbedContent, SettingsScreen ContentSwitcher, SettingsScreen TabPane { height: 1fr; }
    SettingsScreen TabPane { padding: 0; }
    SettingsScreen #form, SettingsScreen #agent-form, SettingsScreen #auto-form { height: 1fr; }
    SettingsScreen #agent-desc, SettingsScreen #agent-role { color: $text-muted; height: auto; margin-left: 20; }
    SettingsScreen #agent-role { max-height: 6; overflow-y: auto; }
    SettingsScreen #steps { height: auto; }
    SettingsScreen .step { height: 3; }
    SettingsScreen .step > Label { width: 4; padding-top: 1; text-align: right; }
    SettingsScreen .step Input { width: 1fr; }
    SettingsScreen .step Button { min-width: 5; width: 5; margin-left: 1; }
    SettingsScreen #step-buttons { height: auto; margin-left: 4; }
    SettingsScreen #step-buttons Button { margin-left: 0; margin-right: 1; }
    SettingsScreen .section { color: $accent; text-style: bold; margin-top: 1; }
    SettingsScreen .row { height: 3; }
    SettingsScreen .row Label { width: 20; padding-top: 1; }
    SettingsScreen .row Input, SettingsScreen .row Select, SettingsScreen .row Checkbox { width: 1fr; }
    SettingsScreen .hint { color: $text-muted; margin-left: 20; height: auto; }
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
        # 에이전트 탭: 생각의 흐름 편집 상태. base 는 설정 덮어쓰기 전(내장·md 파일) 기본값.
        self.base_agents, _ = load_agents(path, include_hidden=True)   # 진행 판정 에이전트의 단계도 여기서 편집
        self.agents, _ = load_agents(path, settings.agent_steps, include_hidden=True)
        self.steps: dict[str, list[str]] = {a.id: list(a.steps) for a in self.agents}
        self.cur_agent: str = pick_agents(self.agents, settings.ai_agents)[0].id

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
            with TabbedContent(initial="tab-general"):
                with TabPane("일반", id="tab-general"):
                    yield from self._compose_general(s, row)
                with TabPane("에이전트", id="tab-agents"):
                    yield from self._compose_agents(row)
                with TabPane("자동 전송", id="tab-auto"):
                    yield from self._compose_auto(s, row)
            yield Label("", id="form-error")
            with Horizontal(id="buttons"):
                yield Button("취소 (Esc)", id="cancel")
                yield Button("저장·적용 (Enter)", id="save", variant="primary")

    def _compose_general(self, s: Settings, row) -> ComposeResult:
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
                yield from row("에이전트 상황 전달", Checkbox("지시·마지막 응답·저장소 내용(목표 문서·변경분)을 초안 모델에 전달",
                                                      s.ai_context, id="ai_context"))
                yield from row("작성 에이전트", Input(" ".join(s.ai_agents), id="ai_agents",
                                                 placeholder="id 를 실행 순서대로, 공백 구분 (예: goal review)"))
                yield Label("사용 가능: " + " · ".join(f"{a.id}({a.name})" for a in self.agents if a.id not in HIDDEN_AGENT_IDS)
                            + f"\n추가: {agents_dir(self.path)}/<id>.md (frontmatter name·description·context + 지시문). "
                              "프롬프트 창에서도 체크해 고를 수 있음 · 생각의 흐름은 「에이전트」 탭", classes="hint")
                yield from row("백그라운드 제안", Checkbox(
                    "입력 대기·권한 대기·막힘 행의 프롬프트를 위 작성 에이전트로 미리 만들어 둠 (메모 없이, 한 번에 하나씩)",
                    s.auto_draft, id="auto_draft"))
                yield Label("키보드", classes="section")
                yield from row("영문 자동 전환", Checkbox(
                    "메인 화면이 앞에 있을 때 입력 소스를 영문으로 바꿔 한글 상태에서도 단축키가 듣게 함 (macOS)",
                    s.auto_abc, id="auto_abc"))

    def _compose_agents(self, row) -> ComposeResult:
        a = pick_agent(self.agents, self.cur_agent)
        with VerticalScroll(id="agent-form"):
            yield from row("에이전트", Select([(x.label, x.id) for x in self.agents], value=a.id,
                                          allow_blank=False, id="agent-pick"))
            yield Label(self._agent_desc(a), id="agent-desc")
            yield Static(a.instructions.strip(), id="agent-role")
            yield Label("생각의 흐름  (요청의 agent.think_steps 로 전달 — 답을 쓰기 전에 이 순서로 생각하고 최종 프롬프트만 출력)",
                        classes="section")
            with Vertical(id="steps"):
                yield from self._step_rows(self.steps[a.id])
            with Horizontal(id="step-buttons"):
                yield Button("+ 단계 추가", id="step-add")
                yield Button("기본값으로", id="step-reset")

    def _compose_auto(self, s: Settings, row) -> ComposeResult:
        """자동 전송 정책 탭. 값은 _collect_auto 가 읽고 Settings.validate 가 검증한다."""
        with VerticalScroll(id="auto-form"):
            yield from row("자동 전송", Switch(s.auto_send, id="auto_send"))
            yield Label("켜면 아래 조건을 모두 만족하는 행에만 사람 없이 초안을 보냄. 권한 대기·막힘은 항상 사람에게 남김",
                        classes="hint")
            yield from row("허용 상태", Input(" ".join(s.auto_send_states), id="auto_send_states",
                                          placeholder="공백 구분 (기본 waiting_input = 입력 대기)"))
            yield from row("허용 대기 사유", Input(" ".join(s.auto_send_waits), id="auto_send_waits",
                                             placeholder="공백 구분: 질문 · 중단 · 없음 (기본 질문)"))
            yield from row("연속 상한(회)", Input(str(s.auto_send_max_streak), type="integer", id="auto_send_max_streak"))
            yield Label("사람 개입 없이 이어서 보낼 수 있는 횟수. 사람이 직접 한 번 보내면 다시 0부터", classes="hint")
            yield from row("최소 간격(초)", Input(str(s.auto_send_cooldown), type="integer", id="auto_send_cooldown"))
            yield from row("저장소별 켬/끔", Input(format_repo_flags(s.auto_send_repos), id="auto_send_repos",
                                             placeholder="예: repo:on repo2:off (없는 저장소는 위 스위치를 따름)"))
            yield from row("최종 결정 필수", Switch(s.auto_send_require_final, id="auto_send_require_final"))
            yield Label("작성 에이전트에 최종 결정(final) 에이전트가 있을 때만 자동 전송", classes="hint")

    def _collect_auto(self) -> dict:
        q = self.query_one
        return dict(
            auto_send=q("#auto_send", Switch).value,
            auto_send_states=q("#auto_send_states", Input).value,
            auto_send_waits=q("#auto_send_waits", Input).value,
            auto_send_max_streak=q("#auto_send_max_streak", Input).value,
            auto_send_cooldown=q("#auto_send_cooldown", Input).value,
            auto_send_repos=q("#auto_send_repos", Input).value,
            auto_send_require_final=q("#auto_send_require_final", Switch).value,
        )

    def _agent_desc(self, a: DraftAgent) -> str:
        where = "내장" if a.builtin else f"파일 {a.path}"
        return (f"{a.description or '-'}  ·  {where}  ·  컨텍스트: {', '.join(a.context)}"
                + ("" if a.memo else "  ·  사용자 메모: 받지 않음")
                + ("  ·  최종 결정: 다른 에이전트들의 초안을 받아 하나로 정함" if a.final else "")
                + ("  ·  프롬프트 초안용이 아님: 프롬프트 창 Ctrl+T 와 자동 전송 루프가 호출"
                   if a.id in HIDDEN_AGENT_IDS else "")
                + (f"  ·  도구: {', '.join(a.tools)} (저장소 읽기 전용, claude)" if a.tools else "")
                + (f"  ·  모델: {a.model}" if a.model else "")
                + (f"  ·  제한 시간: {a.timeout:g}초" if a.timeout else ""))

    def _step_rows(self, steps: list[str]) -> list:
        """단계 편집 행 위젯들. compose 와 mount 양쪽에서 쓰므로 컨텍스트 매니저 대신 직접 만든다."""
        if not steps:
            return [Label("(단계 없음 — 역할 지시문만으로 작성)", classes="hint", id="steps-empty")]
        return [Horizontal(Label(f"{i + 1}."), Input(text, placeholder="생각 단계", classes="step-input"),
                           Button("-", id=f"step-del-{i}", variant="error"), classes="step")
                for i, text in enumerate(steps)]

    def _sync_steps(self) -> None:
        """에이전트 탭의 Input 내용을 현재 에이전트의 단계 목록으로 읽어 둔다."""
        self.steps[self.cur_agent] = [i.value for i in self.query(".step-input")]

    async def _render_steps(self, focus_last: bool = False) -> None:
        box = self.query_one("#steps", Vertical)
        await box.remove_children()
        await box.mount(*self._step_rows(self.steps[self.cur_agent]))
        if focus_last:
            inputs = list(self.query(".step-input"))
            if inputs:
                inputs[-1].focus()

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "agent-pick" or event.value is Select.BLANK or str(event.value) == self.cur_agent:
            return
        self._sync_steps()
        self.cur_agent = str(event.value)
        a = pick_agent(self.agents, self.cur_agent)
        self.query_one("#agent-desc", Label).update(self._agent_desc(a))
        self.query_one("#agent-role", Static).update(a.instructions.strip())
        await self._render_steps()

    def _collect_steps(self) -> dict[str, list[str]]:
        """기본값과 다른 에이전트만 저장한다 (없는 id = 기본값). 빈 목록은 '단계 없음'으로 저장."""
        self._sync_steps()
        out: dict[str, list[str]] = {}
        for base in self.base_agents:
            steps = [t.strip() for t in self.steps.get(base.id, []) if t.strip()]
            if steps != list(base.steps):
                out[base.id] = steps
        return out

    def on_mount(self) -> None:
        self.query_one("#interval", Input).focus()

    def _collect(self) -> Settings:
        q = self.query_one
        return dataclasses.replace(  # 화면에 없는 항목(자동 전송 정책 등)은 현재 값을 그대로 둔다
            self.settings,
            interval=q("#interval", Input).value,
            orca=q("#orca", Input).value,
            local=q("#local", Checkbox).value,
            env=q("#env", Input).value, host=q("#host", Input).value, ssh=q("#ssh", Input).value,
            ai=str(q("#ai", Select).value),
            ai_model=q("#ai_model", Input).value,
            ai_timeout=q("#ai_timeout", Input).value,
            ai_context=q("#ai_context", Checkbox).value,
            ai_agents=q("#ai_agents", Input).value,
            agent_steps=self._collect_steps(),
            auto_abc=q("#auto_abc", Checkbox).value,
            auto_draft=q("#auto_draft", Checkbox).value,
            **self._collect_auto(),
        )

    def action_save(self) -> None:
        new = self._collect()
        errs = new.validate()
        known = {a.id for a in self.agents if a.id not in HIDDEN_AGENT_IDS}
        unknown = [i for i in new.ai_agents if i not in known]
        if unknown:
            errs.append(f"모르는 작성 에이전트: {', '.join(unknown)}")
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

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "save":
            self.action_save()
        elif bid == "cancel":
            self.dismiss(None)
        elif bid == "step-add":
            self._sync_steps()
            self.steps[self.cur_agent].append("")
            await self._render_steps(focus_last=True)
        elif bid == "step-reset":
            base = pick_agent(self.base_agents, self.cur_agent)
            self.steps[self.cur_agent] = list(base.steps)
            await self._render_steps()
        elif bid.startswith("step-del-"):
            self._sync_steps()
            idx = int(bid.rsplit("-", 1)[1])
            del self.steps[self.cur_agent][idx]
            await self._render_steps()


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
        key_binding("a", "toggle_auto", "자동 전송 정지"),
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
        self.proposals = ProposalStore()            # 백그라운드 제안 (행 키별)
        self._proposal_queue: list[str] = []        # 제안을 만들 행 키, 앞에서부터 하나씩
        self._proposal_worker: Worker | None = None
        self._init_auto_send()

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
                           ("자동 전송", "auto"), ("요약", "summary")]:
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
        self._queue_proposals()
        self._render_table()
        self._auto_send_tick()

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
            self._append_proposal_tag(state_txt, r)
            self._append_verdict(state_txt, r)
            wt = Text(("● " if r.unread else "") + r.worktree)
            table.add_row(state_txt, _ago(r.started_at), r.host, r.repo, wt, r.branch,
                          r.agent_type, r.tool, _clock(r.updated_at), self._auto_cell(r), r.summary, key=r.key)
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
            f"표시 {len(vis)}행 | {summary} | {self._auto_status_text()} | 마지막 조회 {since} (간격 {self.interval}초)"
            + self._verdict_summary()
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

        repo_dir = row.path if (src.label == "local" and row.path and os.path.isdir(row.path)) else None
        # 열 때마다 읽어 새 파일이 바로 보이게. 로컬 저장소면 그 안의 .orca-dash/agents/ 정의가 같은 id 를 덮는다
        agents, agent_errors = load_agents(self.config_path, self.settings.agent_steps, repo_dir=repo_dir)
        screen = PromptScreen(row, self.ai, repo_dir or tempfile.gettempdir(), repo_dir=repo_dir,
                              agents=agents, agent_ids=self.settings.ai_agents, agent_errors=agent_errors)
        self._attach_proposal(screen, row)
        self._attach_verdict(screen, row, repo_dir)

        def on_result(text: str | None) -> None:
            chosen = [a.id for a in screen.chain]
            if chosen != self.settings.ai_agents:
                self.settings.ai_agents = chosen  # 마지막에 쓴 에이전트 조합·순서를 기본으로
                try:
                    self.settings.save(self.config_path)
                except OSError:
                    pass
            if text:
                used = chosen if screen.last_draft else []   # AI 초안을 거쳤을 때만 작성 에이전트를 기록
                self.run_worker(self._send_prompt(src, row, text, agent_ids=used), exclusive=False)

        self._open_modal(screen, on_result)

    async def _send_prompt(self, src: Source, row: Row, text: str, *, auto: bool = False,
                           policy: str = "사람이 직접 전송", agent_ids: list[str] = (),
                           drafts: dict | None = None, head: str = "") -> bool:
        """사람(Enter)과 자동 전송이 함께 쓰는 전송 경로. 성공·실패 모두 send-log.jsonl 에 기록한다."""
        target = f"{row.repo}/{row.worktree}"
        kind = "자동 전송" if auto else "프롬프트 전송"
        self.notify(f"{target} 에 {'자동 ' if auto else ''}전송 중…", timeout=3)
        result = "ok"
        try:
            try:
                msg = await send_prompt(src, row.pane_key or "", text)
            except OrcaError as e:
                result = str(e) or "오류"
            except asyncio.CancelledError:
                result = "취소됨"
                raise
            except Exception as e:  # 기록 없이 사라지는 전송이 없도록
                result = f"{type(e).__name__}: {e}"
        finally:
            self._record_send(row, text, auto=auto, policy=policy, agent_ids=list(agent_ids),
                              drafts=drafts, result=result, head=head)
        if result != "ok":
            self.notify(f"{target}: {result}", title=f"{kind} 실패", severity="error", timeout=10)
            return False
        self.proposals.mark_sent(row)   # 이 턴의 제안은 썼거나(자동) 사람이 대신 답했다 — 지우지 않고 보냄으로
        self._proposals_changed()
        self.notify(f"{target}: {msg}", title=kind, timeout=6)
        self.set_timer(2, self.action_refresh)
        return True

    # --- 자동 전송 -----------------------------------------------------------
    def _init_auto_send(self) -> None:
        self.auto_paused = False                       # a 키로 토글. 켜져 있으면 tick 이 아무것도 보내지 않는다
        if not hasattr(self, "proposals"):
            self.proposals = ProposalStore()           # 행 key → 준비된 제안
        self._auto_sending = False                     # 자동 전송이 진행 중이면 다음 tick 은 건너뛴다
        self._auto_tried: dict[str, float | None] = {}  # 행 key → 자동 전송을 시도한 updated_at (성공·실패 모두)
        self._auto_reasons: dict[str, str] = {}        # 행 key → 마지막 tick 의 판단 (상세 창에 표시)
        self._auto_times: dict[str, list[float]] = {}  # 행 key → 성공한 자동 전송 시각들
        self._log_warned = False
        for rec in _read_send_log(config_dir_of(self.config_path)):
            if rec.get("auto") and _sent_ok(rec) and rec.get("row_key"):
                try:
                    self._auto_times.setdefault(str(rec["row_key"]), []).append(float(rec.get("at") or 0))
                except (TypeError, ValueError):
                    pass

    def _record_send(self, row: Row, text: str, *, auto: bool, policy: str, agent_ids: list[str],
                     drafts: dict | None, result: str, head: str = "") -> None:
        now = time.time()
        rec = {"at": now, "row_key": row.key, "repo": row.repo, "worktree": row.worktree, "branch": row.branch,
               "state": row.state, "wait": row.wait, "agent_ids": agent_ids, "text": text, "auto": auto,
               "policy": policy, "result": result, "row_updated_at": row.updated_at}
        if head:
            rec["head"] = head   # is_stalled 의 '변경 없이 반복' 감지용 저장소 상태 값
        if drafts:
            rec["drafts"] = drafts
        if auto and result == "ok":
            self._auto_times.setdefault(row.key, []).append(now)
        try:
            append_send_record(config_dir_of(self.config_path), rec)
        except OSError as e:
            if not self._log_warned:   # 기록을 못 쓰면 연속 횟수·대기 시간을 셀 수 없으므로 자동 전송을 멈춘다
                self._log_warned = True
                self.auto_paused = True
                self.notify(f"전송 기록을 쓰지 못해 자동 전송을 일시 정지했습니다: {e}", title="전송 기록",
                            severity="error", timeout=10)

    def _auto_enabled(self) -> bool:
        s = self.settings
        return bool(getattr(s, "auto_send", False) or any((getattr(s, "auto_send_repos", None) or {}).values()))

    def _auto_status_text(self) -> str:
        day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today = sum(1 for ts in self._auto_times.values() for t in ts if t >= day)
        mode = "일시 정지" if self.auto_paused else "ON" if self._auto_enabled() else "OFF"
        return f"자동 전송 {mode} · 오늘 {today}회"

    def _auto_cell(self, row: Row) -> str:
        times = self._auto_times.get(row.key)
        return f"{len(times)}회 {_clock(max(times) * 1000)}" if times else ""

    def action_toggle_auto(self) -> None:
        self.auto_paused = not self.auto_paused
        self._auto_reasons = {}
        if self.auto_paused:
            self.notify("자동 전송을 일시 정지했습니다. a 로 재개", title="자동 전송", timeout=4)
        elif self._auto_enabled():
            self.notify("자동 전송을 재개했습니다. 다음 새로고침부터 보냅니다.", title="자동 전송", timeout=4)
        else:
            self.notify("일시 정지는 풀었지만 자동 전송이 꺼져 있습니다 (설정 파일의 auto_send).",
                        title="자동 전송", severity="warning", timeout=6)
        self._tick_status()

    def _auto_send_tick(self) -> Row | None:
        """새로고침 뒤에 호출. 일시 정지가 아니면, 정책이 허용하고 유효한 제안이 있는 행 하나에 그 제안을 보낸다.
        제안이 없으면 보내지 않는다(여기서 초안 체인을 돌리지 않는다). 한 번에 한 행만 보내고, 성공이든 실패든
        그 행의 같은 updated_at 에는 다시 시도하지 않는다. 보내기로 한 행을 돌려준다(없으면 None)."""
        if self.auto_paused or self._auto_sending:
            return None
        store = getattr(self, "proposals", None)
        if store is None:
            return None
        self._auto_reasons = {}
        final_ids: set[str] | None = None
        cdir = config_dir_of(self.config_path)
        open_row = self.screen.row.key if isinstance(self.screen, PromptScreen) else None
        for row in sorted(self.rows, key=lambda r: r.updated_at or 0):   # 가장 오래 기다린 행부터
            src = self.source_by_label.get(row.source)
            if not row.pane_key or src is None or src.file:
                continue
            if row.key in self._auto_tried and self._auto_tried[row.key] == row.updated_at:
                self._auto_reasons[row.key] = "이 턴에는 이미 자동 전송을 시도함"
                continue
            prop = store.get(row.key)
            if not proposal_ready(prop, row):
                continue
            if row.key == open_row:
                self._auto_reasons[row.key] = "프롬프트 창이 열려 있어 보류"
                continue
            history = load_send_history(cdir, row.key)
            if any(h.get("auto") and h.get("row_updated_at") == row.updated_at for h in history):
                self._auto_tried[row.key] = row.updated_at   # 재시작 전에 이 턴에 이미 시도했다
                self._auto_reasons[row.key] = "이 턴에는 이미 자동 전송을 시도함"
                continue
            ok, reason = auto_send_allowed(self.settings, row, history)
            agent_ids = list(getattr(prop, "agent_ids", None) or [])
            if ok and getattr(self.settings, "auto_send_require_final", True):
                if final_ids is None:
                    agents, _ = load_agents(self.config_path)
                    final_ids = {a.id for a in agents if a.final}
                if not final_ids.intersection(agent_ids):
                    ok, reason = False, "최종 결정 에이전트를 거치지 않은 제안"
            if not ok:
                self._auto_reasons[row.key] = f"보류 — {reason}"
                continue
            self._auto_tried[row.key] = row.updated_at
            self._auto_reasons[row.key] = f"전송 — {reason}"
            self._auto_sending = True
            self.run_worker(self._auto_send(src, row, prop, reason, agent_ids), group="auto-send",
                            exclusive=False, exit_on_error=False)
            return row
        return None

    async def _auto_send(self, src: Source, row: Row, prop: Proposal, policy: str, agent_ids: list[str]) -> None:
        """정책이 허용한 행에 실제로 보낸다. 보내기 전에 진행 판정(judge_progress)을 거쳐 달성·막힘이면 보내지 않고
        사람에게 알리며, 그 사실도 전송 기록에 result 로 남긴다 (GOAL.md 「자동 전송 정책」 필수 조건)."""
        try:
            repo_dir = self._repo_dir(row)
            cdir = config_dir_of(self.config_path)
            history = load_send_history(cdir, row.key)
            head = await repo_head(repo_dir)
            verdict = await judge_progress(self.ai, row, repo_dir, history,
                                           agent=load_verdict_agent(self.config_path, self.settings.agent_steps, repo_dir))
            self.set_verdict(row, verdict, alert=True)
            if not verdict.failed and verdict.verdict != "continue":
                why = f"진행 판정 {verdict.label}: {verdict.reason}"
                self._auto_reasons[row.key] = f"보류 — {why}"
                self._record_send(row, prop.text.strip(), auto=True, policy=policy, agent_ids=agent_ids,
                                  drafts=getattr(prop, "drafts", None), result=f"보류: {why}", head=head)
                self._tick_status()
                return
            if verdict.failed:
                policy = f"{policy} · {verdict.reason}"   # 판정을 못 했으면 그 사실을 기록에 남기고 정책대로 보낸다
            await self._send_prompt(src, row, prop.text.strip(), auto=True, policy=policy, agent_ids=agent_ids,
                                    drafts=getattr(prop, "drafts", None), head=head)
        finally:
            self._auto_sending = False

    # --- 백그라운드 제안 --------------------------------------------------------
    def _repo_dir(self, row: Row) -> str | None:
        """로컬 저장소 경로 (action_send_prompt 와 같은 기준). 원격·파일 소스거나 경로가 없으면 None."""
        src = self.source_by_label.get(row.source)
        return row.path if (src is not None and src.label == "local" and row.path and os.path.isdir(row.path)) else None

    def _queue_proposals(self) -> None:
        """새로고침 뒤: 바뀐 행의 제안을 버리고, 제안이 필요한 행을 큐에 넣어 한 번에 하나씩 만든다."""
        self.proposals.sync(self.rows)
        if not (self.settings.auto_draft and self.ai.enabled):
            self._proposal_queue.clear()
            return
        order = sorted(self.rows, key=lambda r: (STATE_STYLE.get(r.state, ("", "", 9))[2], -(r.updated_at or 0)))
        for r in order:
            src = self.source_by_label.get(r.source)
            if src is None or src.file:   # 파일 소스는 보낼 수 없으니 제안도 만들지 않는다
                continue
            if r.key not in self._proposal_queue and needs_proposal(r, self.proposals):
                self._proposal_queue.append(r.key)
        running = self._proposal_worker is not None and self._proposal_worker.is_running
        if self._proposal_queue and not running:
            self._proposal_worker = self.run_worker(self._proposal_loop(), group="proposals", exclusive=True,
                                                    exit_on_error=False)

    async def _proposal_loop(self) -> None:
        while self._proposal_queue:
            key = self._proposal_queue.pop(0)
            row = next((r for r in self.rows if r.key == key), None)   # 기다리는 동안 행이 바뀌었을 수 있다
            if (row is None or not (self.settings.auto_draft and self.ai.enabled)
                    or not needs_proposal(row, self.proposals)):
                continue
            await self._propose(row)

    async def _propose(self, row: Row) -> Proposal:
        """설정의 작성 에이전트 조합으로 (메모 없이) 이 행의 제안을 만들어 저장소에 넣는다. 실패해도 예외 대신
        status="error" 인 제안을 돌려준다. 만드는 사이 행이 바뀌었거나 사용자가 직접 만든 초안이 들어왔으면
        결과를 버린다 (status="stale", 저장소에는 넣지 않음)."""
        prev = self.proposals.current(row)
        agents, _ = load_agents(self.config_path, self.settings.agent_steps, repo_dir=self._repo_dir(row))
        chain = pick_agents(agents, self.settings.ai_agents)
        p = Proposal(row.key, "", [a.id for a in chain], time.time(), row.updated_at, "drafting",
                     attempts=(prev.attempts if prev else 0) + 1)
        self.proposals.put(p)
        self._proposals_changed()
        repo_dir = self._repo_dir(row)
        text, error = "", ""
        try:
            text = await draft_each(self.ai, chain, row, "", {}, repo_dir or tempfile.gettempdir(), repo_dir)
        except asyncio.CancelledError:
            if self.proposals.get(row.key) is p:
                self.proposals.invalidate(row.key)
            raise
        except Exception as e:  # DraftError 외의 예기치 못한 오류도 워커를 죽이지 않고 사유로 남긴다
            error = str(e) or type(e).__name__
        p.created_at = time.time()
        if self.proposals.get(row.key) is not p:
            p.status = "stale"
            return p
        if not error and not text.strip():
            error = "빈 응답"
        p.text, p.error, p.status = text, error, ("error" if error else "ready")
        self._proposals_changed()
        return p

    def _store_draft(self, row: Row, text: str, agent_ids: list[str]) -> None:
        """프롬프트 창에서 사용자가 Ctrl+G 로 만든 초안도 그 행의 제안으로 둔다."""
        self.proposals.put(Proposal(row.key, text, list(agent_ids), time.time(), row.updated_at))
        self._proposals_changed()

    def _attach_proposal(self, screen: PromptScreen, row: Row) -> None:
        """프롬프트 창을 열기 전: 그 행의 제안(준비·실패·작성 중)을 넘기고, 창에서 만든 초안을 받을 길을 건다."""
        screen.proposal = self.proposals.current(row)
        screen.on_draft = lambda text, ids: self._store_draft(row, text, ids)

    def _append_proposal_tag(self, state_txt: Text, row: Row) -> None:
        p = self.proposals.current(row)
        tag = {"drafting": ("제안 …", "cyan"), "ready": ("제안 ✓", "bold green"),
               "error": ("제안 ✗", "red")}.get(p.status) if p else None
        if tag:
            state_txt.append(" · ")
            state_txt.append(*tag)

    def _proposal_detail(self, row: Row) -> str:
        """상세 창에 덧붙이는 제안 본문·실패 사유 (본문의 '[이름]' 머리말이 마크업으로 읽히지 않게 이스케이프)."""
        p = self.proposals.current(row)
        if p is None or p.status not in ("ready", "error"):
            return ""
        body = p.text if p.status == "ready" else f"실패 ({p.attempts}/{PROPOSAL_MAX_ATTEMPTS}회 시도): {p.error}"
        return f"\n\n[b]제안[/] ({_ago(p.created_at * 1000)} 전)\n" + escape(body)

    def _proposals_changed(self) -> None:
        """제안 상태가 바뀌었다: 표의 표시와 상세 창을 다시 그린다 (종료 중이면 조용히 넘어감)."""
        try:
            self._render_table()
            row = self._current_row()
            if row:
                self.query_one("#detail", Static).update(row.detail + self._proposal_detail(row))
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_send_prompt()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        key = event.row_key.value if event.row_key else None
        row = next((r for r in self.rows if r.key == key), None)
        if row:
            why = self._auto_reasons.get(row.key)
            self.query_one("#detail", Static).update(row.detail + self._proposal_detail(row) + self._verdict_detail(row)
                                                     + (f"\n\n[b]자동 전송[/] {escape(why)}" if why else ""))

    # --- 진행 판정 -----------------------------------------------------------
    @property
    def verdicts(self) -> dict[str, tuple[Verdict, float | None]]:
        """행 key → (마지막 판정, 판정 당시 행의 updated_at). __init__ 을 건드리지 않도록 처음 쓸 때 만든다."""
        return self.__dict__.setdefault("_verdicts", {})

    def set_verdict(self, row: Row, verdict: Verdict, *, alert: bool = False) -> None:
        """행의 마지막 판정을 기록하고 표를 다시 그린다. alert 이면 달성·막힘일 때 macOS 알림으로 사람을 부른다
        (자동 전송 루프용 — 사람이 직접 요청한 판정은 알리지 않는다)."""
        self.verdicts[row.key] = (verdict, row.updated_at)
        if alert and not verdict.failed and verdict.verdict in ("done", "stuck"):
            notify_user(f"orca-dash · {verdict.label}", f"{row.repo}/{row.worktree}: {verdict.reason}")
        if self.is_mounted:
            self._render_table()
            if (cur := self._current_row()) is not None and cur.key == row.key:
                self.query_one("#detail", Static).update(row.detail + self._proposal_detail(row) + self._verdict_detail(row))

    def _verdict_of(self, row: Row) -> tuple[Verdict, bool] | None:
        """(판정, 그 뒤로 에이전트가 더 움직였는지). 없으면 None."""
        hit = self.verdicts.get(row.key)
        return (hit[0], hit[1] != row.updated_at) if hit else None

    def _append_verdict(self, state_txt: Text, row: Row) -> None:
        hit = self._verdict_of(row)
        if hit:
            verdict, stale = hit
            state_txt.append(f" · 판정 {verdict.label}" + ("(이전)" if stale else ""),
                             style="dim" if stale else verdict.style)

    def _verdict_detail(self, row: Row) -> str:
        hit = self._verdict_of(row)
        if not hit:
            return ""
        verdict, stale = hit
        return (f"\n\n[b]진행 판정[/] {verdict.label}" + (" (이전 응답 기준)" if stale else "")
                + f" — {escape(verdict.reason)}")

    def _verdict_summary(self) -> str:
        keys = {r.key for r in self.rows}
        counts: dict[str, int] = {}
        for key, (verdict, _) in self.verdicts.items():
            if key in keys and not verdict.failed and verdict.verdict != "continue":
                counts[verdict.label] = counts.get(verdict.label, 0) + 1
        return " | 판정: " + " · ".join(f"{k} {v}" for k, v in counts.items()) if counts else ""

    def _attach_verdict(self, screen: "PromptScreen", row: Row, repo_dir: str | None) -> None:
        """프롬프트 창의 Ctrl+T 가 쓸 전송 기록·판정 에이전트·결과 콜백을 채운다."""
        loader = globals().get("load_send_history")  # 자동 전송 작업이 넣는 전송 기록. 없으면 기록 없이 판정
        try:
            screen.history = list(loader(os.path.dirname(self.config_path) or ".", row.key)) if loader else []
        except Exception:
            screen.history = []
        screen.verdict_agent = load_verdict_agent(self.config_path, self.settings.agent_steps, repo_dir)
        screen.on_verdict = lambda verdict: self.set_verdict(row, verdict)


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
                   help="에이전트의 지시·마지막 응답과 저장소 내용(목표 문서·변경분)을 초안 모델에 전달할지 (기본 on)")
    g.add_argument("--ai-agent", metavar="ID", action="append",
                   help=f"작성 에이전트 (반복하면 그 순서로 이어서 작성). 내장: {', '.join(a.id for a in BUILTIN_AGENTS)}. "
                        "<설정 디렉터리>/agents/<id>.md 로 추가 가능")
    p.add_argument("--auto-send", choices=["on", "off"],
                   help="자동 전송 정책 켬/끔 (기본 off). 허용 조건은 옵션의 「자동 전송」 탭에서 정한다")
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
