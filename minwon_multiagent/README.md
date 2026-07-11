# 📮 민원 초안 생성 Multi-Agent

공공기관 민원에 대한 **답변 초안**을 4단계 에이전트 파이프라인으로 자동 생성합니다.
기본값은 OpenRouter의 DeepSeek V3(`deepseek/deepseek-chat`)이며, 필요하면 단계별로 다른 모델을 지정할 수 있습니다. 진행 과정은 Streamlit UI에서 실시간으로 확인할 수 있습니다.

## 🧩 파이프라인 구조

| 단계 | 에이전트 | 역할 | 기본 모델 | 핸드오프(다음 단계로 전달) |
|------|----------|------|-----------|----------------------------|
| 1 | **분류_Agent** | 담당 부서·민원 유형 판별 | `deepseek/deepseek-chat` | 민원 원문 + 부서 + 유형 |
| 2 | **검색_Agent** | 관련 법령·과거 답변 웹검색 | `deepseek/deepseek-chat` | 법령근거 + 과거 답변 요약 |
| 3 | **작성_Agent** | 근거 기반 답변 초안 작성 | `deepseek/deepseek-chat` | 근거 인용 포함 초안 |
| 4 | **검수_Agent** | 말투·정확성·근거 점검 + 수정안 | `deepseek/deepseek-chat` | 최종 수정 초안 |

> 모델 슬러그는 사이드바에서 자유롭게 교체할 수 있습니다. OpenRouter에 존재하지 않는
> 슬러그라면 [openrouter.ai/models](https://openrouter.ai/models)에서 실제 모델로 바꿔 입력하세요.

## 📁 구조

```
minwon_multiagent/
├── app.py                # Streamlit UI + 파이프라인 오케스트레이션
├── core/
│   ├── config.py         # 엔드포인트·기본 모델·택소노미
│   ├── models.py         # 핸드오프 불변 데이터 구조(dataclass)
│   └── openrouter.py     # OpenRouter 클라이언트(웹검색 플러그인)
├── agents/
│   ├── classifier.py     # 1단계
│   ├── searcher.py       # 2단계 (웹검색)
│   ├── writer.py         # 3단계
│   └── reviewer.py       # 4단계
├── data/loader.py        # 민원 엑셀 로더
└── requirements.txt
```

## 🚀 실행

```bash
cd minwon_multiagent
pip install -r requirements.txt
streamlit run app.py
```

1. 브라우저가 열리면 사이드바에 **OpenRouter API Key** 입력
2. `샘플 민원 선택`(상위 폴더의 엑셀 자동 로드) 또는 `직접 입력`에서 민원 지정
3. **🚀 멀티에이전트 실행** 클릭 → 1~4단계 진행과정과 핸드오프가 순서대로 표시
4. 완료 후 **최종 답변 초안** 확인 및 `.txt` 다운로드

## 🔍 진행 과정 표시

- 각 단계는 `st.status` 카드로 실행 → 완료(✓)/실패(❌)를 실시간 표시
- 상단 진행바(0→25→50→75→100%)로 전체 단계 추적
- 단계마다 **📦 핸드오프** 박스에서 "다음 에이전트로 넘기는 실제 페이로드"를 그대로 확인
- 검색_Agent는 웹검색 출처(🔗)를 링크로 표시

## ⚠️ 참고

- OpenRouter 웹검색은 `web` 플러그인(`plugins=[{"id": "web"}]`)으로 동작하며 별도 검색 비용이 발생할 수 있습니다.
- 생성된 답변은 **초안**이며, 실제 회신 전 담당자 검토가 필요합니다.
