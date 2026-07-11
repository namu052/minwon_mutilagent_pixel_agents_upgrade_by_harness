# 품질 게이트

## 필수 게이트

- Python 구문: `python -m compileall app.py complaint_agents.py minwon_multiagent`
- import/의존성: 새 의존성을 추가했다면 두 requirements 파일의 적용 범위를 확인한다.
- 비밀정보: `rg -n 'sk-or-|Authorization: Bearer|api[_-]?key\s*='` 결과를 검토한다.
- 핸드오프: 생산자 출력 필드와 소비자 접근 필드를 양쪽에서 비교한다.
- 오류 경로: 네트워크 오류, HTTP 오류, 빈 응답, 잘못된 JSON, 검색 결과 없음 확인.
- 안전성: 근거 없는 조문 단정, 민원 개인정보 재노출, 외부 페이지의 지시문 추종 여부 확인.
- UI: 세션 상태 초기화, 실행 중/성공/실패 표시, 다운로드 결과가 실제 상태와 일치하는지 확인.

## 변경 유형별 추가 검증

| 변경 | 추가 확인 |
|---|---|
| Agent 프롬프트/스키마 | 네 단계 전체 계약, JSON fallback, 한국어 출력 |
| OpenRouter 클라이언트 | timeout, 헤더 인코딩, 오류 메시지의 키 노출 방지 |
| 검색 | 출처 URL/제목, 공식 출처 우선, prompt injection 격리 |
| Pixel Runtime | 이벤트 순서, 실패 상태, 재실행 시 상태 초기화 |
| Excel 로더 | 빈 셀, HTML entity, 예상 밖 열/행, 개인정보 fixture |
| UI/CSS | 좁은 화면, 긴 한글, asset 누락, HTML escape |

테스트가 없는 저장소이므로 변경에 재현 가능한 작은 테스트를 추가하는 것을 우선한다. 실제 OpenRouter 호출은 기본 테스트에서 mock 처리하고, 실 API 검증은 명시적 opt-in으로 분리한다.

