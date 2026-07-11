from __future__ import annotations

import os

# app.py와 동일한 pyarrow mimalloc segfault 우회 (libarrow 로드 전에 설정해야 한다).
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import complaint_agents as ca  # noqa: E402


LAW_URL = "https://www.law.go.kr/test1"
CASE_URL = "https://www.epeople.go.kr/case1"

DEFAULT_RESPONSES: dict[str, dict[str, Any]] = {
    "issue": {
        "requirements": ["민원 처리 기한 안내 요청"],
        "facts": ["2026년 6월 민원을 접수했다"],
        "issues": ["민원 처리 법정 기한"],
        "summary": "민원 처리 기한 문의",
    },
    "jurisdiction": {
        "candidates": [{"department": "행정안전부", "confidence": 0.85, "reason": "민원 제도 총괄"}],
        "uncertainties": [],
        "rationale": "민원처리법 소관 부처",
    },
    "classifier": {
        "department": "행정안전부",
        "complaint_type": "기관운영/서비스 불만",
        "confidence": 0.82,
        "rationale": "두 분석이 일치",
        "issues": ["민원 처리 법정 기한"],
        "search_terms": ["민원 처리 기한", "민원처리법"],
        "decision": "CONTINUE",
    },
    "legal": {
        "legal_bases": [
            {
                "title": "민원 처리에 관한 법률",
                "article": "제17조",
                "claim": "법정 처리기간 내에 민원을 처리해야 한다",
                "url": LAW_URL,
            }
        ],
        "limitations": [],
    },
    "case": {
        "similar_cases": [{"summary": "처리 기한 초과 민원의 안내 사례", "url": CASE_URL}],
        "limitations": [],
    },
    "writer": {
        "draft": (
            "안녕하십니까. 민원 처리 기한을 문의하신 내용에 답변드립니다. "
            "민원 처리에 관한 법률 제17조에 따라 법정 처리기간 내 처리됩니다. "
            "추가 확인이 필요하시면 담당 부서로 문의하시기 바랍니다."
        ),
        "claim_evidence_map": [
            {"claim": "법정 처리기간 내에 민원을 처리해야 한다", "evidence_urls": [LAW_URL]}
        ],
        "uncertainties": [],
    },
    "citation": {"checks": {"evidence": "PASS", "citation": "PASS"}, "findings": []},
    "privacy": {
        "checks": {"input_fidelity": "PASS", "jurisdiction": "PASS", "tone": "PASS", "privacy": "PASS"},
        "findings": [],
    },
}

SYSTEM_KEYWORDS = [
    ("쟁점 분석 Agent다", "issue"),
    ("관할 분석 Agent다", "jurisdiction"),
    ("분류 확정 Agent다", "classifier"),
    ("법령 근거 검색 Agent다", "legal"),
    ("유사 사례 검색 Agent다", "case"),
    ("답변 작성 Agent다", "writer"),
    ("인용 감사 Agent다", "citation"),
    ("개인정보·문체 감사 Agent다", "privacy"),
]


class FakeClient:
    """OpenRouterClient 대역. system 프롬프트로 Agent를 식별해 스크립트된 응답을 준다.

    overrides: agent key → 응답 목록. 문자열이면 그대로 반환, dict면 JSON 직렬화,
    Exception이면 raise. 목록이 소진되면 기본 응답으로 돌아간다.
    """

    def __init__(self, overrides: dict[str, list[Any]] | None = None) -> None:
        self.overrides = {key: list(values) for key, values in (overrides or {}).items()}
        self.calls: list[str] = []

    def chat(self, *, model: str, messages: list[dict[str, str]], **kwargs: Any) -> str:
        system = messages[0]["content"]
        agent_key = None
        for keyword, key in SYSTEM_KEYWORDS:
            if keyword in system:
                agent_key = key
                break
        if agent_key is None:
            raise AssertionError(f"식별할 수 없는 Agent 프롬프트: {system[:80]}")
        self.calls.append(agent_key)

        queue = self.overrides.get(agent_key)
        if queue:
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            if isinstance(item, dict):
                return json.dumps(item, ensure_ascii=False)
            return str(item)
        return json.dumps(DEFAULT_RESPONSES[agent_key], ensure_ascii=False)


def fake_search(query: str, *, max_results: int = 5) -> list[dict[str, str]]:
    if "법령" in query or "law.go.kr" in query:
        return [{"title": "민원 처리에 관한 법률", "url": LAW_URL, "snippet": "법정 처리기간"}]
    return [{"title": "유사 민원 사례", "url": CASE_URL, "snippet": "처리 기한 안내"}]


def empty_search(query: str, *, max_results: int = 5) -> list[dict[str, str]]:
    return []


def fake_fetch(url: str, *, max_chars: int = 1600) -> str:
    return "본문 발췌"


def always_verified(url: str) -> bool:
    return True


def never_verified(url: str) -> bool:
    return False


@pytest.fixture
def make_supervisor(tmp_path):
    def _make(
        overrides: dict[str, list[Any]] | None = None,
        *,
        search_fn=fake_search,
        verify_fn=always_verified,
    ) -> ca.ComplaintSupervisor:
        client = FakeClient(overrides)
        return ca.ComplaintSupervisor(
            client,
            workspace_dir=tmp_path / "_workspace",
            search_fn=search_fn,
            fetch_fn=fake_fetch,
            verify_fn=verify_fn,
            read_pages=False,
        )

    return _make


COMPLAINT = {
    "complaint_id": "C-001",
    "title": "민원 처리 기한 문의",
    "body": "지난달 접수한 민원의 법정 처리 기한이 궁금합니다. 언제까지 처리되는지 알려주세요.",
}


def run_default(supervisor: ca.ComplaintSupervisor, **kwargs: Any) -> dict[str, Any]:
    params = {**COMPLAINT, **kwargs}
    return supervisor.run(
        complaint_id=params["complaint_id"],
        title=params["title"],
        body=params["body"],
        on_event=params.get("on_event"),
    )
