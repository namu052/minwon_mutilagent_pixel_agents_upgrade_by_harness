from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import complaint_agents as ca

from conftest import run_default

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")


def make_app() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    # 로컬 .streamlit/secrets.toml의 실제 키가 테스트에 유입되어
    # 실 API를 호출하지 않도록 빈 secrets를 명시 주입한다.
    at.secrets["OPENROUTER_API_KEY"] = ""
    return at


class TestAppSmoke:
    def test_initial_render_no_exception(self):
        at = make_app().run()
        assert not at.exception
        assert at.title[0].value == "민원 초안 생성 멀티에이전트 오피스"

    def test_run_without_api_key_shows_error(self):
        at = make_app().run()
        run_buttons = [b for b in at.button if b.label == "Supervisor 실행"]
        assert run_buttons
        run_buttons[0].click().run()
        assert not at.exception
        assert any("API 키" in e.value for e in at.error)

    def test_legacy_session_state_discarded(self):
        at = make_app()
        at.session_state["last_result"] = {"review": {"final_answer": "구버전"}}
        at.run()
        assert not at.exception
        stored = at.session_state["last_result"] if "last_result" in at.session_state else None
        assert stored is None

    def test_result_rendering_with_pipeline_output(self, make_supervisor):
        result = run_default(make_supervisor())
        at = make_app()
        at.session_state["last_result"] = result
        at.run()
        assert not at.exception
        assert any("최종 판정" in s.value for s in at.subheader)

    def test_human_review_result_rendering(self, make_supervisor):
        result = run_default(make_supervisor(), title="", body="")
        assert result["final_output"]["status"] == "INPUT_REJECTED"
        at = make_app()
        at.session_state["last_result"] = result
        at.run()
        assert not at.exception
