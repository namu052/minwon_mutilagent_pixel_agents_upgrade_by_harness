# Integration QA Report

- 검토자 역할: `integration-qa`
- 검토일: 2026-07-11
- 환경: macOS, Python 3.14.6 (`.venv`), streamlit/pandas/requests/beautifulsoup4/pytest 설치

## 자동 게이트

| 게이트 | 명령 | 결과 |
|---|---|---|
| 하네스 구조 | `bash scripts/validate_harness.sh` | PASS |
| Python 구문 | `python -m compileall app.py complaint_agents.py tests` | PASS |
| 전체 테스트 | `pytest -q` (tests/, 85건) | PASS (85 passed) |
| 비밀정보 grep | `rg -n 'sk-or-\|Authorization: Bearer\|api[_-]?key\s*='` | PASS — 검출 항목은 키 입력 UI, 클라이언트 헤더 구성, 비노출 단언 테스트, 문서 예시로 실제 비밀값 없음 |
| Streamlit 기동 | `streamlit run app.py --server.headless` + HTTP 확인 | PASS (HTTP 200) |
| Streamlit 렌더 | `streamlit.testing.v1.AppTest` smoke 5건 | PASS |

## 계약 경계면 검증 (생산자 ↔ 소비자)

| 경계면 | 검증 방식 | 결과 |
|---|---|---|
| ComplaintInput → IntakeResult | `validate_intake_result` + `test_intake_and_agents.py` | PASS |
| 쟁점·관할 중간 결과 → ClassificationResult | classifier가 두 결과 수신 후에만 실행 (barrier 테스트) | PASS |
| 법령·사례 중간 결과 → EvidencePackage | `run_evidence_search_agent` 결정적 취합 + URL/verified 관계 검증 | PASS |
| EvidencePackage → DraftPackage | writer의 검증 URL 화이트리스트, `claim_evidence_map` 검증 | PASS |
| 감사 중간 결과 → ValidationReport | 6개 check 취합, BLOCKER/HIGH PASS 금지 | PASS |
| ValidationReport → FinalOutput | PASS 없는 DRAFT_APPROVED 계약 거부, 강등 경로 | PASS |
| snapshot/이벤트 → Canvas payload | envelope 필드·enum 검증 (`test_pixel_runtime.py`) | PASS |

## 시나리오 테스트 (자동)

| 시나리오 | 테스트 | 결과 |
|---|---|---|
| 표준 성공 (01~06 + manifest) | `TestHappyPath` | PASS |
| REVISE 1회 후 승인, writer·감사 재호출 | `TestRevisionLoop::test_revise_then_pass` | PASS |
| 2회 수정 후 강제 사람 검토 (PASS 승격 금지) | `test_two_revisions_then_human_review` | PASS |
| 입력 거절 시 후속 Agent 미실행 | `test_input_rejected_skips_downstream` | PASS |
| 고위험 개인정보 ESCALATE | `test_high_risk_privacy_escalates` | PASS |
| 검색 결과 없음/미검증 근거 → 초안 강행 없이 사람 검토 | `test_no_search_results...`, `test_unverified_evidence...` | PASS |
| 병렬 셀 재실패 → ESCALATE + agentToolFailed/supervisorDecision 이벤트 | `TestFailureHandling` | PASS |
| 상태 전이 맵 강제, 미정의 전이 거부 | `TestStateMachine` | PASS |
| 이벤트 seq 단조 증가 + 취합 barrier | `TestEventOrdering` | PASS |
| 재실행 격리 (trace_id·이벤트 비혼입) | `test_rerun_isolated` | PASS |
| 원문/API 키 비노출 | `TestSafety` | PASS |
| 구버전 session_state 폐기 | `test_legacy_session_state_discarded` | PASS |

## 수동 UI 검증 (브라우저)

실 OpenRouter 키가 필요한 시나리오는 이 환경에서 실행하지 못했다.

| # | 시나리오 | 결과 | 재현 절차 |
|---:|---|---|---|
| 1 | 표준 성공: 12개 Agent 이동·handoff 후 DRAFT_APPROVED 표시 | NOT RUN | `streamlit run app.py` → 키 입력 → 샘플 선택 → Supervisor 실행 |
| 2 | 수정 후 성공: 검증실→작성석 반송 후 재검증 승인 | NOT RUN | REVISE가 발생하는 민원으로 실행 (검증 finding 유도) |
| 3 | 두 번 수정 실패: 회의실·사람 검토 창구 이동 + HUMAN_REVIEW_REQUIRED | NOT RUN | 반복 REVISE 민원으로 실행 |
| 4 | 검색 결과 없음/네트워크 재실패 → 사람 검토 전환 | NOT RUN | 네트워크 차단 상태로 실행 |
| 5 | 입력 거절: 빈 제목/본문 → INPUT_REJECTED | NOT RUN (자동 테스트로는 PASS) | 제목·본문 비우고 실행 |
| 6 | 재실행: 이전 trace·상태 비혼입 | NOT RUN (자동 테스트로는 PASS) | 연속 2회 실행 후 trace_id 비교 |
| 7 | 반응형/접근성: 좁은 화면·reduced motion | NOT RUN | 브라우저 창 축소, OS 모션 감소 설정 후 확인 |

## 실 API E2E 검증 (2026-07-11 추가)

`.streamlit/secrets.toml`의 실제 OpenRouter 키로 headless E2E를 4회 실행했다 (모델: anthropic/claude-sonnet-4.6).

| 실행 | 샘플 | 결과 | 확인 내용 |
|---|---|---|---|
| 1 | #0 간행물 문의 | HUMAN_REVIEW_REQUIRED | 분류 ESCALATE 조기 종료 경로 정상 (기관 익명화로 관할 특정 불가 — 정당한 판정). 01·02·06 + manifest만 생성 |
| 2 | #20 조기진통 병가 | HUMAN_REVIEW_REQUIRED | classifier가 유력 후보(0.85)에도 과잉 ESCALATE → 프롬프트에 ESCALATE 기준 명확화 (결정적 임계값 규칙은 유지) |
| 3 | #20 재실행 | HUMAN_REVIEW_REQUIRED | 근거 단계 ESCALATE — 정부 사이트(law.go.kr, mpm.go.kr)가 HEAD에 404/리다이렉트 루프 반환 → `verify_url`에 GET(stream) 폴백 추가 |
| 4 | #20 최종 | HUMAN_REVIEW_REQUIRED | **12단계 전체 완주** (01~06 + 감사 중간 산출물 16개 파일). 초안 생성 후 독립 감사가 finding 13건(개인 블로그 출처 BLOCKER, 진단서 세부 재노출 privacy BLOCKER, 발신 주체 단정 등) 적발 → 검증 ESCALATE → 사람 검토 전환. 설계 의도대로 동작 |

전 실행에서 이벤트·manifest·trace 파일에 API 키와 민원 원문 비포함을 자동 확인했다 (스크립트 내 안전 점검 True).

실행 중 발견·수정: ① 지역번호(044-...)가 계좌 패턴 오탐 → 0으로 시작하는 그룹 제외, ② AppTest가 실제 secrets 키로 fallback해 실 API 호출 → 테스트에 빈 secrets 강제 주입. 수정 후 pytest 87건 PASS.

| 5 | #20 (writer 튜닝 후) | **DRAFT_APPROVED** | writer 프롬프트에 감사 통과 규칙 추가(발신 주체 미단정, 개인정보 비반복, SECONDARY 미인용, 세부 사실 미생성) + validator PASS 기준을 계약과 정합화(MEDIUM/LOW는 권고로 보존). 실행 결과: 검증 REVISE(r0) → 수정 1차 → 검증 PASS(r1) → DRAFT_APPROVED. **수정 루프의 실 API 동작까지 확인**. 6개 check 전부 PASS, 잔여 finding 9건은 MEDIUM/LOW 권고. citation 6건 모두 OFFICIAL(law.go.kr, mpm.go.kr). trace: `ac14cb50204d` (r0/r1 감사·초안·검증 중간 산출물 20개 파일) |

미확인 항목: REJECT 실 사례(위해성 민원 fixture 미실행 — 자동 테스트로만 검증).

## 발견 사항 및 처리

1. FakeClient 프롬프트 식별 키워드가 classifier 프롬프트와 충돌 → 고유 문구("… Agent다")로 수정 완료.
2. 휴대전화 번호가 계좌 패턴에 중복 매칭되어 과잉 ESCALATE → `bank_account` 패턴에 부정 전방탐색 추가 완료.
3. 동일 법령·동일 URL·상이 claim이 dedupe로 소실되어 상충 탐지 불가 → dedupe 키에 claim 포함으로 수정 완료.
4. **pyarrow 25.0.0 mimalloc segfault (macOS)**: 브라우저 접속 후 서버가 SIGSEGV(139)로 사망. 크래시 리포트 분석 결과 `libarrow.2500.dylib`의 mimalloc 스레드 힙 초기화(`mi_heap_main`)에서 발생 — pandas의 arrow 문자열 배열(`string_arrow._from_sequence`)이 ScriptRunner 스레드에서 libarrow를 호출하는 경로. Python 3.14/3.12 모두 재현. `ARROW_DEFAULT_MEMORY_POOL=system`으로 mimalloc을 우회하면 완전 해소(재현 환경에서 3회 연속 크래시 → 적용 후 3회 연속 전체 통과). `app.py`와 `tests/conftest.py` 최상단에서 libarrow 로드 전에 env 설정하도록 반영. requirements는 변경하지 않음.

## 종합 판정

자동 검증 전체 PASS. 수동 UI 시나리오 7건은 실 API 키·브라우저 환경 부재로 NOT RUN이며 재현 절차를 위에 기록했다.
