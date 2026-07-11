# 민원 멀티에이전트 픽셀 오피스 하네스

> **한 문장:** 민원 접수부터 관할 분류, 공식 근거 검색, 답변 작성, 독립 검증, 안전한 최종 출력까지를 **12개 전문 업무 Agent**가 분업하고, 그 실행 과정을 **픽셀 아트 사무실**과 파일 기반 trace로 보여주는 Streamlit 애플리케이션입니다.

이 프로젝트는 단일 LLM에게 “민원 답변을 작성해 달라”고 맡기지 않습니다. 실제 행정 조직처럼 접수, 분류, 법령 조사, 사례 조사, 작성, 인용 감사, 개인정보·문체 감사, 출판 역할을 분리하고, 각 단계가 구조화된 산출물을 다음 단계에 전달하도록 강제합니다.

핵심 목표는 답변을 많이 생성하는 것이 아니라 다음 세 가지를 동시에 만족하는 것입니다.

- **분업:** 역할별 Agent가 자기 책임과 경계를 지킵니다.
- **검증:** 작성 Agent와 검증 Agent를 분리해 자기검증 편향을 줄입니다.
- **감사 가능성:** 상태 전이, handoff, 출처와 판정을 `trace_id` 단위로 재구성할 수 있습니다.

모든 결과는 **담당자 검토 전 초안**입니다. 독립 검증에서 `PASS`를 받지 않은 초안은 승인된 답변처럼 표시하거나 다운로드하지 않습니다.

---

## 1. 프로젝트가 해결하는 문제

민원 답변은 단순한 문장 생성이 아닙니다. 최소한 다음 판단이 서로 분리되어야 합니다.

1. 입력이 처리 가능한지, 개인정보 위험은 없는지
2. 어느 기관·부서의 어떤 유형 민원인지
3. 답변에 필요한 법령과 공식 사례가 실제로 존재하는지
4. 검색한 근거만으로 어떤 범위까지 답할 수 있는지
5. 초안의 주장과 출처가 정확히 연결되는지
6. 관할 단정, 개인정보 재노출, 부적절한 문체가 없는지
7. 자동 초안을 제공할지 사람 검토로 전환할지

이 프로젝트의 하네스는 위 판단을 역할별 Agent와 품질 게이트로 분리합니다. 근거가 부족하거나 관할이 불명확한데도 답변을 강행하지 않으며, 안전하게 처리할 수 없는 실행은 `HUMAN_REVIEW_REQUIRED`로 종료합니다.

---

## 2. 전체 아키텍처

이 시스템은 **순차 파이프라인 + 병렬 전문 셀 + 생성–독립검증 루프** 구조입니다.

```text
사용자/Excel 민원 입력
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ ComplaintSupervisor                                         │
│ trace 생성 · DAG 조율 · 상태 전이 · 재시도 · 파일 handoff   │
│ ※ 내용 판정이나 PASS 승격은 수행하지 않음                   │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
intake-agent
        │
        ├──────────── 병렬 분류 셀 ──────────────┐
        ▼                                        ▼
issue-analysis-agent              jurisdiction-analysis-agent
        └──────────────────┬─────────────────────┘
                           ▼
                    classifier-agent
                           │
        ├──────────── 병렬 근거 셀 ──────────────┐
        ▼                                        ▼
legal-research-agent                    similar-case-agent
        └──────────────────┬─────────────────────┘
                           ▼
                 evidence-search-agent
                           │
                           ▼
                 response-writer-agent
                           │
        ├──────────── 병렬 검증 셀 ──────────────┐
        ▼                                        ▼
claim-citation-auditor                 privacy-tone-auditor
        └──────────────────┬─────────────────────┘
                           ▼
                response-validator-agent
                 │         │          │
              PASS      REVISE     ESCALATE/REJECT
                 │         │          │
                 │         └─ writer로 반려      │
                 │            최대 2회            │
                 └──────────────┬─────────────────┘
                                ▼
                   output-publisher-agent
                                │
                                ▼
          FinalOutput + 출처 + 검증 결과 + 실행 trace
```

독립적인 분석·검색·감사 작업만 병렬 실행됩니다. 취합 Agent는 필요한 모든 handoff가 도착한 뒤에만 시작합니다. 병렬 작업이 실패하면 1회 재시도하고, 재실패하면 불완전한 결과를 정상 결과로 위장하지 않고 사람 검토로 전환합니다.

---

## 3. 12개 업무 Agent

Supervisor는 업무 Agent 수에 포함되지 않습니다. Supervisor는 실행을 조율하지만 민원 내용이나 검증 결과를 임의로 바꾸지 않습니다.

| 단계 | Agent | 책임 | 하지 않는 일 | 주요 산출물 |
|---|---|---|---|---|
| 입력 | `intake-agent` | 입력 정규화, 필수값·품질·개인정보 위험 판정 | 누락값 추측, 의미 변경 | `01_intake_result.json` |
| 분류 | `issue-analysis-agent` | 요구사항·사실관계·쟁점 추출 | 관할 최종 확정 | `intermediate/issue_analysis.json` |
| 분류 | `jurisdiction-analysis-agent` | 관할 후보·확신도·불확실성 분석 | 초안 작성 | `intermediate/jurisdiction_analysis.json` |
| 분류 | `classifier-agent` | 두 분석을 취합해 담당 부서·유형·검색어 확정 | 근거 없는 관할 단정 | `02_classification_result.json` |
| 근거 | `legal-research-agent` | 공식 법령·기관 자료 검색 | 검색 결과에 없는 조문 생성 | `intermediate/legal_research.json` |
| 근거 | `similar-case-agent` | 공식 유사 사례·과거 답변 검색 | 비공식 사례의 사실 승격 | `intermediate/similar_case.json` |
| 근거 | `evidence-search-agent` | URL 검증, 중복 제거, 상충·공백 취합 | 미검증 근거 승인 | `03_evidence_package.json` |
| 작성 | `response-writer-agent` | 검증된 근거만 사용해 최초·수정 초안 작성 | 새로운 법령·URL 창작 | `04_draft_package.json` |
| 검증 | `claim-citation-auditor` | 주장–근거–인용 대응 독립 감사 | 원고 직접 수정 | `intermediate/citation_audit_r*.json` |
| 검증 | `privacy-tone-auditor` | 입력 충실성, 관할 표현, 문체, 개인정보 감사 | 인용 정확성 최종 판정 | `intermediate/privacy_audit_r*.json` |
| 검증 | `response-validator-agent` | 두 감사를 취합해 `PASS/REVISE/ESCALATE/REJECT` 판정 | PASS 임의 승격 | `05_validation_report.json` |
| 출력 | `output-publisher-agent` | 판정에 맞는 승인 초안 또는 제한 결과 생성 | 새로운 사실 추가 | `06_final_output.json` |

### 검증과 수정 루프

```text
PASS      → APPROVED → DRAFT_APPROVED
REVISE    → Writer 재작성 → 두 Auditor 재검증 (최대 2회)
ESCALATE  → HUMAN_REVIEW_REQUIRED
REJECT    → REJECTED
```

수정 2회 뒤에도 `PASS`가 아니면 자동으로 사람 검토로 전환합니다. 검증 단계에 도달하지 못한 실행은 UI에서 `FAIL`이 아니라 `NOT RUN`으로 표시합니다.

---

## 4. 하네스 구성

하네스는 특정 코딩 도구의 프롬프트 모음이 아니라, **민원 업무의 역할·계약·상태·검증·인계 방식을 저장소 안에서 고정하는 실행 규약**입니다.

### 4.1 단일 진실 공급원(SSOT)

```text
.harness/
├── skills/
│   └── minwon-orchestrator/SKILL.md   # 전체 업무 실행 SOP
├── agents/
│   ├── intake-agent.md                # 6개 표준 업무 역할
│   ├── classifier-agent.md
│   ├── evidence-search-agent.md
│   ├── response-writer-agent.md
│   ├── response-validator-agent.md
│   ├── output-publisher-agent.md
│   ├── system-architect.md             # 개발·고도화 보조 역할
│   ├── agent-pipeline-engineer.md
│   ├── streamlit-pixel-engineer.md
│   ├── civic-safety-reviewer.md
│   └── integration-qa.md
└── references/
    ├── business-workflow.md            # 업무 흐름과 허용 상태 전이
    ├── data-contracts.md               # 01~06 JSON 데이터 계약
    ├── project-map.md                  # 루트/참고 구현 경계
    └── quality-gates.md                # 필수 검증 항목
```

역할과 규칙을 변경할 때는 `.harness/`를 먼저 수정합니다. `.claude/`와 `.agents/`는 공용 원본을 가리키는 어댑터이며 별도의 규칙 원본이 아닙니다.

### 4.2 런타임별 진입점과 어댑터

| 경로 | 대상 | 역할 |
|---|---|---|
| `AGENTS.md` | Codex | 프로젝트 범위, 계획 책임, 하네스 진입점 |
| `CLAUDE.md` | Claude Code | 구현 책임, 공용 하네스 진입점 |
| `.agents/skills/minwon-orchestrator/` | Codex 호환 계층 | 공용 orchestrator 스킬 포인터 |
| `.claude/skills/minwon-orchestrator/` | Claude Code | 공용 orchestrator 스킬 포인터 |
| `.claude/agents/` | Claude Code | 공용 역할 파일을 호출하는 Agent 어댑터 |

팀/서브에이전트 기능이 있는 런타임에서는 역할별 Agent를 호출합니다. 해당 기능이 없으면 Supervisor가 같은 역할과 데이터 계약을 유지한 채 순차 실행합니다. 런타임이 달라도 산출물 형식과 품질 게이트는 동일합니다.

### 4.3 업무 Agent와 개발 Agent의 분리

하네스에는 두 종류의 역할이 있습니다.

- **업무 Agent:** 실제 민원을 입력 → 처리 → 검증 → 출력합니다.
- **개발 Agent:** 앱과 하네스를 분석·구현·검토·테스트합니다.

개발 Agent는 업무 Agent를 대체하지 않습니다.

| 개발 역할 | 담당 영역 | 주요 인계 문서 |
|---|---|---|
| `system-architect` | 구현 경계, 상태 머신, 계약 설계 | `_workspace/01_system-architect_plan.md` |
| `agent-pipeline-engineer` | OpenRouter, Agent 함수, DAG, handoff | `_workspace/02_agent-pipeline-engineer_notes.md` |
| `streamlit-pixel-engineer` | Streamlit UI, Canvas, session state | `_workspace/02_streamlit-pixel-engineer_notes.md` |
| `civic-safety-reviewer` | 법령·개인정보·검색 안전성 독립 검토 | `_workspace/03_civic-safety-review.md` |
| `integration-qa` | 계약, UI, 오류 경로, 회귀 검증 | `_workspace/04_integration-qa_report.md` |

### 4.4 Codex → Claude Code 인계

```text
Codex
  └─ 저장소·하네스 분석 및 결정 완료 계획
       └─ plan/CODEX_PLAN.md
            ▼
Claude Code
  └─ 계획 기반 구현·테스트
       └─ _workspace/CLAUDE_IMPLEMENTATION.md
            ▼
사용자
  └─ 구현 결과와 남은 위험 검토
```

Codex는 계획을 작성하고, Claude Code는 계획과 `.harness/` 계약을 기준으로 구현합니다. 인계 문서 형식과 공통 금지 사항은 [`docs/CODEX_CLAUDE_HANDOFF.md`](docs/CODEX_CLAUDE_HANDOFF.md)를 따릅니다.

---

## 5. 데이터 계약과 상태 전이

### 5.1 표준 파일 handoff

각 단계는 이전 단계의 구조화된 JSON만 입력으로 받습니다.

| 순서 | 계약 | 핵심 필드 |
|---:|---|---|
| 01 | `IntakeResult` | 정규화 민원, quality/privacy flags, `CONTINUE/REJECT/ESCALATE` |
| 02 | `ClassificationResult` | 부서, 유형, confidence, 쟁점, 검색어 |
| 03 | `EvidencePackage` | 법령, 사례, verified, conflicts, coverage gaps |
| 04 | `DraftPackage` | 초안, `claim_evidence_map`, uncertainties, revision count |
| 05 | `ValidationReport` | 6개 check, findings, 수정 지시, 최종 판정 |
| 06 | `FinalOutput` | status, answer, citations, validation report, disclaimer, trace ID |

필수 필드나 enum이 잘못된 LLM 응답은 다음 단계로 전달하지 않습니다. 같은 Agent에 스키마 교정을 1회 요청하고, 다시 실패하면 사람 검토로 전환합니다.

### 5.2 상태 머신

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
  → DRAFT_READY (최대 2회)
APPROVED | HUMAN_REVIEW_REQUIRED | REJECTED | INPUT_REJECTED
  → PUBLISHED
```

정의되지 않은 전이는 `InvalidStateTransition`으로 차단됩니다.

---

## 6. 실행 trace와 감사 로그

각 실행은 `_workspace/traces/{trace_id}/`에 독립적으로 저장됩니다.

```text
_workspace/traces/<trace_id>/
├── 01_intake_result.json
├── 02_classification_result.json
├── 03_evidence_package.json
├── 04_draft_package.json
├── 05_validation_report.json
├── 06_final_output.json
├── intermediate/
│   ├── issue_analysis.json
│   ├── jurisdiction_analysis.json
│   ├── legal_research.json
│   ├── similar_case.json
│   ├── draft_r*.json
│   ├── citation_audit_r*.json
│   └── privacy_audit_r*.json
├── events.json
└── manifest.json
```

조기 종료에서는 실행된 단계와 `06_final_output.json`만 생성됩니다. `manifest.json`은 생략된 단계와 사유를 기록합니다.

Agent 이벤트는 다음 순서를 사용합니다.

```text
agentCreated → agentToolStart → handoffProduced → agentToolDone
실패: agentToolFailed → supervisorDecision
종료: finalStatus
```

이벤트에는 API 키, 민원 원문, 웹 페이지 본문, 전체 LLM 응답을 넣지 않습니다.

---

## 7. 검색과 근거 검증

법령·유사 사례 검색은 다음 순서로 동작합니다.

```text
OpenRouter openrouter:web_search (Exa)
  → 실패 또는 citation 없음
DuckDuckGo fallback
  → bot challenge 또는 결과 없음
EvidencePackage.decision = ESCALATE
```

- OpenRouter가 반환한 표준 `url_citation`만 근거 후보로 수집합니다.
- DuckDuckGo의 HTTP 202/bot challenge는 실제 검색 결과 0건과 구분합니다.
- 공식 기관·법령 도메인을 우선 분류합니다.
- URL 접근을 확인하지 못한 근거는 `verified: false`이며 핵심 주장에 사용할 수 없습니다.
- 검색 페이지의 지시문은 명령이 아니라 비신뢰 외부 데이터로 취급합니다.
- 모든 검색 공급자가 실패하면 근거 없이 초안을 작성하지 않습니다.

---

## 8. Pixel Office

Streamlit 화면의 HTML Canvas 오피스는 장식용 애니메이션이 아니라 Supervisor Runtime의 상태 시각화입니다.

| 공간 | 표시되는 업무 |
|---|---|
| 접수 데스크 | 입력 정규화와 개인정보 위험 확인 |
| 분류 셀 | 쟁점·관할 병렬 분석과 취합 |
| 법령 자료실 | 법령 검색과 근거 검증 |
| 사례 검색실 | 유사 사례 검색 |
| 작성석 | 최초 작성과 수정 |
| 검증실 | 인용·개인정보·문체 교차 감사 |
| Supervisor 데스크 | 상태 결정과 최종 출판 |
| 회의실 | 수정·상충 검토 |
| 사람 검토 창구 | 자동 처리 중단과 담당자 확인 전환 |

Agent의 이동, 타이핑, 자료 열람, 문서 전달, 수정 반송, 오류와 종료 상태는 실제 Runtime 이벤트를 반영합니다. Canvas는 이벤트를 소비할 뿐 비즈니스 판정을 생성하지 않습니다.

---

## 9. 설치와 실행

### 요구사항

- Python 3.11 이상 권장
- OpenRouter API Key
- 인터넷 연결
- Streamlit, pandas, openpyxl, requests, BeautifulSoup

### 설치

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

### API 키 설정

앱 사이드바에 직접 입력하거나, 커밋되지 않는 `.streamlit/secrets.toml`에 저장합니다.

```toml
OPENROUTER_API_KEY = "sk-or-..."
```

기본 모델은 모든 역할군에서 DeepSeek V3(`deepseek/deepseek-chat`)입니다. 사이드바의 역할군 설정 또는 고급 Agent별 override에서 다른 OpenRouter 모델로 변경할 수 있습니다.

### 앱 실행

```bash
streamlit run app.py
```

기본 접속 주소는 `http://localhost:8501`입니다. 해당 포트를 다른 프로세스가 사용 중이면 Streamlit이 다음 포트를 선택할 수 있습니다.

---

## 10. 간단한 사용 예시

### 예시 A: 포함된 Excel 샘플 사용

1. 앱 왼쪽에서 OpenRouter API Key를 입력합니다.
2. `엑셀 샘플`에서 민원을 선택합니다.
3. `선택 민원 불러오기`를 누릅니다.
4. 제목과 본문을 확인합니다.
5. `Supervisor 실행`을 누릅니다.
6. Pixel Runtime에서 Agent의 이동과 handoff를 확인합니다.
7. 최종 판정과 검증 보고서를 확인합니다.
8. 필요하면 `FinalOutput + trace 다운로드`로 결과를 저장합니다.

### 예시 B: 직접 민원 입력

```text
제목: 공원 야간 조명 고장 및 안전 조치 요청

본문:
주민들이 이용하는 공원 산책로의 조명 여러 개가 꺼져 있어
야간 통행 시 안전사고가 우려됩니다. 담당 부서와 조치 절차,
예상 처리 과정에 대해 안내해 주시기 바랍니다.
```

예상 흐름은 다음과 같습니다.

```text
접수 CONTINUE
→ 시설·안전 관련 쟁점과 관할 후보 분류
→ 공식 조례·기관 안내·유사 사례 검색
→ 검증된 근거가 있으면 답변 초안 작성
→ 인용 감사 + 개인정보·문체 감사
→ PASS면 DRAFT_APPROVED
→ 근거 부족/관할 불명확이면 HUMAN_REVIEW_REQUIRED
```

`DRAFT_APPROVED`도 실제 발송 답변이 아니라 담당자 검토 전 초안입니다.

---

## 11. 프로젝트 구조

```text
.
├── app.py                         # Streamlit UI + Pixel Office
├── complaint_agents.py            # 12-Agent 파이프라인, 계약, 상태, trace
├── requirements.txt
├── assets/pixel_office/            # 배경·캐릭터·가구 PNG
├── tests/                          # 계약·파이프라인·검색·안전·UI 테스트
├── .harness/                       # 공용 하네스 SSOT
├── .agents/                        # Codex 스킬 어댑터
├── .claude/                        # Claude Code Agent/스킬 어댑터
├── docs/
│   ├── HARNESS.md
│   └── CODEX_CLAUDE_HANDOFF.md
├── plan/CODEX_PLAN.md              # Codex 고도화 계획
├── scripts/validate_harness.sh
├── _workspace/                     # 실행 trace와 도구 간 인계 산출물
└── minwon_multiagent/              # 패키지형 참고 구현
```

루트 `app.py`와 `complaint_agents.py`가 메인 구현입니다. `minwon_multiagent/`는 참고 구현이므로 명시적인 요청이나 공통 결함 사유 없이 양쪽을 동시에 수정하지 않습니다.

---

## 12. 안전 경계와 실패 처리

- `PASS` 없는 초안을 `DRAFT_APPROVED`로 출력하지 않습니다.
- 검색 Agent가 제공하지 않은 법령·조문을 Writer가 새로 만들 수 없습니다.
- BLOCKER가 하나라도 있거나 근거·관할·개인정보 HIGH finding이 있으면 PASS할 수 없습니다.
- 고위험 개인정보, 불명확한 관할, 상충 근거, 위해 가능성은 사람 검토로 보냅니다.
- 네트워크 오류와 JSON/schema 불일치는 1회 재시도 후 ESCALATE합니다.
- 최종 출력 생성이 실패하면 초안을 그대로 노출하지 않습니다.
- 앱은 실제 행정 처분, 자동 승인, 답변 자동 발송을 수행하지 않습니다.

---

## 13. 테스트와 품질 게이트

```bash
# 하네스 필수 파일·역할·계약 확인
bash scripts/validate_harness.sh

# Python 구문 확인
python -m compileall app.py complaint_agents.py minwon_multiagent tests

# 자동 테스트
pytest -q

# 비밀정보 패턴 검토
rg -n 'sk-or-|Authorization: Bearer|api[_-]?key\s*=' .

# 수동 UI 검증
streamlit run app.py
```

자동 테스트는 OpenRouter 호출과 검색을 기본적으로 mock 처리합니다. 실 API 검증은 명시적으로 실행하며, 실제 API 키나 민원 개인정보를 fixture·로그·커밋에 남기지 않습니다.

수동 UI 검증에서는 최소한 다음 시나리오를 확인합니다.

- 정상 승인
- 수정 후 승인
- 근거 부족으로 사람 검토 전환
- 입력 거절
- 검색 공급자 실패
- 검증 미실행 `NOT RUN` 표시
- 재실행 시 trace 격리
- 좁은 화면과 asset 누락 fallback

---

## 14. 알려진 제약

- LLM과 외부 검색 결과는 비결정적이며 동일 입력도 세부 결과가 달라질 수 있습니다.
- OpenRouter 웹검색은 모델 토큰 비용 외에 별도 검색 비용이 발생할 수 있습니다.
- 외부 검색 공급자와 정부 사이트의 접근 정책에 따라 일시적인 검색 실패가 발생할 수 있습니다.
- 앱은 공개 웹 근거만 사용하며 정부 내부 문서나 행정 시스템에 접근하지 않습니다.
- 법령 URL 접근 가능 여부를 확인하더라도 법률적 해석의 최종 책임은 담당자에게 있습니다.
- pyarrow 25.x가 일부 macOS 환경에서 mimalloc 관련 충돌을 일으킬 수 있어 앱과 테스트가 `ARROW_DEFAULT_MEMORY_POOL=system`을 설정합니다.

---

## 15. 하네스 변경 원칙

하네스를 확장할 때는 다음 순서를 지킵니다.

1. `.harness/references/business-workflow.md`에서 업무 흐름과 상태 전이를 먼저 변경합니다.
2. `.harness/references/data-contracts.md`에서 생산자–소비자 계약을 변경합니다.
3. `.harness/agents/`의 공용 역할 경계를 갱신합니다.
4. `.harness/skills/minwon-orchestrator/SKILL.md`의 실행 SOP를 갱신합니다.
5. `.agents/`, `.claude/` 어댑터가 공용 원본을 계속 가리키는지 확인합니다.
6. 제품 코드, 테스트, 문서를 같은 계약에 맞춰 변경합니다.
7. `scripts/validate_harness.sh`와 전체 테스트를 실행합니다.

이 순서는 규칙이 여러 파일에 복제되어 서로 어긋나는 것을 막기 위한 것입니다.

---

## 16. 참고한 하네스 README

이 README의 설명 구조는 다음 공개 프로젝트가 강조하는 역할 분리, 파일 기반 handoff, SSOT, 생성–검증 루프, 산출물 중심 문서화 방식을 참고했습니다.

- [wookiesong/Policy_makers_harness](https://github.com/wookiesong/Policy_makers_harness)
- [bcchung81/report-harness](https://github.com/bcchung81/report-harness)

구체적인 업무 역할, 데이터 계약, 상태 전이와 구현 내용은 이 저장소의 `.harness/`와 실제 제품 코드를 기준으로 작성했습니다.
