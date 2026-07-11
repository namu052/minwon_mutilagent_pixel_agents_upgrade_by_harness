# minwon_mutilagent_pixel_agents 공용 하네스

이 폴더는 [`namu052/minwon_mutilagent_pixel_agents`](https://github.com/namu052/minwon_mutilagent_pixel_agents)에서 **AI Agent가 민원 업무를 입력 → 처리 → 검증 → 출력 흐름으로 수행**하도록 정의한 Codex·Claude Code 공용 하네스다.

## 핵심 업무 구조

```text
입력: 민원 접수·정규화
  → 처리: 분류 → 공식 근거 검색 → 답변 작성
  → 검증: 독립 검수 → 수정(최대 2회) 또는 사람 검토
  → 출력: 승인된 초안/출처/검증 결과/실행 trace
```

`PASS` 판정이 없는 초안은 승인 출력할 수 없다. 근거·관할·개인정보가 불확실하거나 두 번의 수정 후에도 실패하면 사람 검토로 전환한다.

## 설계

- 공용 원본: `.harness/` — 민원 업무 Agent 역할, Supervisor, 데이터 계약의 단일 진실 공급원
- Codex 진입점: `AGENTS.md`
- Claude Code 진입점: `CLAUDE.md`, `.claude/agents/`, `.claude/skills/`
- Codex 스킬 검색 호환: `.agents/skills/`
- 중간 산출물: `_workspace/` (실행 시 생성)

Claude/Codex 어댑터 파일은 공용 원본을 가리키는 얇은 포인터다. 규칙을 바꿀 때는 먼저 `.harness/`를 수정하고 어댑터와의 일치 여부를 점검한다.

## 적용 방법

이 폴더의 **내용 전체**를 대상 저장소 루트에 복사한다. 기존 `AGENTS.md` 또는 `CLAUDE.md`가 있다면 덮어쓰지 말고 이 파일의 하네스 포인터 섹션만 병합한다.

```bash
cp -R harness_For_minwon_mutilagent_pixel_agents/. /path/to/minwon_mutilagent_pixel_agents/
```

## 사용 예

- `민원 앱의 OpenRouter 오류를 진단하고 수정해줘`
- `분류→검색→작성→검수 핸드오프를 변경해줘`
- `Pixel Runtime UI를 개선하고 회귀 테스트해줘`
- `두 구현의 중복과 드리프트를 점검해줘`

에이전트 도구가 없는 세션에서는 오케스트레이터가 역할을 순차적으로 수행한다. 도구 이름이나 모델 이름은 런타임마다 다르므로 하네스는 특정 API를 강제하지 않는다.

## 업무 Agent

- `intake-agent`: 입력 정규화 및 개인정보 위험 판정
- `classifier-agent`: 담당 부서·유형·쟁점 분류
- `evidence-search-agent`: 공식 법령·사례 검색과 교차검증
- `response-writer-agent`: 근거 기반 답변 작성
- `response-validator-agent`: 독립 검증과 PASS/REVISE/ESCALATE/REJECT 판정
- `output-publisher-agent`: 판정에 맞는 안전한 최종 출력

기존 `.harness/agents/system-architect.md` 등의 파일은 앱을 고도화할 때 사용하는 개발 보조 역할이며, 위 업무 Agent 흐름을 대체하지 않는다.

## 프로젝트 기준선

- 메인 제출 앱: `app.py`, `complaint_agents.py`
- 참고 패키지 구현: `minwon_multiagent/`
- 실행: `pip install -r requirements.txt && streamlit run app.py`
- 외부 서비스: OpenRouter Chat Completions, 선택적 웹검색
- 민감 영역: 민원 원문, 법령/행정 근거, API 키, 외부 URL 콘텐츠
