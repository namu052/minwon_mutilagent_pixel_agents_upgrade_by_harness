# 구현 결과

- 구현: Claude Code (`docs/CODEX_CLAUDE_HANDOFF.md` 형식)
- 기준 계획: `plan/CODEX_PLAN.md` (계획 문서상 경로는 `_workspace/CODEX_PLAN.md`였으나 실제 파일은 `plan/`에 위치 — 내용 그대로 사용)
- 작성일: 2026-07-11

## 구현 요약

4개 Agent 고정 순차 파이프라인을 Supervisor가 조율하는 12개 전문 업무 Agent DAG로 확장했다. 하네스의 입력 → 처리 → 독립 검증 → 출력 흐름, 최대 2회 수정 루프, 허용 상태 전이 맵, `_workspace/traces/{trace_id}/` 파일 handoff, PASS 없는 승인 금지 불변 조건을 코드·산출물·trace·화면에 일치시켰다. Pixel Office는 CSS 반복 애니메이션에서 9개 공간·12개 Agent의 HTML Canvas 상태 애니메이션으로 교체했다.

## 계획 대비 변경 사항

| # | 계획 | 실제 구현 | 이유와 영향 |
|---:|---|---|---|
| 1 | Agent 구현 방식 미지정 (LLM 여부) | `intake`, `evidence-search`, `response-validator`, `output-publisher` 4개는 LLM 없이 결정적 규칙으로 구현 | 안전 불변 조건(PASS 금지 규칙, URL 검증, PII 판정)을 LLM 비결정성과 분리해 테스트로 강제 가능. 비용·지연도 감소. UI에는 "결정적 규칙"으로 표시 |
| 2 | 병렬 셀 이벤트 발행 시점 미지정 | 시작 이벤트는 제출 전 고정 순서, 완료·handoff 이벤트는 두 작업 완료 후 고정 순서로 발행 | seq를 결정적으로 만들기 위함(계획의 "event seq 중앙 발급" 완화책 구체화). 실제 LLM 호출은 병렬 실행됨 |
| 3 | REVISION_REQUIRED 상태에서 writer 실패 시 전이 경로 없음 (상태 맵상 DRAFT_READY로만 전이 가능) | `finish()`가 미정의 전이를 강제하지 않고 note 기록 후 HUMAN_REVIEW_REQUIRED 제한 출력으로 안전 종료 | 계획 작업 7의 "정의되지 않은 상태 전이를 안전하게 사람 검토로 종료" 요구 준수. manifest `notes`에 기록됨 |
| 4 | `assets/pixel_office/` 신규 스프라이트 추가 가능 | 기존 asset만 재사용, 신규 asset 없음 | Canvas가 기존 캐릭터 시트·가구 PNG + 도형 fallback으로 충분. 계획상 "필요 시" 항목 |
| 5 | 검증 명령의 `pytest` | 저장소에 pytest가 없어 `.venv`를 생성해 `requirements.txt + pytest` 설치 | `requirements.txt`는 변경하지 않음(신규 런타임 의존성 없음). pytest는 개발 도구로만 사용 |
| 6 | validator가 LLM 호출 주체인지 미지정 | validator는 두 감사 결과의 결정적 취합·판정만 수행. LLM 감사는 auditor 2종이 담당 | 계획 42행 "Supervisor는 내용 판정을 하지 않음" 및 "검증 불능을 PASS로 처리하지 않는다"를 규칙으로 강제하기 위함 |
| 7 | validator PASS 판정 세부 기준 미지정 | 초기 구현은 MEDIUM finding에도 REVISE였으나, 실 API 검증에서 PASS 도달 불가 확인 후 계약 기준(BLOCKER 전부 + 근거·관할·개인정보 HIGH만 PASS 금지)으로 정합화. MEDIUM/LOW는 권고로 보고서에 보존 | 실 LLM 감사는 항상 소수의 MEDIUM 권고를 남기므로 계약보다 엄격한 기준은 승인 경로를 실질 차단. BLOCKER/HIGH/check FAIL의 REVISE·ESCALATE는 유지 |

## 변경 파일과 핵심 심볼

- `complaint_agents.py` (전면 재작성, 파이프라인 엔지니어 소유)
  - 계약: `validate_complaint_input`~`validate_final_output`, `ContractViolation`, `_has_pass_blockers`
  - 상태: `ALLOWED_TRANSITIONS`, `PipelineStateMachine`, `InvalidStateTransition`
  - LLM 헬퍼: `call_agent_json` (비JSON/스키마 불일치 1회 재요청 → `AgentEscalation`)
  - 12개 Agent: `run_intake_agent`, `run_issue_analysis_agent`, `run_jurisdiction_analysis_agent`, `run_classifier_agent`, `run_legal_research_agent`, `run_similar_case_agent`, `run_evidence_search_agent`, `run_response_writer_agent`, `run_claim_citation_auditor`, `run_privacy_tone_auditor`, `run_response_validator_agent`, `run_output_publisher_agent`
  - Runtime: `PixelAgentState`(계획 공개 인터페이스 필드), `PixelAgentStateStore`(공통 envelope, 중앙 seq, 스레드 안전), `AGENT_SPECS`, `ZONES`
  - Trace: `TraceWriter`(원자적 JSON, manifest, events), `STANDARD_ARTIFACTS`
  - Supervisor: `ComplaintSupervisor.run()`(DAG, `_run_parallel_cell` barrier, 1회 재시도, 최대 2회 revision, 조기 종료), `SUPERVISOR_TOOLS`(requires/provides)
- `app.py` (전면 재작성, UI 엔지니어 소유)
  - `render_pixel_office`(HTML Canvas, `ZONE_LAYOUT`, reduced-motion, asset fallback, `_json_for_html` escape)
  - `run_pipeline`(Supervisor `run` 호출로 변경), `render_results`(판정/검증 보고서/수정 이력/산출물/상태·handoff/Supervisor 탭), `build_download_payload`(FinalOutput + 비민감 trace만)
  - 역할군 모델 + 고급 Agent override, `RESULT_SCHEMA_VERSION` 기반 구세션 폐기
- `tests/` (신규): `conftest.py`(FakeClient·주입식 검색/검증), `test_contracts.py`, `test_intake_and_agents.py`, `test_pipeline.py`, `test_pixel_runtime.py`, `test_app_smoke.py` — 총 85건
- `README.md`: 12-Agent 구조, DAG, 안전 경계, trace, 구/신 다운로드 필드 대응표, 검증 방법
- 비변경: `minwon_multiagent/`(계획 비대상), `requirements.txt`, 샘플 Excel, OpenRouter 키 입력 방식

## 데이터 계약 및 상태 전이

- `.harness/references/data-contracts.md`의 1~7 계약을 validator 함수로 구현. 각 표준 산출물은 생산자 Agent가 검증 후 `_workspace/traces/{trace_id}/01~06_*.json`에 원자 기록.
- 전문 셀 중간 결과는 `intermediate/`에 저장하고 취합 Agent(classifier/evidence-search/validator)를 거친 뒤에만 표준 단계로 전달.
- 상태 전이는 `business-workflow.md` 맵과 동일하며 미정의 전이는 `InvalidStateTransition`. `revision_count == 2` 후 REVISE는 `HUMAN_REVIEW_REQUIRED`로 전환(PASS 승격 금지).
- 최종 불변 조건: `FinalOutput.status == DRAFT_APPROVED` ⇔ `ValidationReport.decision == PASS` ∧ 상태 APPROVED — 계약(`validate_final_output`)과 publisher 강등 로직 이중 강제.

## 실행한 테스트와 결과

| 검증 | 결과 |
|---|---|
| `bash scripts/validate_harness.sh` | PASS |
| `python -m compileall app.py complaint_agents.py tests` | PASS |
| `pytest -q` (85 tests) | PASS |
| `rg -n 'sk-or-\|Authorization: Bearer\|api[_-]?key\s*=' .` | PASS (실제 비밀값 없음, 상세는 `04_integration-qa_report.md`) |
| `streamlit run app.py` headless 기동 + AppTest smoke 5건 | PASS |

세부 시나리오 매핑은 `_workspace/04_integration-qa_report.md` 참조.

## 실행하지 못한 테스트

- 실 OpenRouter API 호출 검증 (테스트는 전부 mock): 앱 실행 후 실제 키로 수동 확인 필요.
- 브라우저 수동 UI 시나리오 7건 (NOT RUN, 재현 절차는 QA 보고서에 기록): 표준 성공, 수정 후 성공, 2회 수정 실패, 검색 재실패, 입력 거절, 재실행 격리, 반응형/reduced-motion.
- 실 네트워크 대상 `duckduckgo_search`/`verify_url` 동작 (mock 주입으로 대체).

## 안전성 검토 결과

`_workspace/03_civic-safety-review.md` — 종합 PASS(조건부). 잔여 위험: 비정형 PII 탐지의 LLM 의존, prompt injection 원천 차단 불가(완화: URL 화이트리스트, 결정적 감사, PASS 금지 규칙, 사람 검토 전환).

## 남은 작업과 알려진 위험

- 수동 UI 시나리오 7건의 브라우저 검증 (실 API 키 필요).
- Canvas의 handoff 종이 애니메이션은 최근 6건 이벤트만 재생 — 매우 긴 실행에서는 과거 handoff가 이벤트 패널로만 확인됨.
- Streamlit 실행 중 갱신은 각 단계 callback 시점의 snapshot 재렌더 방식 — 프레임 보간은 Canvas 내부에서만 수행되므로 초장시간 LLM 호출 중에는 화면 변화가 없음.
- `verify_url`은 HEAD 요청 기반이라 봇 차단 사이트에서 false negative(과잉 ESCALATE) 가능 — 안전 방향의 오류로 수용.
