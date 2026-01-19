# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import requests


@dataclass
class JiraConfig:
    jira_base: str
    user: str
    token: str
    timeout_sec: int = 30


def _jira_auth(cfg: JiraConfig) -> Tuple[str, str]:
    return cfg.user, cfg.token


def _extract_jira_error_message(response: requests.Response) -> str:
    if response is None:
        return "Jira 응답을 받지 못했습니다."
    try:
        payload = response.json()
    except Exception:
        text = response.text or ""
        return f"status={response.status_code} body={text.strip()}"

    messages = payload.get("errorMessages") or []
    errors = payload.get("errors") or {}

    parts = []
    if messages:
        parts.append("; ".join(str(msg) for msg in messages))
    if errors:
        parts.append("; ".join(f"{k}: {v}" for k, v in errors.items()))
    if not parts:
        return f"status={response.status_code} body={response.text.strip()}"
    return f"status={response.status_code} " + " | ".join(parts)


def fetch_issue_status(cfg: JiraConfig, issue_key: str) -> Tuple[bool, str]:
    url = f"{cfg.jira_base}/rest/api/2/issue/{issue_key}"
    response = requests.get(
        url,
        params={"fields": "status"},
        headers={"Accept": "application/json"},
        auth=_jira_auth(cfg),
        timeout=cfg.timeout_sec,
    )
    if response.status_code != 200:
        return False, _extract_jira_error_message(response)
    payload = response.json()
    try:
        status_name = payload["fields"]["status"]["name"]
    except Exception:
        return False, "Jira 상태 정보를 파싱하지 못했습니다."
    return True, status_name


def fetch_transitions(cfg: JiraConfig, issue_key: str) -> Tuple[bool, list[Dict[str, Any]] | str]:
    url = f"{cfg.jira_base}/rest/api/2/issue/{issue_key}/transitions"
    response = requests.get(
        url,
        params={"expand": "transitions.fields"},
        headers={"Accept": "application/json"},
        auth=_jira_auth(cfg),
        timeout=cfg.timeout_sec,
    )
    if response.status_code != 200:
        return False, _extract_jira_error_message(response)
    payload = response.json()
    return True, payload.get("transitions", [])


def find_complete_transition(transitions: list[Dict[str, Any]], target_name: str = "Complete") -> Dict[str, Any] | None:
    for transition in transitions:
        if transition.get("name") == target_name:
            return transition
    for transition in transitions:
        to_name = (transition.get("to") or {}).get("name")
        if to_name == target_name:
            return transition
    return None


def transition_issue_to_complete(
    cfg: JiraConfig,
    issue_key: str,
    resolution_name: str,
    from_status_name: str = "승인요청",
    target_status_name: str = "Complete",
) -> Tuple[bool, str]:
    if not resolution_name:
        return False, "Resolution 값이 비어 있습니다."

    status_ok, status_or_error = fetch_issue_status(cfg, issue_key)
    if not status_ok:
        return False, f"상태 조회 실패: {status_or_error}"
    if status_or_error != from_status_name:
        return False, f"현재 상태가 '{from_status_name}'가 아닙니다. (현재: {status_or_error})"

    transitions_ok, transitions_or_error = fetch_transitions(cfg, issue_key)
    if not transitions_ok:
        return False, f"전이 조회 실패: {transitions_or_error}"

    transition = find_complete_transition(transitions_or_error, target_name=target_status_name)
    if not transition:
        return False, f"전이 '{target_status_name}'를 찾지 못했습니다."

    url = f"{cfg.jira_base}/rest/api/2/issue/{issue_key}/transitions"
    payload = {
        "transition": {"id": transition["id"]},
        "fields": {"resolution": {"name": resolution_name}},
    }
    response = requests.post(
        url,
        json=payload,
        headers={"Accept": "application/json"},
        auth=_jira_auth(cfg),
        timeout=cfg.timeout_sec,
    )

    if response.status_code not in {200, 204}:
        return False, f"전이 실패: {_extract_jira_error_message(response)}"

    return True, f"{issue_key} 전이 완료 ({target_status_name})"
