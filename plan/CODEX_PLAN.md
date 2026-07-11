# 민원 멀티에이전트 픽셀 오피스 고도화 계획

## 목표와 사용자 가치

- 현재 4개 Agent 파이프라인을 Supervisor가 조율하는 12개 전문 업무 Agent 구조로 확장한다.
- 하네스의 입력 → 처리 → 독립 검증 → 출력 흐름과 최대 2회 수정 루프를 실제 코드, 산출물, trace, 화면에 일치시킨다.
- 픽셀 오피스를 실제 사무실처럼 접수, 분류, 조사, 작성, 검증, 결재가 일어나는 동적 공간으로 표현한다.
- 최종 답변의 근거 추적성, 개인정보 안전성, 관할 불확실성 처리와 사람 검토 전환을 강화한다.

## 현재 구조와 Gap

현재 과제 제출용 메인 구현은 루트 `app.py`와 `complaint_agents.py`다. `minwon_multiagent/`는 패키지형 참고 구현이다.

- `ComplaintSupervisor`가 분류, 검색, 작성, 검수 4개 도구를 고정 순서로 호출한다.
- 하네스 필수 역할인 `intake-agent`와 `output-publisher-agent`가 없다.
- 기존 결과 shape가 `IntakeResult`~`FinalOutput` 표준 계약과 다르다.
- 검수 결과에 PASS/REVISE/ESCALATE/REJECT 강제 규칙이 없고, 작성↔검증 최대 2회 수정 루프도 없다.
- 허용 상태 전이 맵, `trace_id`, 단계별 파일 handoff, 사람 검토용 제한 출력이 없다.
- 검색 결과와 핵심 주장 간 검증된 URL 매핑 및 독립 검증이 충분하지 않다.
- Pixel Runtime은 4개 고정 좌석과 단순 CSS 반복 애니메이션 중심이며 실제 이동, 병렬 작업, 회의, 재작업을 표현하지 못한다.
- 자동 테스트가 없어 스키마, 상태 전이, 오류, 안전성, UI 회귀를 보장하지 못한다.

## 목표 업무 흐름

### Agent 구성

| 번호 | Agent | 책임 | 표준 계약상 위치 |
|---:|---|---|---|
| 1 | `intake-agent` | 입력 정규화, 필수값, 품질 및 개인정보 위험 판정 | `IntakeResult` 생산자 |
| 2 | `issue-analysis-agent` | 요구사항, 사실관계, 핵심 쟁점 추출 | 분류 전문 셀 |
| 3 | `jurisdiction-analysis-agent` | 관할 기관·부서 후보와 불확실성 분석 | 분류 전문 셀 |
| 4 | `classifier-agent` | 두 전문 분석을 취합해 최종 분류 확정 | `ClassificationResult` 생산자 |
| 5 | `legal-research-agent` | 공식 법령 및 담당 기관 자료 검색 | 근거 전문 셀 |
| 6 | `similar-case-agent` | 공식 유사 사례 및 과거 답변 검색 | 근거 전문 셀 |
| 7 | `evidence-search-agent` | 출처 검증, 중복 제거, 상충 및 coverage gap 취합 | `EvidencePackage` 생산자 |
| 8 | `response-writer-agent` | 검증된 근거만 사용해 최초·수정 초안 작성 | `DraftPackage` 생산자 |
| 9 | `claim-citation-auditor` | 핵심 주장과 법령·URL·인용의 대응 검증 | 검증 전문 셀 |
| 10 | `privacy-tone-auditor` | 개인정보, 입력 충실성, 관할 표현, 공문 문체 검증 | 검증 전문 셀 |
| 11 | `response-validator-agent` | 독립 감사 결과를 취합해 최종 판정 | `ValidationReport` 생산자 |
| 12 | `output-publisher-agent` | 판정에 맞는 승인 초안 또는 제한 결과 생성 | `FinalOutput` 생산자 |

Supervisor는 업무 Agent 수에 포함하지 않으며 도구 등록, 의존성, 상태 전이, 재시도, 수정 횟수, trace와 파일 handoff만 관리한다. 내용 판정이나 PASS 승격을 직접 수행하지 않는다.

### 실행 DAG

```text
intake-agent
  → issue-analysis-agent + jurisdiction-analysis-agent (병렬)
  → classifier-agent (취합)
  → legal-research-agent + similar-case-agent (병렬)
  → evidence-search-agent (취합)
  → response-writer-agent
  → claim-citation-auditor + privacy-tone-auditor (병렬)
  → response-validator-agent (취합)
      ├─ PASS → output-publisher-agent
      ├─ REVISE → response-writer-agent → 두 auditor → validator (최대 2회)
      ├─ ESCALATE → output-publisher-agent의 사람 검토용 제한 출력
      └─ REJECT → output-publisher-agent의 안전한 거절 출력
```

독립 전문 셀만 `ThreadPoolExecutor`로 병렬 실행한다. 표준 단계 간 순서는 유지한다. 병렬 작업 하나가 실패하면 해당 작업을 1회 재시도하고, 재실패하면 취합 Agent가 불완전한 결과를 정상 결과로 위장하지 않고 ESCALATE한다.

## 변경 대상 / 비대상

### 변경 대상

- 루트 `complaint_agents.py`: Agent 함수, 표준 데이터 계약, Supervisor DAG, 상태 머신, 재시도·수정 루프, trace와 Pixel Runtime 이벤트
- 루트 `app.py`: 실행 UI, 결과·오류·사람 검토 화면, HTML Canvas 픽셀 오피스와 이벤트 시각화
- 신규 `tests/`: 파이프라인, 계약, 상태 전이, 안전성, Pixel snapshot 및 UI smoke 테스트
- 필요 시 `assets/pixel_office/`: 기존 스타일을 유지하는 최소 추가 스프라이트
- `README.md`: 새 12-Agent 구조, 실행 흐름, 안전 경계 및 검증 방법

### 비대상

- 참고 구현 `minwon_multiagent/` 동기화 또는 구조 개편
- 실제 행정 처분, 자동 승인, 민원 답변 자동 발송
- 별도 React/Vite 앱, WebSocket 서버, 데이터베이스, 사용자 인증
- 외부 CDN 또는 대형 게임 엔진 도입
- 브라우저 새로고침을 넘어서는 영구 실행 이력 서비스

## 데이터 계약과 상태 전이

### 표준 산출물

각 실행은 `_workspace/traces/{trace_id}/`에 다음 JSON 파일을 원자적으로 기록한다.

1. `01_intake_result.json`: `IntakeResult`
2. `02_classification_result.json`: `ClassificationResult`
3. `03_evidence_package.json`: `EvidencePackage`
4. `04_draft_package.json`: `DraftPackage`
5. `05_validation_report.json`: `ValidationReport`
6. `06_final_output.json`: `FinalOutput`

필드와 enum은 `.harness/references/data-contracts.md`를 그대로 따른다. 전문 셀의 중간 결과는 `intermediate/` 하위에 두되 표준 생산자인 classifier, evidence-search, validator가 검증·취합한 뒤에만 다음 표준 단계로 전달한다.

조기 종료에서는 실행된 선행 산출물과 `06_final_output.json`만 요구한다. `manifest.json`에 실행하지 않은 단계와 사유를 기록한다. JSON 파일에는 API 키를 절대 기록하지 않으며 민원 원문은 `01_intake_result.json` 외 trace/event에 복제하지 않는다.

### 허용 상태 전이

```text
RECEIVED
  → NORMALIZED | INPUT_REJECTED | HUMAN_REVIEW_REQUIRED
NORMALIZED
  → CLASSIFIED | HUMAN_REVIEW_REQUIRED
CLASSIFIED
  → EVIDENCE_READY | HUMAN_REVIEW_REQUIRED
EVIDENCE_READY
  → DRAFT_READY
DRAFT_READY
  → VALIDATING
VALIDATING
  → APPROVED | REVISION_REQUIRED | HUMAN_REVIEW_REQUIRED | REJECTED
REVISION_REQUIRED
  → DRAFT_READY (revision_count + 1, 최대 2회)
APPROVED
  → PUBLISHED
HUMAN_REVIEW_REQUIRED | REJECTED | INPUT_REJECTED
  → PUBLISHED
```

정의되지 않은 상태 전이는 `InvalidStateTransition`으로 중단한다. `revision_count == 2`인 초안이 다시 REVISE 판정을 받으면 Supervisor는 PASS로 바꾸지 않고 `HUMAN_REVIEW_REQUIRED`로 전환한다.

### 최종 출력 불변 조건

- `ValidationReport.decision == PASS`이고 상태가 APPROVED인 경우에만 `FinalOutput.status == DRAFT_APPROVED`를 허용한다.
- BLOCKER가 하나라도 있거나 근거·관할·개인정보 HIGH가 있으면 PASS를 거부한다.
- ESCALATE에서는 승인 답변 대신 사유, 담당자가 확인할 항목, 확인 가능한 출처만 제공한다.
- 모든 `FinalOutput`은 `validation_report`, `disclaimer`, `trace_id`를 포함한다.
- 검색 패키지에 없거나 `verified: false`인 근거는 핵심 주장의 근거로 사용할 수 없다.

## 구현 작업

### 작업 1: 표준 모델과 스키마 검증 계층 구축

- 담당: `agent-pipeline-engineer`
- 대상 파일과 심볼: `complaint_agents.py`의 기존 parsing helper 및 신규 계약 dataclass/validator
- 변경 내용: `ComplaintInput`, `IntakeResult`, `ClassificationResult`, `EvidencePackage`, `DraftPackage`, `ValidationReport`, `FinalOutput`, 전문 셀 중간 결과 타입을 JSON 직렬화 가능한 dataclass 또는 명시적 validator로 정의한다.
- 입력/출력 계약: 필수 필드, enum, 숫자 범위, 리스트·객체 타입, URL/verified 관계를 검증한다.
- 오류 처리: LLM의 비JSON 또는 스키마 불일치는 동일 Agent에 오류 요약을 전달해 1회 재요청하고 재실패 시 ESCALATE한다.
- 테스트: 정상/필드 누락/잘못된 enum/문자열 confidence/빈 URL/미검증 근거 fixture.
- 완료 조건: 다음 단계가 검증되지 않은 dict를 받지 않으며 표준 payload round-trip 테스트가 통과한다.

### 작업 2: 입력·분류 전문 셀 구현

- 담당: `intake-agent`, `issue-analysis-agent`, `jurisdiction-analysis-agent`, `classifier-agent`
- 대상 파일과 심볼: 기존 `normalize_text`, `classify_complaint` 및 `ComplaintSupervisor` 등록 도구
- 변경 내용: 의미를 바꾸지 않는 입력 정규화, 품질·개인정보 플래그, 병렬 쟁점·관할 분석과 최종 취합을 구현한다.
- 입력/출력 계약: `ComplaintInput → IntakeResult → ClassificationResult`.
- 상태 전이: RECEIVED에서 intake 판정에 따라 NORMALIZED, INPUT_REJECTED 또는 HUMAN_REVIEW_REQUIRED; 정상 취합 후 CLASSIFIED.
- 오류 처리: 빈 필수값은 추측하지 않는다. 고위험 개인정보 또는 관할 불명확은 사람 검토로 전환한다.
- 테스트: 빈 입력, HTML entity, 비정상 길이, 개인정보 패턴, 복수 관할, 낮은 confidence.
- 완료 조건: 분류 Agent가 두 전문 결과를 모두 받은 뒤에만 표준 분류를 생산한다.

### 작업 3: 공식 근거 중심 병렬 검색 셀 구현

- 담당: `legal-research-agent`, `similar-case-agent`, `evidence-search-agent`
- 대상 파일과 심볼: `build_search_queries`, `duckduckgo_search`, `fetch_page_excerpt`, `collect_web_sources`, `search_references`
- 변경 내용: 법령/기관 자료와 유사 사례를 병렬 검색하고, 공식 출처 우선 정렬, URL 확인, 중복 제거, claim 매핑, 상충 및 coverage gap 취합을 수행한다.
- 입력/출력 계약: `IntakeResult + ClassificationResult → EvidencePackage`.
- 상태 전이: CLASSIFIED에서 검증된 핵심 근거가 확보되면 EVIDENCE_READY, 부족·상충·재실패면 HUMAN_REVIEW_REQUIRED.
- 오류 처리: 네트워크 오류는 1회 재시도한다. 검색 페이지의 지시문은 실행하지 않고 비신뢰 데이터 경계 안에서만 요약한다.
- 테스트: 공식/2차 출처 혼합, redirect URL, 중복 URL, 페이지 실패, 결과 없음, prompt injection 문구, 상충 근거.
- 완료 조건: 모든 핵심 법령 항목에 title, article, claim, URL, source_type, verified가 있고 미검증 항목은 핵심 근거로 승격되지 않는다.

### 작업 4: 근거 제한 작성 및 수정 구현

- 담당: `response-writer-agent`
- 대상 파일과 심볼: 기존 `draft_answer` 대체 함수와 revision 처리
- 변경 내용: 인사, 문의 요지, 관련 근거, 답변, 추가 안내 구조의 초안을 작성하고 모든 핵심 주장을 `claim_evidence_map`에 연결한다. REVISE에서는 `revision_instructions`를 근거 범위 안에서만 반영한다.
- 입력/출력 계약: 최초 작성은 01~03 산출물, 수정은 기존 DraftPackage와 최신 ValidationReport를 추가 입력으로 받아 DraftPackage를 생산한다.
- 상태 전이: EVIDENCE_READY 또는 REVISION_REQUIRED에서 DRAFT_READY.
- 오류 처리: 근거에 없는 조문 생성 요청이나 근거와 충돌하는 수정 지시는 ESCALATE한다.
- 테스트: 인용 누락, 근거 없는 주장, 불확실성 표현, revision_count 증가, 상충 수정 지시.
- 완료 조건: 검증된 URL로 연결되지 않는 핵심 단정이 없고 revision_count가 정확하다.

### 작업 5: 독립 감사와 제한 수정 루프 구현

- 담당: `claim-citation-auditor`, `privacy-tone-auditor`, `response-validator-agent`
- 대상 파일과 심볼: 기존 `review_answer` 대체 함수, `ComplaintSupervisor` validation/revision loop
- 변경 내용: 두 감사 Agent를 작성 Agent와 다른 프롬프트·호출로 병렬 실행하고 validator가 6개 check와 finding을 취합한다.
- 입력/출력 계약: 01~04 산출물 및 감사 중간 결과를 받아 `ValidationReport`를 생산한다.
- 상태 전이: DRAFT_READY → VALIDATING → APPROVED/REVISION_REQUIRED/HUMAN_REVIEW_REQUIRED/REJECTED.
- 오류 처리: 검증 불능을 PASS로 처리하지 않는다. 감사 Agent 재실패는 ESCALATE한다.
- 테스트: BLOCKER/HIGH PASS 금지, REVISE 재호출 순서, 두 번 수정 후 강제 사람 검토, 작성·검증 역할 독립성.
- 완료 조건: 모든 최종 초안에 독립 ValidationReport가 존재하고 PASS 승격 규칙이 강제된다.

### 작업 6: 안전한 최종 출판 구현

- 담당: `output-publisher-agent`
- 대상 파일과 심볼: 신규 publisher 함수와 `ComplaintSupervisor.to_result`
- 변경 내용: 최종 상태와 ValidationReport를 `FinalOutput`으로 변환하며 새로운 사실은 생성하지 않는다.
- 입력/출력 계약: 전체 표준 산출물 + trace → `FinalOutput`.
- 상태 전이: 종료 가능 상태에서 PUBLISHED.
- 오류 처리: 최종 형식 생성 실패 시 초안을 노출하지 않고 HUMAN_REVIEW_REQUIRED 제한 결과를 최소 계약으로 생성한다.
- 테스트: PASS/ESCALATE/REJECT/INPUT_REJECTED별 answer와 citation 노출 규칙.
- 완료 조건: PASS 없는 결과가 UI 또는 다운로드에서 승인 초안으로 표시되지 않는다.

### 작업 7: Supervisor DAG, 파일 handoff와 감사 trace 구현

- 담당: `agent-pipeline-engineer`
- 대상 파일과 심볼: `SupervisorTool`, `PixelAgentStateStore`, `ComplaintSupervisor.__init__`, `initial_state`, `invoke_tool`, 신규 `run`
- 변경 내용: requires/provides 기반 DAG, 병렬 셀, 상태 머신, 1회 재시도, 최대 2회 revision, trace 디렉터리와 원자적 JSON 저장을 구현한다.
- 이벤트 계약: `agentCreated → agentToolStart → handoffProduced → agentToolDone`; 실패는 `agentToolFailed → supervisorDecision`; 마지막은 `finalStatus`.
- 오류 처리: 부분 병렬 실패, 파일 기록 실패, 정의되지 않은 상태 전이를 안전하게 사람 검토 또는 실패로 종료한다.
- 테스트: 이벤트 순서, 병렬 완료 후 취합 barrier, 조기 종료 파일 목록, 재실행 격리, 원문/API 키 비노출.
- 완료 조건: 각 Agent의 입력, 출력, 상태, handoff와 Supervisor 결정이 하나의 trace_id로 재구성 가능하다.

### 작업 8: HTML Canvas Pixel Office 구현

- 담당: `streamlit-pixel-engineer`
- 대상 파일과 심볼: `app.py`의 `OFFICE_AGENTS`, `build_idle_runtime_snapshot`, `render_pixel_office`, `render_pixel_runtime`
- 변경 내용: 현재 CSS 중심 오피스를 바닐라 Canvas 기반 상태 애니메이션으로 교체한다.
- 공간: 접수 데스크, 분류 셀, 법령 자료실, 사례 검색실, 작성석, 검증실, Supervisor 데스크, 회의실, 사람 검토 창구.
- 동작: 보행, 착석, 타이핑, 자료 열람, 문서 전달, 두 문서 취합 대기, 교차 검토, 수정 반송, 회의, 오류 알림, 사람 검토 이동.
- 병렬 표현: 독립 셀 Agent가 동시에 움직이고, 취합 Agent는 필요한 handoff가 모두 도착한 뒤 활성화한다.
- 반응형: 논리 좌표는 고정하고 Canvas를 컨테이너 크기에 맞춰 스케일한다. 긴 한글은 escape·축약하고 상세는 이벤트 패널에 표시한다.
- 접근성: `prefers-reduced-motion`에서는 이동을 즉시 반영하고 반복 애니메이션을 줄인다.
- fallback: asset이 없으면 팀 색상의 픽셀 도형 캐릭터·가구를 렌더링한다.
- 테스트: 12개 Agent snapshot, zone/activity 매핑, 긴 한글, 좁은 화면, asset 누락, HTML 특수문자.
- 완료 조건: 화면의 위치, 행동, handoff, 실패, 수정 및 종료 상태가 실제 Runtime 이벤트와 일치한다.

### 작업 9: Streamlit 실행·결과 UX 개편

- 담당: `streamlit-pixel-engineer`
- 대상 파일과 심볼: `run_pipeline`, `render_results`, `main`
- 변경 내용: UI가 도구 순서를 직접 호출하지 않고 Supervisor `run`을 실행하도록 변경한다. 전체 단계, 전문 셀, revision과 최종 판정을 표시한다.
- 모델 설정: 기본 화면은 역할군별 모델을 설정하고 고급 설정에서만 Agent별 override를 제공한다.
- 결과 화면: 판정, 답변 또는 사람 검토 사유, 출처, 검증 보고서, 수정 이력, handoff, trace를 분리한다.
- 다운로드: 화면과 동일한 FinalOutput 및 비민감 trace만 포함한다.
- 오류 처리: 재실행 시 이전 상태를 초기화하고 실패한 trace를 보존하되 다른 실행과 섞지 않는다.
- 테스트: 초기, 실행, 성공, 수정 후 성공, 검색 실패, 사람 검토, 거절, 재실행 Streamlit smoke 시나리오.
- 완료 조건: 승인 여부와 업무 진행 상태를 사용자가 오인하지 않으며 Canvas와 결과 패널이 같은 snapshot을 사용한다.

### 작업 10: 안전성 검토, 회귀 테스트와 문서화

- 담당: `civic-safety-reviewer`, `integration-qa`
- 대상: 전체 변경 diff, `tests/`, `README.md`, Claude 구현 기록
- 변경 내용: 법령 정확성, 관할 단정, 개인정보 재노출, prompt injection, 생산자/소비자 필드, UI/Runtime 일치를 독립 검토한다.
- 결과 기록: `_workspace/03_civic-safety-review.md`, `_workspace/04_integration-qa_report.md`, `_workspace/CLAUDE_IMPLEMENTATION.md`.
- 완료 조건: 각 계획 작업이 구현 기록과 1:1로 대응하고 자동·수동 검증이 PASS/FAIL/NOT RUN으로 구분된다.

## Pixel Runtime 공개 인터페이스

`PixelAgentState`는 최소 다음 필드를 가진다.

```json
{
  "agent_id": "string",
  "display_name": "string",
  "role": "string",
  "team": "intake|classification|evidence|writing|validation|publishing",
  "status": "waiting|moving|active|blocked|error|done",
  "zone": "string",
  "target_zone": "string|null",
  "activity": "idle|walking|typing|reading|handoff|reviewing|meeting|alert",
  "task_id": "string|null",
  "last_safe_summary": "string",
  "outputs": []
}
```

모든 Pixel 이벤트는 다음 공통 envelope를 사용한다.

```json
{
  "seq": 1,
  "timestamp": "ISO-8601",
  "trace_id": "string",
  "type": "agentCreated|agentToolStart|agentMove|handoffProduced|agentToolDone|agentToolFailed|supervisorDecision|finalStatus",
  "agent_id": "string|null",
  "task_id": "string|null",
  "from_zone": "string|null",
  "to_zone": "string|null",
  "safe_summary": "string"
}
```

이벤트에는 API 키, 민원 원문, 웹 페이지 본문, 전체 LLM 응답을 넣지 않는다. Canvas는 snapshot과 이벤트만 소비하며 비즈니스 판정을 만들거나 변경하지 않는다.

## 작업 순서와 의존성

1. 시스템 아키텍트가 계약, 상태 머신, DAG, 파일 소유권을 확정한다.
2. 파이프라인 엔지니어가 표준 모델과 Supervisor 기반을 먼저 구현한다.
3. 입력·분류 셀과 검색 셀을 구현하고 계약 테스트를 통과시킨다.
4. Writer, 감사 셀, Validator, Publisher와 revision 루프를 구현한다.
5. Pixel 이벤트 snapshot을 고정한 뒤 UI 엔지니어가 Canvas와 결과 UX를 구현한다.
6. Civic Safety Reviewer가 프롬프트, 검색, 로그와 출력을 독립 검토한다.
7. Integration QA가 전체 handoff, 상태, 오류, UI를 검증하고 담당 구현자에게 수정 사항을 반환한다.
8. 회귀 수정 후 전체 게이트를 다시 실행하고 Claude 구현 기록을 작성한다.

공유 파일 충돌을 피하기 위해 파이프라인 엔지니어는 `complaint_agents.py`, UI 엔지니어는 `app.py`를 소유한다. UI에 전달하는 shape 변경은 먼저 작업 노트에 기록하고 양쪽 테스트 fixture를 함께 갱신한다.

## 테스트 시나리오와 인수 기준

### 자동 테스트

- 빈 제목·본문, HTML entity, 고위험 개인정보 입력의 CONTINUE/REJECT/ESCALATE 판정
- 쟁점·관할 전문 결과가 `ClassificationResult`로 정확히 취합되는지 검증
- 법령·사례 병렬 실행, 공식 출처 우선, 중복 제거, 상충·coverage gap 보존
- 미검증 URL이 핵심 주장 근거로 승격되지 않는지 검증
- 모든 초안 핵심 주장이 `claim_evidence_map`의 검증 URL에 연결되는지 검증
- BLOCKER 또는 근거·관할·개인정보 HIGH가 PASS되지 않는지 검증
- REVISE가 Writer와 두 감사 Agent를 재호출하고 2회 초과 시 사람 검토로 전환되는지 검증
- PASS 없는 결과가 `DRAFT_APPROVED`로 출판되지 않는지 검증
- 네트워크 오류, HTTP 오류, 빈 choices, 비JSON, 필수 필드 누락의 1회 재시도와 ESCALATE
- 허용되지 않은 상태 전이 거부
- 병렬 전문 Agent 완료 후 취합 순서 및 이벤트 seq 일관성
- 이벤트와 오류에 API 키·민원 원문·웹 본문이 포함되지 않는지 검증
- Canvas snapshot의 12개 Agent, zone, activity, handoff, 최종 상태 일치
- 긴 한글, 좁은 화면, asset 누락, HTML 특수문자의 안전한 UI fallback

### 수동 UI 검증

브라우저에서 다음 시나리오를 각각 PASS/FAIL/NOT RUN으로 기록한다.

1. 표준 성공: 12개 Agent의 이동과 handoff 후 DRAFT_APPROVED 표시
2. 수정 후 성공: 검증실에서 작성실로 문서가 반송되고 재검증 후 승인
3. 두 번 수정 실패: 회의실과 사람 검토 창구 이동 후 HUMAN_REVIEW_REQUIRED 표시
4. 검색 결과 없음 또는 네트워크 재실패: 초안 강행 없이 사람 검토 전환
5. 입력 거절: 후속 처리 Agent 미실행과 안전한 INPUT_REJECTED 출력
6. 재실행: 이전 trace와 Agent 상태가 새 실행에 섞이지 않음
7. 반응형/접근성: 좁은 화면과 reduced motion 환경에서 정보 손실 없음

## 마이그레이션과 호환성

- 실행 명령 `streamlit run app.py`, 샘플 Excel, OpenRouter API 키 입력 방식은 유지한다.
- 기존 `last_result` session state는 버전 필드가 없는 경우 폐기하고 새 schema snapshot으로 초기화한다.
- 기존 다운로드 JSON은 새 `FinalOutput + trace` 구조로 변경되는 공개 동작 변경이다. README에 이전/신규 필드 대응표를 추가한다.
- 기존 PNG asset은 우선 재사용하고 신규 asset은 같은 `assets/pixel_office/` 규칙을 따른다.
- 신규 Python 의존성은 원칙적으로 추가하지 않는다. 불가피할 경우 루트 `requirements.txt`에만 추가하고 참고 패키지 요구사항은 변경하지 않는다.
- `minwon_multiagent/`와의 API 호환 또는 동기화는 보장하지 않는다.

## 위험과 완화책

- Agent 수 증가에 따른 비용·지연: 독립 작업 병렬화, 역할군 기본 모델, 검색 수 제한, 상세 Agent override를 제공한다.
- 병렬 결과의 비결정성: 표준 정렬, 취합 barrier, event seq의 중앙 발급으로 결과 순서를 결정적으로 만든다.
- Streamlit의 실행 중 갱신 제약: 각 Agent 시작·완료 callback에서 snapshot을 갱신하고 Canvas 내부 프레임 보간으로 자연스러운 이동을 표현한다.
- 외부 검색의 부정확성: 공식 출처 우선, URL 확인, verified 플래그, 상충·공백 보존, 핵심 근거 부족 시 ESCALATE한다.
- LLM의 스키마 이탈: 명시적 validator, 1회 교정 재요청, 재실패 시 사람 검토로 제한한다.
- 개인정보 노출: safe summary만 이벤트에 기록하고 원문/API 키/웹 본문이 trace에 들어가지 않는 테스트를 둔다.
- Canvas asset 누락·레이아웃 붕괴: 도형 fallback, 논리 좌표 스케일링, 좁은 화면 테스트를 적용한다.

## 전체 검증 명령

```bash
bash scripts/validate_harness.sh
python -m compileall app.py complaint_agents.py tests
pytest -q
rg -n 'sk-or-|Authorization: Bearer|api[_-]?key\s*=' .
streamlit run app.py
```

실제 OpenRouter 호출 테스트는 기본 pytest에서 mock 처리하고, 실 API 검증은 환경 변수로 명시적으로 활성화하는 opt-in 테스트로 분리한다.

## 전체 완료 조건

- 12개 Agent의 책임, 입력, 출력과 handoff가 trace에서 구분된다.
- 독립 전문 셀은 병렬 실행되고 하네스 표준 단계는 정해진 순서를 유지한다.
- 01~06 산출물과 실제 상태 전이가 하네스 계약에 부합한다.
- 작성과 검증이 독립되어 있고 최대 2회 수정 제한이 강제된다.
- PASS 없는 결과는 승인 초안으로 표시되거나 다운로드되지 않는다.
- Canvas 오피스의 위치, 행동, 문서 전달, 회의, 오류 상태가 실제 이벤트와 일치한다.
- 재실행 시 이전 실행의 Agent, 이벤트, 산출물이 섞이지 않는다.
- 자동 테스트와 하네스 검증이 통과하고 수동 UI 시나리오 결과가 기록된다.
- `minwon_multiagent/`에는 변경이 없고 기존 샘플 입력과 OpenRouter 설정을 계속 사용할 수 있다.

## 사용자 결정 필요 사항

없음. 다음 기본값을 확정한다.

- 12개 전문 Agent 모드를 기본 실행 모드로 사용한다.
- 모든 LLM 기반 Agent의 OpenRouter 기본 모델은 DeepSeek V3(`deepseek/deepseek-chat`)로 통일한다.
- 픽셀 오피스는 외부 프론트엔드 없이 Streamlit HTML Canvas로 구현한다.
- 루트 구현만 고도화하고 `minwon_multiagent/`는 비대상으로 둔다.
- 모든 결과는 담당자 검토 전 초안이며 실제 행정 결정이나 자동 발송을 수행하지 않는다.

## Claude Code 인계 지시

1. 구현 전에 `AGENTS.md`, `.harness/skills/minwon-orchestrator/SKILL.md`, `.harness/references/business-workflow.md`, `.harness/references/data-contracts.md`, 본 계획을 순서대로 읽는다.
2. `system-architect → agent-pipeline-engineer/streamlit-pixel-engineer → civic-safety-reviewer → integration-qa` 순서로 하네스 역할을 수행한다.
3. 계획과 다른 구조가 필요하면 임의 확장하지 말고 `_workspace/CLAUDE_IMPLEMENTATION.md`의 계획 대비 변경 사항에 이유와 영향을 먼저 기록한다.
4. 구현 후 `docs/CODEX_CLAUDE_HANDOFF.md` 형식으로 `_workspace/CLAUDE_IMPLEMENTATION.md`를 작성한다.
5. 테스트하지 못한 항목은 통과로 표시하지 말고 NOT RUN과 재현 절차를 남긴다.
