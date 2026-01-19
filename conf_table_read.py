#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Confluence 페이지(REST API body.storage)에서 표를 읽어
- "반영여부" 컬럼을 정확히 찾아
- 각 행의 "반영여부" 셀 텍스트를 출력하고
- (옵션) 반영여부가 "완료"인 행만 추려서 이슈키(예: AMVCSALIVE-1708)까지 같이 출력

핵심:
- 병합 헤더(rowspan/colspan), 2단/3단 그룹 헤더를 그리드로 펼쳐 "합성 헤더명"을 만든 후 컬럼 인덱스를 결정
- 데이터 행도 colspan을 펼쳐서 컬럼 인덱스에 정확히 매칭
"""

from __future__ import annotations

import argparse
import getpass
import os

from conf_table_read_lib import (
    ConfConfig,
    DEFAULT_CONF_BASE,
    DEFAULT_CONF_CONTEXT,
    DEFAULT_PAGE_ID,
    extract_target_column_rows,
    fetch_confluence_storage_html,
    normalize_text,
)


def _prompt_required(label: str, secret: bool = False) -> str:
    prompt = f"{label}: "
    while True:
        if secret:
            value = getpass.getpass(prompt)
        else:
            value = input(prompt).strip()
        if value:
            return value


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf-base", default=DEFAULT_CONF_BASE)
    ap.add_argument("--conf-context", default=DEFAULT_CONF_CONTEXT)
    ap.add_argument("--page-id", default=DEFAULT_PAGE_ID)
    ap.add_argument("--user", default=os.getenv("CONF_USER", ""))
    ap.add_argument("--token", default=os.getenv("CONF_TOKEN", ""))
    ap.add_argument("--col", default="반영여부")
    ap.add_argument("--only-done", action="store_true", help="반영여부에 '완료'가 포함된 행만 출력")
    args = ap.parse_args()

    if not args.conf_base or not args.page_id:
        raise SystemExit(
            "conf-base/page-id가 필요합니다. "
            "환경변수 CONF_BASE/CONF_PAGE_ID를 설정하거나 옵션으로 전달하세요."
        )

    args.user = _prompt_required("ID")
    args.token = _prompt_required("비밀번호", secret=True)

    cfg = ConfConfig(
        conf_base=args.conf_base,
        conf_context=args.conf_context,
        page_id=args.page_id,
        user=args.user,
        token=args.token,
    )

    xhtml = fetch_confluence_storage_html(cfg)
    rows = extract_target_column_rows(xhtml, target_col_name=args.col)

    # 출력: 표/헤더/행/반영여부셀
    done_n = normalize_text("완료")

    # 어떤 표에서 어떤 컬럼으로 매핑되었는지 먼저 요약
    seen = {}
    for r in rows:
        k = (r["table_index"], r["target_col_idx"])
        if k not in seen:
            seen[k] = r["columns"]
    for (t_idx, col_idx), cols in sorted(seen.items()):
        print(f"\n=== TABLE #{t_idx} ===")
        print(f"타겟 컬럼 인덱스: {col_idx}")
        # 컬럼명 전체가 길 수 있으니 처음 30개만 표시
        for i, name in enumerate(cols[:30]):
            mark = "  <-- TARGET" if i == col_idx else ""
            print(f"  [{i:02d}] {name}{mark}")
        if len(cols) > 30:
            print(f"  ... (총 {len(cols)}개 컬럼)")

    print("\n--- ROWS ---")
    cnt = 0
    for r in rows:
        cell_n = normalize_text(r["target_cell"])
        if args.only_done and (done_n not in cell_n):
            continue
        cnt += 1
        keys = ", ".join(r["issue_keys"]) if r["issue_keys"] else "-"
        print(
            f"[T{r['table_index']}] row={r['row_index']:03d} "
            f"{args.col}='{r['target_cell']}' keys={keys}"
        )

    print(f"\n출력 행 수: {cnt}")


if __name__ == "__main__":
    main()
