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

import re
import os
import argparse
import getpass
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

import requests
from bs4 import BeautifulSoup

ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
DEFAULT_CONF_BASE = os.getenv("CONF_BASE", "https://conf-stms.semes.com:18090")
DEFAULT_CONF_CONTEXT = os.getenv("CONF_CONTEXT", "/wiki")
DEFAULT_PAGE_ID = os.getenv("CONF_PAGE_ID", "")


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = s.replace("\xa0", " ")
    s = s.strip()
    s = re.sub(r"\s+", "", s)
    return s.lower()


def _cell_text(tag) -> str:
    return tag.get_text(" ", strip=True) if tag else ""


def _prompt_if_empty(label: str, current: str, secret: bool = False) -> str:
    if current:
        return current
    prompt = f"{label}: "
    if secret:
        return getpass.getpass(prompt)
    return input(prompt).strip()


@dataclass
class ConfConfig:
    conf_base: str                 # 예: https://conf-stms.semes.com:18090
    conf_context: str              # 예: "" 또는 "/wiki"
    page_id: str
    user: str
    token: str                     # Basic Auth password 또는 PAT(환경에 맞게)
    timeout_sec: int = 30


def fetch_confluence_storage_html(cfg: ConfConfig) -> str:
    """
    Confluence REST API 호출 -> body.storage.value (XHTML) 반환
    /wiki 환경 섞임 대비로 2개 URL을 순차 시도
    """
    auth = (cfg.user, cfg.token)
    ctx = (cfg.conf_context or "").strip()

    urls = []
    if ctx:
        urls.append(f"{cfg.conf_base}{ctx}/rest/api/content/{cfg.page_id}")
        urls.append(f"{cfg.conf_base}/rest/api/content/{cfg.page_id}")
    else:
        urls.append(f"{cfg.conf_base}/rest/api/content/{cfg.page_id}")
        urls.append(f"{cfg.conf_base}/wiki/rest/api/content/{cfg.page_id}")

    last_status = None
    last_text = ""
    for url in urls:
        r = requests.get(
            url,
            params={"expand": "body.storage"},
            headers={"Accept": "application/json"},
            auth=auth,
            timeout=cfg.timeout_sec,
        )
        last_status = r.status_code
        last_text = r.text or ""
        if r.status_code != 200:
            continue
        j = r.json()
        try:
            return j["body"]["storage"]["value"]
        except Exception as e:
            raise RuntimeError(f"Confluence 응답 파싱 실패: {e}")

    raise RuntimeError(f"Confluence 호출 실패: status={last_status}, body_head={last_text[:200].replace(chr(10),' ')}")


def _row_has_issue_key(tr) -> bool:
    txt = tr.get_text(" ", strip=True) or ""
    return bool(ISSUE_KEY_RE.search(txt))


def _count_cols_in_tr(tr) -> int:
    cnt = 0
    for cell in tr.find_all(["th", "td"]):
        try:
            colspan = int(cell.get("colspan", "1") or "1")
        except Exception:
            colspan = 1
        cnt += max(1, colspan)
    return cnt


def _max_cols(rows: List) -> int:
    mx = 0
    for tr in rows:
        mx = max(mx, _count_cols_in_tr(tr))
    return mx


def _detect_header_row_count(rows: List, scan_limit: int = 30) -> int:
    """
    상단에서부터 스캔하면서 "이슈키가 처음 등장하는 행" 직전까지를 헤더 영역으로 간주.
    (그룹 헤더/병합 헤더가 여러 줄이어도 자연스럽게 포함됨)
    """
    lim = min(scan_limit, len(rows))
    for i in range(lim):
        if _row_has_issue_key(rows[i]):
            return i
    # 이슈키를 못 찾으면, 상단 2줄 정도만 헤더로 가정
    return min(2, len(rows))


def _build_header_grid(header_rows: List) -> List[List[str]]:
    """
    헤더 영역을 rowspan/colspan 고려해서 그리드로 펼친다.
    grid[r][c] = 해당 위치의 헤더 텍스트(최상단 기준으로 채움)
    """
    nrows = len(header_rows)
    ncols = _max_cols(header_rows)
    grid = [["" for _ in range(ncols)] for _ in range(nrows)]
    occupied = [[False for _ in range(ncols)] for _ in range(nrows)]

    def advance(r: int, c: int) -> int:
        while c < ncols and occupied[r][c]:
            c += 1
        return c

    for r, tr in enumerate(header_rows):
        c = 0
        for cell in tr.find_all(["th", "td"]):
            c = advance(r, c)
            if c >= ncols:
                break

            text = _cell_text(cell)

            try:
                colspan = int(cell.get("colspan", "1") or "1")
            except Exception:
                colspan = 1
            try:
                rowspan = int(cell.get("rowspan", "1") or "1")
            except Exception:
                rowspan = 1

            colspan = max(1, colspan)
            rowspan = max(1, rowspan)

            for rr in range(r, min(nrows, r + rowspan)):
                for cc in range(c, min(ncols, c + colspan)):
                    # 첫 행(해당 cell이 존재하는 행)의 텍스트를 대표로 저장
                    if rr == r and not grid[rr][cc]:
                        grid[rr][cc] = text
                    occupied[rr][cc] = True

            c += colspan

    return grid


def _compose_columns(header_grid: List[List[str]]) -> List[str]:
    """
    컬럼별로 위->아래 헤더 텍스트를 모아서 합성 컬럼명 생성
    """
    if not header_grid:
        return []
    nrows = len(header_grid)
    ncols = len(header_grid[0])

    cols = []
    for c in range(ncols):
        parts = []
        for r in range(nrows):
            t = (header_grid[r][c] or "").strip()
            if t and (not parts or parts[-1] != t):
                parts.append(t)
        cols.append(" / ".join(parts))
    return cols


def _expand_data_row_by_colspan(tr, ncols: int) -> List[str]:
    """
    데이터 행을 colspan 기준으로 펼쳐서 ncols 길이의 셀 텍스트 리스트로 만든다.
    """
    out = []
    for cell in tr.find_all(["td", "th"]):
        txt = _cell_text(cell)
        try:
            colspan = int(cell.get("colspan", "1") or "1")
        except Exception:
            colspan = 1
        colspan = max(1, colspan)
        out.extend([txt] * colspan)
        if len(out) >= ncols:
            break
    if len(out) < ncols:
        out.extend([""] * (ncols - len(out)))
    return out[:ncols]


def extract_target_column_rows(
    storage_xhtml: str,
    target_col_name: str = "반영여부",
) -> List[Dict[str, Any]]:
    """
    반환:
      [
        {
          "table_index": 0,
          "columns": [... 합성 컬럼명 ...],
          "target_col_idx": 12,
          "row_index": 5,                 # (table 내부에서) data row index
          "target_cell": "완료",
          "issue_keys": ["AMVCSALIVE-1708", ...],  # 행에서 발견된 이슈키(있으면)
          "row_cells": [... ncols ...],   # 필요 시 전체 행 값
        },
        ...
      ]
    """
    soup = BeautifulSoup(storage_xhtml, "lxml")
    target_n = _norm(target_col_name)

    results: List[Dict[str, Any]] = []

    for t_idx, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_cnt = _detect_header_row_count(rows)
        header_rows = rows[:header_cnt]
        data_rows = rows[header_cnt:]

        if not header_rows or not data_rows:
            continue

        header_grid = _build_header_grid(header_rows)
        columns = _compose_columns(header_grid)
        ncols = len(columns)

        # 타겟 컬럼 인덱스 찾기(합성 컬럼명에서 부분 포함)
        target_idx: Optional[int] = None
        for i, col in enumerate(columns):
            if target_n in _norm(col):
                target_idx = i
                break
        if target_idx is None:
            continue

        for r_i, tr in enumerate(data_rows):
            # 데이터가 없는 행 제외(원하면 이 조건 제거 가능)
            if not tr.find_all(["td", "th"]):
                continue

            expanded = _expand_data_row_by_colspan(tr, ncols)
            target_cell = expanded[target_idx] if target_idx < len(expanded) else ""

            # 이슈키 추출(있으면)
            text_blob = tr.get_text(" ", strip=True) or ""
            issue_keys = sorted(set(m.group(0) for m in ISSUE_KEY_RE.finditer(text_blob)))

            results.append({
                "table_index": t_idx,
                "columns": columns,
                "target_col_idx": target_idx,
                "row_index": r_i,
                "target_cell": target_cell,
                "issue_keys": issue_keys,
                "row_cells": expanded,
            })

    return results


def main():
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

    args.user = _prompt_if_empty("user", args.user)
    args.token = _prompt_if_empty("token", args.token, secret=True)

    if not args.user or not args.token:
        raise SystemExit("user/token 값이 필요합니다.")

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
    done_n = _norm("완료")

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
        cell_n = _norm(r["target_cell"])
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
