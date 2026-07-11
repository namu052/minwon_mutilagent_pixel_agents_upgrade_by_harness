from __future__ import annotations

import json

import pytest

import complaint_agents as ca


def valid_validation_report(**over):
    report = {
        "decision": "PASS",
        "checks": {key: "PASS" for key in ca.CHECK_KEYS},
        "findings": [],
        "revision_instructions": [],
        "validated_at": "2026-07-11T00:00:00+00:00",
    }
    report.update(over)
    return report


def valid_final_output(**over):
    output = {
        "status": "DRAFT_APPROVED",
        "answer": "답변 초안",
        "citations": ["https://www.law.go.kr/a"],
        "validation_report": valid_validation_report(),
        "disclaimer": ca.DISCLAIMER,
        "trace_id": "t1",
    }
    output.update(over)
    return output


class TestClassificationResult:
    BASE = {
        "department": "행정안전부",
        "complaint_type": "기타",
        "confidence": 0.7,
        "rationale": "r",
        "issues": ["i"],
        "search_terms": ["t"],
        "decision": "CONTINUE",
    }

    def test_roundtrip(self):
        validated = ca.validate_classification_result(dict(self.BASE))
        assert json.loads(json.dumps(validated, ensure_ascii=False)) == validated

    def test_missing_field(self):
        data = dict(self.BASE)
        del data["department"]
        with pytest.raises(ca.ContractViolation):
            ca.validate_classification_result(data)

    def test_bad_enum(self):
        with pytest.raises(ca.ContractViolation):
            ca.validate_classification_result({**self.BASE, "decision": "MAYBE"})

    def test_string_confidence(self):
        with pytest.raises(ca.ContractViolation):
            ca.validate_classification_result({**self.BASE, "confidence": "높음"})

    def test_out_of_range_confidence(self):
        with pytest.raises(ca.ContractViolation):
            ca.validate_classification_result({**self.BASE, "confidence": 1.4})


class TestEvidencePackage:
    def base(self, **item_over):
        item = {
            "title": "민원 처리에 관한 법률",
            "article": "제17조",
            "claim": "처리기간 준수",
            "url": "https://www.law.go.kr/a",
            "source_type": "OFFICIAL",
            "verified": True,
        }
        item.update(item_over)
        return {
            "legal_bases": [item],
            "similar_cases": [],
            "conflicts": [],
            "coverage_gaps": [],
            "decision": "CONTINUE",
        }

    def test_roundtrip(self):
        assert ca.validate_evidence_package(self.base())["legal_bases"][0]["verified"] is True

    def test_verified_requires_url(self):
        with pytest.raises(ca.ContractViolation):
            ca.validate_evidence_package(self.base(url=""))

    def test_unverified_with_empty_url_allowed(self):
        package = self.base(url="", verified=False)
        assert ca.validate_evidence_package(package)["decision"] == "CONTINUE"

    def test_bad_source_type(self):
        with pytest.raises(ca.ContractViolation):
            ca.validate_evidence_package(self.base(source_type="BLOG"))


class TestValidationReport:
    def test_pass_with_blocker_rejected(self):
        report = valid_validation_report(
            findings=[{"severity": "BLOCKER", "message": "m", "fix": "f"}]
        )
        with pytest.raises(ca.ContractViolation):
            ca.validate_validation_report(report)

    def test_pass_with_high_privacy_rejected(self):
        report = valid_validation_report(
            findings=[{"severity": "HIGH", "category": "privacy", "message": "m", "fix": "f"}]
        )
        with pytest.raises(ca.ContractViolation):
            ca.validate_validation_report(report)

    def test_revise_with_blocker_allowed(self):
        report = valid_validation_report(
            decision="REVISE",
            findings=[{"severity": "BLOCKER", "message": "m", "fix": "f"}],
        )
        assert ca.validate_validation_report(report)["decision"] == "REVISE"

    def test_bad_check_value(self):
        report = valid_validation_report()
        report["checks"]["tone"] = "OK"
        with pytest.raises(ca.ContractViolation):
            ca.validate_validation_report(report)


class TestFinalOutput:
    def test_approved_roundtrip(self):
        validated = ca.validate_final_output(valid_final_output())
        assert validated["status"] == "DRAFT_APPROVED"

    def test_approved_without_pass_rejected(self):
        output = valid_final_output(
            validation_report=valid_validation_report(decision="REVISE")
        )
        with pytest.raises(ca.ContractViolation):
            ca.validate_final_output(output)

    def test_non_approved_must_not_expose_answer(self):
        output = valid_final_output(status="HUMAN_REVIEW_REQUIRED")
        with pytest.raises(ca.ContractViolation):
            ca.validate_final_output(output)

    def test_human_review_shape(self):
        output = valid_final_output(
            status="HUMAN_REVIEW_REQUIRED",
            answer=None,
            validation_report=valid_validation_report(decision="ESCALATE"),
        )
        assert ca.validate_final_output(output)["answer"] is None


class TestStateMachine:
    def test_happy_path(self):
        sm = ca.PipelineStateMachine()
        for state in ["NORMALIZED", "CLASSIFIED", "EVIDENCE_READY", "DRAFT_READY",
                      "VALIDATING", "APPROVED", "PUBLISHED"]:
            sm.transition(state)
        assert sm.state == "PUBLISHED"

    def test_revision_loop_transitions(self):
        sm = ca.PipelineStateMachine()
        for state in ["NORMALIZED", "CLASSIFIED", "EVIDENCE_READY", "DRAFT_READY", "VALIDATING"]:
            sm.transition(state)
        sm.transition("REVISION_REQUIRED")
        sm.transition("DRAFT_READY")
        sm.transition("VALIDATING")
        sm.transition("HUMAN_REVIEW_REQUIRED")
        sm.transition("PUBLISHED")

    def test_undefined_transition_rejected(self):
        sm = ca.PipelineStateMachine()
        with pytest.raises(ca.InvalidStateTransition):
            sm.transition("APPROVED")

    def test_evidence_ready_cannot_escalate_directly(self):
        sm = ca.PipelineStateMachine()
        for state in ["NORMALIZED", "CLASSIFIED", "EVIDENCE_READY"]:
            sm.transition(state)
        with pytest.raises(ca.InvalidStateTransition):
            sm.transition("HUMAN_REVIEW_REQUIRED")
