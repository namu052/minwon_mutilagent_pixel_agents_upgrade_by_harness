---
name: minwon-orchestrator
description: "AI Agent가 민원 업무를 입력→처리→검증→출력 순서로 수행하도록 조율한다. 민원 분류, 법령·사례 검색, 답변 작성, 독립 검수, 수정 반복, 사람 검토 전환, 최종 결과와 실행 trace 생성 요청에 반드시 사용한다. 민원 처리 재실행·수정·보완·부분 재처리에도 사용한다."
---

# Minwon Business Supervisor

## 최우선 목표

이 스킬은 코드를 개발하는 절차가 아니라 **AI Agent가 실제 민원 업무를 처리하는 실행 구조**를 정의한다. 전체 실행에서 입력 → 처리 → 검증 → 출력 단계와 각 handoff가 관찰 가능해야 한다.

반드시 `.harness/references/business-workflow.md`와 `.harness/references/data-contracts.md`를 먼저 읽는다.

## Agent 구성

| 단계 | Agent | 책임 | 산출물 |
|---|---|---|---|
| 입력 | intake-agent | 정규화·필수값·개인정보 위험 | `01_intake_result.json` |
| 처리 | classifier-agent | 관할·유형·쟁점 분류 | `02_classification_result.json` |
| 처리 | evidence-search-agent | 공식 근거·유사 사례 검색 | `03_evidence_package.json` |
| 처리 | response-writer-agent | 근거 기반 답변 작성 | `04_draft_package.json` |
| 검증 | response-validator-agent | 독립 품질·근거·안전 검증 | `05_validation_report.json` |
| 출력 | output-publisher-agent | 판정 기반 최종 결과 | `06_final_output.json` |

## 실행 원칙

- 업무 흐름은 순차 파이프라인이며 작성↔검증 구간만 제한적으로 반복한다.
- 각 Agent는 공용 역할 파일과 데이터 계약을 따른다.
- 런타임이 팀/서브에이전트를 지원하면 역할별로 호출한다. 지원하지 않으면 Supervisor가 같은 역할을 순차 수행한다.
- 파일 기반 handoff를 기준으로 삼아 Codex와 Claude Code에서 같은 결과 구조를 유지한다.
- 사용자가 부분 재실행을 요청하면 해당 단계 이후 산출물만 무효화한다.

## Phase 0 — 실행 준비

1. 민원별 고유 `trace_id`를 만든다.
2. `_workspace/`에 기존 결과가 있으면 새 trace 디렉토리로 분리하거나 보존한다.
3. 원문과 API 키가 로그에 노출되지 않도록 기록 수준을 정한다.
4. 상태를 `RECEIVED`로 기록한다.

## Phase 1 — 입력

intake-agent에 `ComplaintInput`을 전달한다. `CONTINUE`만 처리 단계로 넘긴다.

- REJECT → `INPUT_REJECTED`로 출력 단계 이동
- ESCALATE → `HUMAN_REVIEW_REQUIRED`로 출력 단계 이동
- CONTINUE → `NORMALIZED`

## Phase 2 — 처리

1. classifier-agent 실행 → `CLASSIFIED`
2. evidence-search-agent 실행 → `EVIDENCE_READY`
3. response-writer-agent 실행 → `DRAFT_READY`

어느 Agent든 ESCALATE하면 후속 생성을 중단하고 출력 단계로 이동한다. 검색 근거가 부족한데 작성 Agent를 강행하지 않는다.

## Phase 3 — 검증 및 수정 루프

response-validator-agent가 모든 선행 산출물을 교차 비교한다.

```text
PASS      → APPROVED
REVISE    → writer 재호출 → validator 재호출 (최대 2회)
ESCALATE  → HUMAN_REVIEW_REQUIRED
REJECT    → REJECTED
```

수정 2회 후에도 PASS가 아니면 자동으로 `HUMAN_REVIEW_REQUIRED`로 전환한다. Supervisor가 검증 판정을 임의로 PASS로 바꾸지 않는다.

## Phase 4 — 출력

output-publisher-agent가 `FinalOutput`을 생성한다.

- APPROVED만 `DRAFT_APPROVED`
- HUMAN_REVIEW_REQUIRED는 승인 답변 대신 사유·확인 항목 제공
- REJECTED/INPUT_REJECTED는 안전한 제한 출력
- 모든 결과에 출처, 검증 보고서, disclaimer, trace_id 포함

## 이벤트와 감사 추적

각 Agent에 대해 다음 이벤트를 순서대로 남긴다.

```text
agentCreated → agentToolStart → handoffProduced → agentToolDone
실패 시 agentToolFailed → supervisorDecision
최종 finalStatus
```

이벤트 payload에는 원문 전체나 API 키를 넣지 않는다. 파일명, 상태, 요약, trace_id만 기록한다.

## 실패 처리

- 네트워크 오류: 1회 재시도 후 ESCALATE
- JSON/schema 불일치: 해당 Agent 1회 재요청 후 ESCALATE
- 출처 검증 실패: 미검증 근거 제거 후 coverage gap 기록; 핵심 근거면 ESCALATE
- Agent 호출 불가: Supervisor가 같은 계약으로 직접 수행하거나 HUMAN_REVIEW_REQUIRED
- 최종 출력 실패: 초안 노출 없이 HUMAN_REVIEW_REQUIRED

## 완료 조건

다음 조건을 모두 만족해야 정상 완료다.

- `01`~`06` 산출물 또는 조기 종료에 필요한 산출물이 존재
- 실제 상태 전이가 허용된 맵과 일치
- 초안의 핵심 주장과 출처가 매핑됨
- 독립 ValidationReport가 존재
- PASS 없는 결과가 DRAFT_APPROVED로 표시되지 않음
- 입력 → 처리 → 검증 → 출력 이벤트가 trace에서 확인됨

