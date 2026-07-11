"""전역 설정: OpenRouter 엔드포인트, 단계별 기본 모델, 분류 택소노미."""

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL}/chat/completions"
REQUEST_TIMEOUT_SEC = 120

# 각 단계(Agent)별 기본 모델.
# 사용자가 UI에서 자유롭게 덮어쓸 수 있으므로, OpenRouter에 존재하지 않는
# 슬러그라면 UI에서 실제 모델로 교체하면 된다.
DEFAULT_MODELS = {
    "classifier": "deepseek/deepseek-chat",
    "searcher": "deepseek/deepseek-chat",
    "writer": "deepseek/deepseek-chat",
    "reviewer": "deepseek/deepseek-chat",
}

# 분류_Agent가 참고할 부서/유형 후보 (강제값이 아닌 힌트).
DEPARTMENT_HINTS = [
    "인사혁신처",
    "행정안전부",
    "여성가족부",
    "국토교통부",
    "교육부",
    "지방자치단체(상수도·시설 등)",
    "기타/판별불가",
]

COMPLAINT_TYPE_HINTS = [
    "법령·제도 해석 질의",
    "단순 정보 문의",
    "민원처리 지연·불만·항의",
    "정책·인사 제안",
    "정보공개 요청",
    "칭찬·기타",
]

# OpenRouter 랭킹/식별용 헤더 (선택값).
APP_REFERER = "https://localhost/minwon-multiagent"
APP_TITLE = "민원 초안 생성 Multi-Agent"
