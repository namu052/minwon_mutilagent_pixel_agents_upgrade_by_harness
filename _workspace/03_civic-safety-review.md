# Civic Safety Review (독립 검토)

- 검토자 역할: `civic-safety-reviewer`
- 검토 대상: `complaint_agents.py`, `app.py`, `tests/`, trace 산출물 구조
- 검토일: 2026-07-11

## 1. 법령 정확성 / 근거 조작 방지

| 항목 | 판정 | 근거 |
|---|---|---|
| 검색 결과에 없는 조문 생성 차단 | PASS | `run_evidence_search_agent`가 검색 sources에 없는 URL을 `verified: false`로 강등 (`tests/test_intake_and_agents.py::test_hallucinated_url_not_verified`) |
| 미검증 근거의 핵심 주장 승격 차단 | PASS | writer가 검증 URL 외 매핑 제거 + `claim-citation-auditor` 결정적 BLOCKER (`test_unverified_urls_removed_from_claim_map`) |
| 근거 없는 초안 강행 차단 | PASS | 검증 근거 0건이면 writer 호출 전 ESCALATE (`test_no_search_results_escalates_without_draft`) |
| 상충 근거 보존 | PASS | 같은 법령·다른 claim을 `conflicts`에 기록 (`test_conflicting_claims_recorded`) |

## 2. 관할 단정

- classifier는 관할분석 confidence가 낮거나 불확실성이 있으면 강제 ESCALATE (`LOW_CONFIDENCE_THRESHOLD = 0.45`, `test_low_confidence_forced_escalate`) — PASS
- `privacy-tone-auditor`의 jurisdiction check FAIL 시 계약 수준에서 PASS 금지 (`_has_pass_blockers`) — PASS

## 3. 개인정보

| 항목 | 판정 | 근거 |
|---|---|---|
| 고위험 개인정보(주민번호·계좌) 입력 시 사람 검토 전환 | PASS | `run_intake_agent` ESCALATE (`test_rrn_escalates`, `test_high_risk_privacy_escalates`) |
| 이벤트/safe_summary 마스킹 | PASS | `make_safe_summary`가 PII 패턴 마스킹 (`test_privacy_masked_in_safe_summary`) |
| 초안 내 PII 재노출 탐지 | PASS | `run_privacy_tone_auditor` 결정적 regex 검사 → HIGH privacy finding → PASS 금지 |
| 민원 원문의 trace 복제 제한 | PASS | 원문은 `01_intake_result.json`에만 존재 (`test_body_only_in_intake_artifact`) |
| API 키 비기록 | PASS | 이벤트·trace 파일 grep 테스트 (`test_events_do_not_leak_raw_body_or_key`, `test_trace_files_do_not_contain_api_key`) |

주의: PII regex는 주민번호/휴대전화/이메일/계좌 4종 패턴 기반이다. 주소·이름 등 비정형 개인정보는 LLM 감사(privacy-tone-auditor)에 의존하므로 완전 탐지를 보장하지 않는다 → 잔여 위험으로 기록.

## 4. Prompt Injection

- 검색 결과는 프롬프트에서 "신뢰할 수 없는 외부 데이터" 경계(`UNTRUSTED_CONTENT_NOTICE`)로 감싸 지시문 추종을 금지 — PASS (구조 검토)
- 웹 본문은 `fetch_page_excerpt`로 1,600자 제한 발췌만 사용, 이벤트·trace에 미기록 — PASS
- 잔여 위험: LLM이 경계 문구를 무시할 가능성은 원천 차단 불가. 완화책으로 writer는 검증 URL 화이트리스트로 제한되고, 감사 Agent의 결정적 검사가 LLM과 독립적으로 동작한다.

## 5. 출력 안전

- `validate_final_output`이 PASS 없는 `DRAFT_APPROVED`를 계약 수준에서 거부 — PASS
- publisher는 승인 없는 요청을 받으면 `HUMAN_REVIEW_REQUIRED`로 강등 (`test_approved_without_pass_downgrades`) — PASS
- 비승인 상태에서 `answer: null` 강제, 초안 비노출 — PASS
- 모든 출력에 disclaimer("담당자 검토 전 초안입니다.") + trace_id 포함 — PASS

## 종합 판정

**PASS (조건부)** — 잔여 위험 2건(비정형 PII의 LLM 의존 탐지, prompt injection의 원천 차단 불가)은 결정적 방어선(URL 화이트리스트, PASS 금지 규칙, 사람 검토 전환)으로 완화되어 있으며 실제 발송이 없는 "담당자 검토 전 초안" 범위에서 수용 가능하다.
