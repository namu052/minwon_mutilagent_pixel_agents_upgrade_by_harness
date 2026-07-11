# 민원 업무 Agent 워크플로

이 문서는 하네스의 최우선 실행 계약이다. 코딩 에이전트 구조보다 실제 민원 처리 흐름이 우선한다.

## 전체 흐름

```text
[입력]
민원번호·제목·본문
  ↓ intake-agent
정규화된 민원 + 개인정보/입력 품질 플래그
  ↓
[처리]
classifier-agent → 담당 부서·유형·검색 쟁점
  ↓
evidence-search-agent → 공식 근거·유사 사례·출처
  ↓
response-writer-agent → 근거 기반 답변 초안
  ↓
[검증]
response-validator-agent → PASS | REVISE | ESCALATE | REJECT
  ├─ REVISE → response-writer-agent 재작성 → 재검증(최대 2회)
  ├─ ESCALATE → 사람 검토용 결과
  ├─ REJECT → 안전한 실패 결과
  └─ PASS
       ↓
[출력]
output-publisher-agent → 최종 초안 + 출처 + 검증 결과 + 실행 trace
```

## 불변 규칙

1. 모든 단계는 이전 단계의 구조화된 산출물을 입력으로 받는다.
2. 검색 Agent가 제공하지 않은 법령·조문을 작성 Agent가 새로 만들어내지 않는다.
3. 검증 Agent는 작성 Agent와 독립된 역할이어야 한다.
4. `PASS` 없는 초안을 승인된 최종 답변처럼 출력하지 않는다.
5. `REVISE`는 최대 2회다. 이후에도 실패하면 `ESCALATE`한다.
6. 개인정보 고위험, 관할 불명확, 근거 상충, 위해 가능성은 사람 검토로 보낸다.
7. 모든 출력에는 “담당자 검토 전 초안” 상태와 검증 판정을 표시한다.

## 상태 전이

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
  → PUBLISHED (안전한 제한 출력)
```

정의되지 않은 상태 전이는 허용하지 않는다. Supervisor는 단계 시작·완료·실패 및 handoff를 trace에 남긴다.

