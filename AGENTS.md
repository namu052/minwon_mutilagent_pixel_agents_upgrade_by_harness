# Codex project instructions

## 공용 하네스: 민원 Multi-Agent Pixel 앱

민원 처리 또는 그 구조의 구현·리뷰·테스트에는 `.harness/skills/minwon-orchestrator/SKILL.md`를 읽고 따른다. 핵심은 실제 업무 Agent의 입력 → 처리 → 검증 → 출력 흐름이며, 개발 편의 때문에 이 흐름이나 검증 단계를 생략하지 않는다.

업무 역할은 `.harness/agents/`, 데이터 계약과 상태 전이는 `.harness/references/business-workflow.md`, `.harness/references/data-contracts.md`가 기준이다. 병렬 에이전트 기능이 없으면 같은 역할을 순차 실행한다.

변경 전에는 루트 구현(`app.py`, `complaint_agents.py`)과 패키지 구현(`minwon_multiagent/`) 중 어느 것이 변경 대상인지 명시한다. 양쪽을 무조건 동기화하지 않는다.

## Codex 담당 범위

Codex는 고도화 계획을 작성하는 역할이다. 사용자가 별도로 구현을 요청하지 않는 한 제품 코드를 수정하지 않는다.

1. 저장소와 업무 하네스를 분석한다.
2. `.harness/references/business-workflow.md`, `data-contracts.md`를 기준으로 gap을 찾는다.
3. 구현 가능한 계획을 `_workspace/CODEX_PLAN.md`에 작성한다.
4. 계획에는 파일·심볼 단위 변경, 데이터 계약, 상태 전이, 테스트, 완료 조건을 포함한다.
5. Claude Code가 판단 없이 착수할 수 있도록 의사결정과 비목표를 명시한다.

인계 형식은 `docs/CODEX_CLAUDE_HANDOFF.md`를 따른다.

## 변경 이력

| 날짜 | 변경 내용 | 대상 | 사유 |
|---|---|---|---|
| 2026-07-11 | 초기 공용 하네스 구성 | 전체 | Codex·Claude Code 교차 운영 |
