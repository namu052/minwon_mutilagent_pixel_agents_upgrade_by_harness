from __future__ import annotations

import json
from pathlib import Path

import complaint_agents as ca

from conftest import (
    COMPLAINT,
    DEFAULT_RESPONSES,
    LAW_URL,
    empty_search,
    run_default,
)


def trace_files(result) -> set[str]:
    trace_dir = Path(result["trace_dir"])
    return {str(p.relative_to(trace_dir)) for p in trace_dir.rglob("*.json")}


REVISE_CITATION_AUDIT = {
    "checks": {"evidence": "PASS", "citation": "FAIL"},
    "findings": [
        {
            "severity": "MEDIUM",
            "category": "citation",
            "message": "인용 표기가 불명확합니다.",
            "fix": "근거 인용을 명확히 표기하십시오.",
        }
    ],
}


class TestHappyPath:
    def test_full_pipeline_approves(self, make_supervisor):
        supervisor = make_supervisor()
        result = run_default(supervisor)

        assert result["final_state"] == "PUBLISHED"
        assert result["final_output"]["status"] == "DRAFT_APPROVED"
        assert result["final_output"]["citations"] == [LAW_URL]
        assert result["final_output"]["validation_report"]["decision"] == "PASS"

        files = trace_files(result)
        for name in ca.STANDARD_ARTIFACTS.values():
            assert name in files
        assert "manifest.json" in files
        assert "intermediate/issue_analysis.json" in files
        assert "intermediate/jurisdiction_analysis.json" in files

    def test_state_history_matches_allowed_map(self, make_supervisor):
        result = run_default(make_supervisor())
        states = [h["state"] for h in result["state_history"]]
        assert states == [
            "RECEIVED", "NORMALIZED", "CLASSIFIED", "EVIDENCE_READY",
            "DRAFT_READY", "VALIDATING", "APPROVED", "PUBLISHED",
        ]

    def test_rerun_isolated(self, make_supervisor):
        first = run_default(make_supervisor())
        second = run_default(make_supervisor())
        assert first["trace_id"] != second["trace_id"]
        assert first["trace_dir"] != second["trace_dir"]
        second_events = second["pixel_runtime"]["events"]
        assert all(e["trace_id"] == second["trace_id"] for e in second_events)


class TestRevisionLoop:
    def test_revise_then_pass(self, make_supervisor):
        supervisor = make_supervisor({"citation": [REVISE_CITATION_AUDIT]})
        result = run_default(supervisor)

        assert result["final_output"]["status"] == "DRAFT_APPROVED"
        assert result["artifacts"]["draft_package"]["revision_count"] == 1
        assert len(result["revision_history"]) == 1
        # REVISE는 writer와 두 감사 Agent를 모두 재호출한다.
        calls = supervisor.client.calls
        assert calls.count("writer") == 2
        assert calls.count("citation") == 2
        assert calls.count("privacy") == 2
        states = [h["state"] for h in result["state_history"]]
        assert states.count("VALIDATING") == 2
        assert "REVISION_REQUIRED" in states

    def test_two_revisions_then_human_review(self, make_supervisor):
        supervisor = make_supervisor(
            {"citation": [REVISE_CITATION_AUDIT, REVISE_CITATION_AUDIT, REVISE_CITATION_AUDIT]}
        )
        result = run_default(supervisor)

        assert result["final_output"]["status"] == "HUMAN_REVIEW_REQUIRED"
        assert result["final_output"]["answer"] is None
        assert result["artifacts"]["draft_package"]["revision_count"] == ca.MAX_REVISIONS
        # PASS 승격이 아닌 사람 검토 전환이어야 한다.
        assert result["artifacts"]["validation_report"]["decision"] == "REVISE"
        states = [h["state"] for h in result["state_history"]]
        assert states.count("VALIDATING") == ca.MAX_REVISIONS + 1
        assert states[-2] == "HUMAN_REVIEW_REQUIRED"


class TestEarlyExits:
    def test_input_rejected_skips_downstream(self, make_supervisor):
        supervisor = make_supervisor()
        result = run_default(supervisor, title="", body="")

        assert result["final_output"]["status"] == "INPUT_REJECTED"
        assert supervisor.client.calls == []  # 후속 LLM Agent 미실행
        files = trace_files(result)
        assert "01_intake_result.json" in files
        assert "06_final_output.json" in files
        assert "02_classification_result.json" not in files
        manifest = result["manifest"]
        assert "classification_result" in manifest["skipped_stages"]

    def test_high_risk_privacy_escalates(self, make_supervisor):
        supervisor = make_supervisor()
        result = run_default(
            supervisor, body="주민등록번호 900101-1234567 정정을 요청합니다. 처리 부탁드립니다."
        )
        assert result["final_output"]["status"] == "HUMAN_REVIEW_REQUIRED"
        assert supervisor.client.calls == []

    def test_classifier_escalate_stops_before_search(self, make_supervisor):
        classifier = dict(DEFAULT_RESPONSES["classifier"])
        classifier["decision"] = "ESCALATE"
        supervisor = make_supervisor({"classifier": [classifier]})
        result = run_default(supervisor)

        assert result["final_output"]["status"] == "HUMAN_REVIEW_REQUIRED"
        assert "legal" not in supervisor.client.calls
        assert "writer" not in supervisor.client.calls

    def test_low_confidence_forced_escalate(self, make_supervisor):
        classifier = dict(DEFAULT_RESPONSES["classifier"])
        classifier["confidence"] = 0.2
        supervisor = make_supervisor({"classifier": [classifier]})
        result = run_default(supervisor)
        assert result["final_output"]["status"] == "HUMAN_REVIEW_REQUIRED"

    def test_no_search_results_escalates_without_draft(self, make_supervisor):
        supervisor = make_supervisor(search_fn=empty_search)
        result = run_default(supervisor)

        assert result["final_output"]["status"] == "HUMAN_REVIEW_REQUIRED"
        assert "writer" not in supervisor.client.calls
        assert result["artifacts"]["evidence_package"]["decision"] == "ESCALATE"

    def test_unverified_evidence_escalates(self, make_supervisor):
        supervisor = make_supervisor(verify_fn=lambda url: False)
        result = run_default(supervisor)
        assert result["final_output"]["status"] == "HUMAN_REVIEW_REQUIRED"
        assert "writer" not in supervisor.client.calls


class TestFailureHandling:
    def test_parallel_cell_failure_retries_then_escalates(self, make_supervisor):
        errors = [ca.OpenRouterError("네트워크 오류")] * 8
        supervisor = make_supervisor({"issue": list(errors)})
        result = run_default(supervisor)

        assert result["final_output"]["status"] == "HUMAN_REVIEW_REQUIRED"
        # 셀 실행 실패 후 재시도까지 수행했는지 확인 (call_agent_json 2회 × 셀 재시도 2회)
        assert supervisor.client.calls.count("issue") >= 2
        events = result["pixel_runtime"]["events"]
        assert any(e["type"] == "agentToolFailed" for e in events)
        assert any(e["type"] == "supervisorDecision" for e in events)

    def test_auditor_total_failure_escalates(self, make_supervisor):
        # privacy auditor는 결정적 finding이 없으면 LLM 실패 시 ESCALATE한다.
        errors = [ca.OpenRouterError("호출 실패")] * 8
        supervisor = make_supervisor({"privacy": list(errors)})
        result = run_default(supervisor)
        assert result["final_output"]["status"] == "HUMAN_REVIEW_REQUIRED"
        assert result["final_output"]["answer"] is None


class TestSafety:
    def test_events_do_not_leak_raw_body_or_key(self, make_supervisor):
        supervisor = make_supervisor()
        result = run_default(supervisor)
        blob = json.dumps(result["pixel_runtime"]["events"], ensure_ascii=False)
        blob += json.dumps(result["manifest"], ensure_ascii=False)
        assert COMPLAINT["body"] not in blob
        assert "sk-or-" not in blob

    def test_trace_files_do_not_contain_api_key(self, make_supervisor):
        supervisor = make_supervisor()
        result = run_default(supervisor)
        for path in Path(result["trace_dir"]).rglob("*.json"):
            assert "sk-or-" not in path.read_text(encoding="utf-8")

    def test_body_only_in_intake_artifact(self, make_supervisor):
        supervisor = make_supervisor()
        result = run_default(supervisor)
        trace_dir = Path(result["trace_dir"])
        for path in trace_dir.rglob("*.json"):
            rel = str(path.relative_to(trace_dir))
            if rel == "01_intake_result.json":
                continue
            content = path.read_text(encoding="utf-8")
            if rel.startswith("intermediate/") or rel in ("events.json", "manifest.json"):
                assert COMPLAINT["body"] not in content, rel


class TestEventOrdering:
    def test_seq_monotonic_and_barrier(self, make_supervisor):
        result = run_default(make_supervisor())
        events = result["pixel_runtime"]["events"]
        seqs = [e["seq"] for e in events]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)

        def done_seq(agent_id):
            return max(
                e["seq"] for e in events
                if e["type"] == "agentToolDone" and e["agent_id"] == agent_id
            )

        def start_seq(agent_id):
            return min(
                e["seq"] for e in events
                if e["type"] == "agentToolStart" and e["agent_id"] == agent_id
            )

        # 취합 Agent는 병렬 셀 완료 후에만 시작한다 (barrier).
        assert start_seq("classifier-agent") > done_seq("issue-analysis-agent")
        assert start_seq("classifier-agent") > done_seq("jurisdiction-analysis-agent")
        assert start_seq("evidence-search-agent") > done_seq("legal-research-agent")
        assert start_seq("evidence-search-agent") > done_seq("similar-case-agent")
        assert start_seq("response-validator-agent") > done_seq("claim-citation-auditor")
        assert start_seq("response-validator-agent") > done_seq("privacy-tone-auditor")

    def test_final_status_event_last(self, make_supervisor):
        result = run_default(make_supervisor())
        events = result["pixel_runtime"]["events"]
        final_events = [e for e in events if e["type"] == "finalStatus"]
        assert len(final_events) == 1
        assert "DRAFT_APPROVED" in final_events[0]["safe_summary"]

    def test_handoff_events_reference_files(self, make_supervisor):
        result = run_default(make_supervisor())
        events = result["pixel_runtime"]["events"]
        handoffs = [e for e in events if e["type"] == "handoffProduced"]
        summaries = " ".join(e["safe_summary"] for e in handoffs)
        for name in ca.STANDARD_ARTIFACTS.values():
            assert name in summaries
