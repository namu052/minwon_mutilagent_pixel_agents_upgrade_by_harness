# Claude Code project instructions

## 공용 하네스: 민원 Multi-Agent Pixel 앱

민원 처리 또는 그 구조의 구현·리뷰·테스트에는 `minwon-orchestrator` 스킬을 사용하라. 실제 업무 Agent의 입력 → 처리 → 검증 → 출력 흐름이 최우선이다. 공용 원본은 `.harness/skills/minwon-orchestrator/SKILL.md`이며 `.claude/skills/`는 런타임용 포인터다.

에이전트 역할의 단일 진실 공급원은 `.harness/agents/`다. 팀 기능을 사용할 수 없으면 동일한 역할과 품질 게이트를 순차적으로 수행하라.

## Claude Code 담당 범위

Claude Code는 Codex가 작성한 `_workspace/CODEX_PLAN.md`를 구현하는 역할이다.

1. 구현 전에 계획, 현재 코드, `git status`를 대조한다.
2. 불명확하거나 코드와 충돌하는 계획은 임의 확장하지 말고 `_workspace/CLAUDE_IMPLEMENTATION.md`에 차이와 판단을 기록한다.
3. 계획의 작업 순서와 데이터 계약을 따라 제품 코드를 수정한다.
4. `.harness/references/quality-gates.md`와 계획의 테스트를 실행한다.
5. 구현 결과, 변경 파일, 검증 결과, 미완료 사항을 `_workspace/CLAUDE_IMPLEMENTATION.md`에 기록한다.

인계 형식은 `docs/CODEX_CLAUDE_HANDOFF.md`를 따른다.

## 변경 이력

| 날짜 | 변경 내용 | 대상 | 사유 |
|---|---|---|---|
| 2026-07-11 | 초기 공용 하네스 구성 | 전체 | Codex·Claude Code 교차 운영 |
