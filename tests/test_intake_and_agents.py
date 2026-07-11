from __future__ import annotations

import pytest

import complaint_agents as ca

from conftest import LAW_URL, FakeClient


def make_input(**over):
    data = {"complaint_id": "C-1", "title": "제목", "body": "본문 내용입니다. 문의 드립니다.", "submitted_at": None}
    data.update(over)
    return data


class TestIntakeAgent:
    def test_continue(self):
        result = ca.run_intake_agent(make_input())
        assert result["decision"] == "CONTINUE"
        assert result["quality_flags"] == []

    def test_empty_title_rejected(self):
        result = ca.run_intake_agent(make_input(title="  "))
        assert result["decision"] == "REJECT"
        assert "missing_title" in result["quality_flags"]

    def test_empty_body_rejected(self):
        result = ca.run_intake_agent(make_input(body=""))
        assert result["decision"] == "REJECT"

    def test_html_entity_normalized_without_meaning_change(self):
        result = ca.run_intake_agent(make_input(title="&lt;민원&gt; 처리 문의"))
        assert result["complaint"]["title"] == "<민원> 처리 문의"

    def test_rrn_escalates(self):
        result = ca.run_intake_agent(make_input(body="제 주민번호는 900101-1234567 입니다. 확인 부탁드립니다."))
        assert result["decision"] == "ESCALATE"
        assert "resident_registration_number" in result["privacy_flags"]

    def test_phone_flagged_but_continues(self):
        result = ca.run_intake_agent(make_input(body="연락처는 010-1234-5678 입니다. 회신 부탁드립니다."))
        assert result["decision"] == "CONTINUE"
        assert "phone_number" in result["privacy_flags"]

    def test_landline_not_flagged_as_bank_account(self):
        result = ca.run_intake_agent(
            make_input(body="자세한 내용은 인사혁신처 복무제도과 044-201-8445 로 문의하십시오.")
        )
        assert result["decision"] == "CONTINUE"
        assert "bank_account" not in result["privacy_flags"]

    def test_bank_account_still_detected(self):
        result = ca.run_intake_agent(make_input(body="환불 계좌는 352-1234-5678-93 입니다. 처리 부탁드립니다."))
        assert result["decision"] == "ESCALATE"
        assert "bank_account" in result["privacy_flags"]

    def test_privacy_masked_in_safe_summary(self):
        result = ca.run_intake_agent(make_input(title="010-1234-5678 로 연락주세요"))
        assert "010-1234-5678" not in result["safe_summary"]

    def test_abnormal_length_truncated(self):
        result = ca.run_intake_agent(make_input(body="가" * (ca.MAX_BODY_CHARS + 500)))
        assert "body_truncated" in result["quality_flags"]
        assert len(result["complaint"]["body"]) == ca.MAX_BODY_CHARS


class TestEvidenceSearchAgent:
    def legal(self, url=LAW_URL):
        return {
            "legal_bases": [
                {"title": "민원처리법", "article": "제17조", "claim": "기한 준수", "url": url}
            ],
            "limitations": [],
            "sources": [{"url": url}],
        }

    def cases(self):
        return {"similar_cases": [], "limitations": [], "sources": []}

    def test_verified_official_source(self):
        package = ca.run_evidence_search_agent(
            legal_research=self.legal(), similar_case=self.cases(), verify_fn=lambda u: True
        )
        item = package["legal_bases"][0]
        assert item["verified"] is True
        assert item["source_type"] == "OFFICIAL"
        assert package["decision"] == "CONTINUE"

    def test_hallucinated_url_not_verified(self):
        legal = self.legal()
        legal["legal_bases"][0]["url"] = "https://www.law.go.kr/not-in-sources"
        package = ca.run_evidence_search_agent(
            legal_research=legal, similar_case=self.cases(), verify_fn=lambda u: True
        )
        assert package["legal_bases"][0]["verified"] is False
        assert package["decision"] == "ESCALATE"

    def test_unreachable_url_escalates(self):
        package = ca.run_evidence_search_agent(
            legal_research=self.legal(), similar_case=self.cases(), verify_fn=lambda u: False
        )
        assert package["decision"] == "ESCALATE"
        assert any("검증된 핵심" in gap for gap in package["coverage_gaps"])

    def test_duplicate_urls_deduped(self):
        legal = self.legal()
        legal["legal_bases"].append(dict(legal["legal_bases"][0]))
        package = ca.run_evidence_search_agent(
            legal_research=legal, similar_case=self.cases(), verify_fn=lambda u: True
        )
        assert len(package["legal_bases"]) == 1

    def test_conflicting_claims_recorded(self):
        legal = self.legal()
        second = dict(legal["legal_bases"][0])
        second["claim"] = "기한 규정이 없다"
        legal["legal_bases"].append(second)
        legal["legal_bases"][1]["url"] = LAW_URL
        package = ca.run_evidence_search_agent(
            legal_research=legal, similar_case=self.cases(), verify_fn=lambda u: True
        )
        assert package["conflicts"]


class TestWriterGuards:
    def evidence(self, verified=True):
        return {
            "legal_bases": [
                {
                    "title": "민원처리법",
                    "article": "제17조",
                    "claim": "기한 준수",
                    "url": LAW_URL,
                    "source_type": "OFFICIAL",
                    "verified": verified,
                }
            ],
            "similar_cases": [],
            "conflicts": [],
            "coverage_gaps": [],
            "decision": "CONTINUE",
        }

    def intake(self):
        return ca.run_intake_agent(make_input())

    def classification(self):
        return {
            "department": "행정안전부",
            "complaint_type": "기타",
            "confidence": 0.8,
            "rationale": "r",
            "issues": ["기한"],
            "search_terms": ["기한"],
            "decision": "CONTINUE",
        }

    def test_no_verified_evidence_escalates(self):
        with pytest.raises(ca.AgentEscalation):
            ca.run_response_writer_agent(
                FakeClient(),
                intake_result=self.intake(),
                classification_result=self.classification(),
                evidence_package=self.evidence(verified=False),
                model="m",
            )

    def test_unverified_urls_removed_from_claim_map(self):
        client = FakeClient(
            {
                "writer": [
                    {
                        "draft": "안녕하십니까. 답변드립니다. 감사합니다.",
                        "claim_evidence_map": [
                            {"claim": "근거 있는 주장", "evidence_urls": [LAW_URL]},
                            {"claim": "지어낸 주장", "evidence_urls": ["https://fake.example.com/x"]},
                        ],
                        "uncertainties": [],
                    }
                ]
            }
        )
        package = ca.run_response_writer_agent(
            client,
            intake_result=self.intake(),
            classification_result=self.classification(),
            evidence_package=self.evidence(),
            model="m",
        )
        claims = {item["claim"]: item["evidence_urls"] for item in package["claim_evidence_map"]}
        assert claims["근거 있는 주장"] == [LAW_URL]
        assert claims["지어낸 주장"] == []
        assert any("지어낸 주장" in u for u in package["uncertainties"])

    def test_revision_count_increments(self):
        previous = {
            "draft": "이전 초안",
            "claim_evidence_map": [{"claim": "c", "evidence_urls": [LAW_URL]}],
            "uncertainties": [],
            "revision_count": 0,
        }
        report = {"revision_instructions": ["문구를 완화하라"]}
        package = ca.run_response_writer_agent(
            FakeClient(),
            intake_result=self.intake(),
            classification_result=self.classification(),
            evidence_package=self.evidence(),
            model="m",
            previous_draft=previous,
            validation_report=report,
        )
        assert package["revision_count"] == 1

    def test_revision_limit_enforced(self):
        previous = {
            "draft": "이전 초안",
            "claim_evidence_map": [],
            "uncertainties": [],
            "revision_count": ca.MAX_REVISIONS,
        }
        with pytest.raises(ca.AgentEscalation):
            ca.run_response_writer_agent(
                FakeClient(),
                intake_result=self.intake(),
                classification_result=self.classification(),
                evidence_package=self.evidence(),
                model="m",
                previous_draft=previous,
                validation_report={"revision_instructions": []},
            )


class TestValidatorRules:
    def audit(self, findings=None, checks=None, keys=("evidence", "citation")):
        return {
            "checks": {**{k: "PASS" for k in keys}, **(checks or {})},
            "findings": findings or [],
        }

    def privacy_audit(self, findings=None, checks=None):
        return self.audit(findings, checks, keys=("input_fidelity", "jurisdiction", "tone", "privacy"))

    def draft(self):
        return {"draft": "d", "claim_evidence_map": [], "uncertainties": [], "revision_count": 0}

    def test_clean_audits_pass(self):
        report = ca.run_response_validator_agent(
            citation_audit=self.audit(),
            privacy_audit=self.privacy_audit(),
            draft_package=self.draft(),
        )
        assert report["decision"] == "PASS"

    def test_blocker_forces_revise(self):
        report = ca.run_response_validator_agent(
            citation_audit=self.audit(
                findings=[{"severity": "BLOCKER", "category": "evidence", "message": "m", "fix": "f"}],
                checks={"evidence": "FAIL"},
            ),
            privacy_audit=self.privacy_audit(),
            draft_package=self.draft(),
        )
        assert report["decision"] == "REVISE"
        assert report["revision_instructions"] == ["f"]

    def test_privacy_blocker_escalates(self):
        report = ca.run_response_validator_agent(
            citation_audit=self.audit(),
            privacy_audit=self.privacy_audit(
                findings=[{"severity": "BLOCKER", "category": "privacy", "message": "m", "fix": "f"}],
                checks={"privacy": "FAIL"},
            ),
            draft_package=self.draft(),
        )
        assert report["decision"] == "ESCALATE"

    def test_harm_rejects(self):
        report = ca.run_response_validator_agent(
            citation_audit=self.audit(),
            privacy_audit=self.privacy_audit(
                findings=[{"severity": "HIGH", "category": "harm", "message": "m", "fix": "f"}],
            ),
            draft_package=self.draft(),
        )
        assert report["decision"] == "REJECT"

    def test_check_fail_blocks_pass(self):
        report = ca.run_response_validator_agent(
            citation_audit=self.audit(checks={"citation": "FAIL"}),
            privacy_audit=self.privacy_audit(),
            draft_package=self.draft(),
        )
        assert report["decision"] != "PASS"


class TestPublisherRules:
    def test_approved_without_pass_downgrades(self):
        output = ca.run_output_publisher_agent(
            final_state="APPROVED",
            trace_id="t",
            draft_package={"draft": "d", "claim_evidence_map": [], "uncertainties": [], "revision_count": 0},
            validation_report={
                "decision": "REVISE",
                "checks": {k: "PASS" for k in ca.CHECK_KEYS},
                "findings": [],
                "revision_instructions": [],
                "validated_at": "now",
            },
        )
        assert output["status"] == "HUMAN_REVIEW_REQUIRED"
        assert output["answer"] is None

    def test_rejected_hides_answer(self):
        output = ca.run_output_publisher_agent(final_state="REJECTED", trace_id="t")
        assert output["answer"] is None
        assert output["citations"] == []

    def test_input_rejected_includes_quality_reasons(self):
        output = ca.run_output_publisher_agent(
            final_state="INPUT_REJECTED",
            trace_id="t",
            intake_result={"quality_flags": ["missing_title"], "privacy_flags": [], "safe_summary": "s"},
        )
        assert output["status"] == "INPUT_REJECTED"

    def test_all_outputs_have_required_fields(self):
        for state in ("HUMAN_REVIEW_REQUIRED", "REJECTED", "INPUT_REJECTED"):
            output = ca.run_output_publisher_agent(final_state=state, trace_id="t")
            assert output["disclaimer"] == ca.DISCLAIMER
            assert output["trace_id"] == "t"
            assert isinstance(output["validation_report"], dict)


class TestSchemaRetry:
    def test_non_json_then_valid_recovers(self):
        client = FakeClient({"issue": ["이건 JSON이 아님"]})
        result = ca.run_issue_analysis_agent(
            client, intake_result=ca.run_intake_agent(make_input()), model="m"
        )
        assert result["issues"]
        assert client.calls.count("issue") == 2

    def test_repeated_schema_failure_escalates(self):
        client = FakeClient({"issue": ["비JSON 1", "비JSON 2"]})
        with pytest.raises(ca.AgentEscalation):
            ca.run_issue_analysis_agent(
                client, intake_result=ca.run_intake_agent(make_input()), model="m"
            )
