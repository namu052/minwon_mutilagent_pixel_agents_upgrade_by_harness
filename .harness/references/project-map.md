# 프로젝트 맵

## 제품 흐름

`민원 입력 → 분류 → 법령·유사사례 검색 → 답변 작성 → 검수 → 최종 초안/trace/Pixel Runtime 표시`

## 구현 경계

| 영역 | 루트 구현 | 패키지형 참고 구현 |
|---|---|---|
| UI/조율 | `app.py` | `minwon_multiagent/app.py` |
| 에이전트/런타임 | `complaint_agents.py` | `minwon_multiagent/agents/` |
| 모델/설정/HTTP | `complaint_agents.py` 내부 | `minwon_multiagent/core/` |
| 입력 로더 | `app.py` | `minwon_multiagent/data/loader.py` |

루트 구현이 README상 과제 제출용 메인 앱이다. 패키지형 구현은 참고 구현이므로 요청 없이 두 구현을 동시에 고치지 않는다. 공통 결함이면 각각의 영향과 동기화 필요성을 보고한다.

## 주요 계약

1. 각 단계의 출력이 다음 단계 입력과 일치해야 한다.
2. OpenRouter 응답은 실패·빈 choices·비JSON·citation 부재를 견뎌야 한다.
3. 웹검색 결과는 신뢰된 사실로 자동 승격하지 않는다.
4. 최종 결과는 초안임을 유지하고 담당자 검토 필요성을 숨기지 않는다.
5. Pixel 상태와 이벤트는 실제 Supervisor 실행 상태를 반영해야 한다.
6. API 키와 민원 원문을 로그, 예외, 테스트 fixture, 커밋에 남기지 않는다.

## 런타임 중립 원칙

- 역할은 특정 모델명(`opus` 등)에 의존하지 않는다.
- 오케스트레이션은 `spawn/subagent/team` 같은 기능이 있으면 활용하고 없으면 순차 실행한다.
- 에이전트 간 전달은 `_workspace/{phase}_{agent}_{artifact}.md` 파일을 공통 형식으로 사용한다.
- 모든 에이전트가 같은 작업 트리에서 편집할 때 담당 파일을 먼저 선언하고 타인의 변경을 덮어쓰지 않는다.

