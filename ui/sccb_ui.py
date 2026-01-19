# -*- coding: utf-8 -*-

"""
SCCB Automation UI Skeleton (Tkinter)

목표(1단계 UI 골격):
- conf-user / conf-token 등 입력
- "대상 조회" 버튼
- 이슈 리스트 표시(체크/선택)
- 선택 후 "Complete 처리" 버튼
- 로그 창

※ 현재는 네트워크 연동(Confluence/Jira API)은 연결하지 않고,
  UI 구성 + 이벤트 흐름 + 데이터 모델만 만든 골격입니다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from datetime import datetime
from typing import List

from conf_table_read_lib import (
    ConfConfig,
    analyze_storage_for_target_column,
    extract_target_column_rows,
    fetch_confluence_storage_html,
)


def _safe_text(value: str) -> str:
    return value.strip() if value else ""


@dataclass
class IssueRow:
    selected: bool
    key: str
    summary: str
    assignee: str
    status: str


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SCCB Automation UI")
        self.geometry("1100x720")
        self.minsize(1000, 650)

        # state
        self.issues: List[IssueRow] = []
        self._tree_item_to_index: dict[str, int] = {}

        # styles
        self._init_style()

        # layout
        self._build_ui()

        # seed (demo)
        self._log("UI started. (Skeleton mode)")

    def _init_style(self) -> None:
        style = ttk.Style(self)
        # Windows 기본 테마 유지 (과도한 커스터마이징 지양)
        try:
            style.theme_use("clam")
        except Exception:
            pass

    def _build_ui(self) -> None:
        # Root grid
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)   # middle
        self.rowconfigure(2, weight=1)   # log

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1)

        mid = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid.grid(row=1, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(1, weight=1)

        bot = ttk.Frame(self, padding=(10, 0, 10, 10))
        bot.grid(row=2, column=0, sticky="nsew")
        bot.columnconfigure(0, weight=1)
        bot.rowconfigure(1, weight=1)

        # -------- Top: Credentials --------
        cred = ttk.LabelFrame(top, text="Credentials", padding=10)
        cred.grid(row=0, column=0, sticky="nsew")
        for c in range(6):
            cred.columnconfigure(c, weight=1)

        # defaults (필요 시 고정 가능)
        self.var_conf_base = tk.StringVar(value="https://conf-stms.semes.com:18090")
        self.var_conf_page_id = tk.StringVar(value="397731584")

        self.var_jira_base = tk.StringVar(value="https://jira-stms.semes.com:18080")

        self.var_conf_user = tk.StringVar(value="")
        self.var_conf_token = tk.StringVar(value="")
        self.var_jira_user = tk.StringVar(value="")
        self.var_jira_token = tk.StringVar(value="")

        self.var_resolution_name = tk.StringVar(value="완료")  # Complete 시 Resolution 기본값
        self.var_skip_label = tk.StringVar(value="SCCB_SKIP")

        # Row 0
        ttk.Label(cred, text="Conf Base").grid(row=0, column=0, sticky="w")
        ttk.Entry(cred, textvariable=self.var_conf_base).grid(row=0, column=1, sticky="ew", padx=(5, 15))

        ttk.Label(cred, text="Page ID").grid(row=0, column=2, sticky="w")
        ttk.Entry(cred, textvariable=self.var_conf_page_id, width=14).grid(
            row=0,
            column=3,
            sticky="w",
            padx=(5, 15),
        )

        ttk.Label(cred, text="Jira Base").grid(row=0, column=4, sticky="w")
        ttk.Entry(cred, textvariable=self.var_jira_base).grid(row=0, column=5, sticky="ew", padx=(5, 0))

        # Row 1
        ttk.Label(cred, text="Conf User").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cred, textvariable=self.var_conf_user).grid(row=1, column=1, sticky="ew", padx=(5, 15), pady=(8, 0))

        ttk.Label(cred, text="Conf Token").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(cred, textvariable=self.var_conf_token, show="*").grid(row=1, column=3, sticky="ew", padx=(5, 15), pady=(8, 0))

        ttk.Label(cred, text="Skip Label").grid(row=1, column=4, sticky="w", pady=(8, 0))
        ttk.Entry(cred, textvariable=self.var_skip_label, width=18).grid(row=1, column=5, sticky="w", padx=(5, 0), pady=(8, 0))

        # Row 2
        ttk.Label(cred, text="Jira User").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cred, textvariable=self.var_jira_user).grid(row=2, column=1, sticky="ew", padx=(5, 15), pady=(8, 0))

        ttk.Label(cred, text="Jira Token").grid(row=2, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(cred, textvariable=self.var_jira_token, show="*").grid(row=2, column=3, sticky="ew", padx=(5, 15), pady=(8, 0))

        ttk.Label(cred, text="Resolution").grid(row=2, column=4, sticky="w", pady=(8, 0))
        ttk.Entry(cred, textvariable=self.var_resolution_name, width=18).grid(row=2, column=5, sticky="w", padx=(5, 0), pady=(8, 0))

        # Row 3 buttons
        btns = ttk.Frame(cred)
        btns.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(10, 0))
        btns.columnconfigure(0, weight=1)

        self.btn_fetch = ttk.Button(btns, text="대상 조회", command=self.on_fetch)
        self.btn_fetch.grid(row=0, column=0, sticky="w")

        self.btn_select_all = ttk.Button(btns, text="전체 선택", command=lambda: self._set_all_selected(True))
        self.btn_select_all.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.btn_select_none = ttk.Button(btns, text="전체 해제", command=lambda: self._set_all_selected(False))
        self.btn_select_none.grid(row=0, column=2, sticky="w", padx=(8, 0))

        self.btn_complete = ttk.Button(btns, text="선택 Complete 처리", command=self.on_complete_selected)
        self.btn_complete.grid(row=0, column=3, sticky="w", padx=(20, 0))

        self.btn_quit = ttk.Button(btns, text="종료", command=self.destroy)
        self.btn_quit.grid(row=0, column=4, sticky="e")

        # -------- Mid: Issue list --------
        list_frame = ttk.LabelFrame(mid, text="Issues", padding=10)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        columns = ("selected", "key", "summary", "assignee", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.heading("selected", text="선택")
        self.tree.heading("key", text="Issue Key")
        self.tree.heading("summary", text="Summary")
        self.tree.heading("assignee", text="Assignee")
        self.tree.heading("status", text="Status")

        self.tree.column("selected", width=60, anchor="center")
        self.tree.column("key", width=140, anchor="w")
        self.tree.column("summary", width=520, anchor="w")
        self.tree.column("assignee", width=140, anchor="w")
        self.tree.column("status", width=140, anchor="w")

        self.tree.bind("<Double-1>", self.on_tree_double_click)

        hint = ttk.Label(mid, text="Tip: 행 더블클릭으로 선택 토글")
        hint.grid(row=1, column=0, sticky="w", pady=(6, 0))

        # -------- Bottom: Log --------
        log_frame = ttk.LabelFrame(bot, text="Log", padding=10)
        log_frame.grid(row=0, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.txt_log = tk.Text(log_frame, height=10, wrap="word")
        self.txt_log.grid(row=0, column=0, sticky="nsew")

        log_vsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.txt_log.yview)
        log_vsb.grid(row=0, column=1, sticky="ns")
        self.txt_log.configure(yscrollcommand=log_vsb.set)

    # -----------------------------
    # Events
    # -----------------------------
    def on_fetch(self) -> None:
        if not self._validate_basic_inputs():
            return

        self._log("Fetching targets from Confluence...")

        cfg = ConfConfig(
            conf_base=_safe_text(self.var_conf_base.get()),
            conf_context="/wiki",
            page_id=_safe_text(self.var_conf_page_id.get()),
            user=_safe_text(self.var_conf_user.get()),
            token=_safe_text(self.var_conf_token.get()),
        )

        try:
            storage = fetch_confluence_storage_html(cfg)
        except Exception as exc:
            self._handle_fetch_exception(exc)
            return

        try:
            rows = extract_target_column_rows(storage, target_col_name="반영여부")
        except Exception as exc:
            self._log(f"파싱 실패 (jql 또는 table not found): {exc}")
            messagebox.showerror("파싱 실패", f"파싱 실패 (jql 또는 table not found): {exc}")
            return

        parse_info = analyze_storage_for_target_column(storage, target_col_name="반영여부")
        if not parse_info["has_table"] or not parse_info["has_target_column"]:
            self._log("파싱 실패 (jql 또는 table not found)")
            messagebox.showerror("파싱 실패", "파싱 실패 (jql 또는 table not found)")
            return

        if not rows:
            self.issues = []
            self._render_tree()
            self._log("조회 결과 0건")
            messagebox.showinfo("조회 결과", "조회 결과 0건")
            return

        issues: List[IssueRow] = []
        seen = set()
        for row in rows:
            status = row.get("target_cell") or ""
            for key in row.get("issue_keys", []):
                if key in seen:
                    continue
                seen.add(key)
                issues.append(IssueRow(False, key, summary="(Confluence table)", assignee="", status=status))

        self.issues = sorted(issues, key=lambda item: item.key)
        self._render_tree()
        self._log(f"Confluence rows={len(rows)} issues={len(self.issues)}")

    def on_complete_selected(self) -> None:
        """
        1단계: UI 골격에서는 실제 Complete 처리 대신,
        선택된 대상 목록과 입력 파라미터를 로그에 출력합니다.
        """
        selected = [it for it in self.issues if it.selected]
        if not selected:
            messagebox.showinfo("알림", "선택된 이슈가 없습니다.")
            return

        resolution = self.var_resolution_name.get().strip()
        self._log(f"Complete clicked. selected={len(selected)} resolution='{resolution}' (skeleton)")
        for it in selected:
            self._log(f" - {it.key} ({it.status})")

        messagebox.showinfo("Skeleton", "현재는 UI 골격 단계입니다.\n다음 단계에서 실제 Complete API를 연결합니다.")

    def on_tree_double_click(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        idx = self._tree_item_to_index.get(item_id)
        if idx is None:
            return
        self.issues[idx].selected = not self.issues[idx].selected
        self._update_tree_row(item_id, self.issues[idx])

    # -----------------------------
    # Helpers
    # -----------------------------
    def _validate_basic_inputs(self) -> bool:
        # 최소 입력 체크(1단계)
        if not self.var_conf_base.get().strip():
            messagebox.showerror("입력 오류", "Conf Base를 입력하세요.")
            return False
        if not self.var_conf_page_id.get().strip():
            messagebox.showerror("입력 오류", "Conf Page ID를 입력하세요.")
            return False
        if not self.var_jira_base.get().strip():
            messagebox.showerror("입력 오류", "Jira Base를 입력하세요.")
            return False
        if not self.var_conf_user.get().strip():
            messagebox.showerror("입력 오류", "Conf User를 입력하세요.")
            return False
        if not self.var_conf_token.get().strip():
            messagebox.showerror("입력 오류", "Conf Token을 입력하세요.")
            return False
        if not self.var_jira_user.get().strip():
            messagebox.showerror("입력 오류", "Jira User를 입력하세요.")
            return False
        if not self.var_jira_token.get().strip():
            messagebox.showerror("입력 오류", "Jira Token을 입력하세요.")
            return False
        return True

    def _render_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._tree_item_to_index.clear()

        for idx, it in enumerate(self.issues):
            item_id = self.tree.insert(
                "", "end",
                values=("✔" if it.selected else "", it.key, it.summary, it.assignee, it.status),
            )
            self._tree_item_to_index[item_id] = idx

        self._log(f"Issues displayed: {len(self.issues)}")

    def _update_tree_row(self, item_id: str, it: IssueRow) -> None:
        self.tree.item(item_id, values=("✔" if it.selected else "", it.key, it.summary, it.assignee, it.status))

    def _set_all_selected(self, flag: bool) -> None:
        for it in self.issues:
            it.selected = flag
        for item_id, idx in self._tree_item_to_index.items():
            self._update_tree_row(item_id, self.issues[idx])
        self._log(f"Select all set to {flag}. selected={sum(1 for x in self.issues if x.selected)}")

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.txt_log.insert("end", line)
        self.txt_log.see("end")

    def _handle_fetch_exception(self, exc: Exception) -> None:
        message = str(exc)
        status_code = self._extract_status_code(message)
        if status_code in {"401", "403"}:
            self._log(f"인증 실패 (401/403): status={status_code}")
            messagebox.showerror("인증 실패", f"인증 실패 (401/403): status={status_code}")
            return
        self._log(f"Confluence 조회 실패: {message}")
        messagebox.showerror("조회 실패", f"Confluence 조회 실패: {message}")

    @staticmethod
    def _extract_status_code(message: str) -> str | None:
        marker = "status="
        if marker not in message:
            return None
        tail = message.split(marker, 1)[1].strip()
        digits = ""
        for ch in tail:
            if ch.isdigit():
                digits += ch
            else:
                break
        return digits or None


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
