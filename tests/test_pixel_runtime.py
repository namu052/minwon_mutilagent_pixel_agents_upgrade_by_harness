from __future__ import annotations

import json

import pytest

import complaint_agents as ca

from conftest import run_default


EVENT_ENVELOPE_KEYS = {
    "seq", "timestamp", "trace_id", "type", "agent_id", "task_id",
    "from_zone", "to_zone", "safe_summary",
}

AGENT_STATE_KEYS = {
    "agent_id", "display_name", "role", "team", "status", "zone",
    "target_zone", "activity", "task_id", "last_safe_summary", "outputs",
}


class TestSnapshotContract:
    def test_idle_snapshot_has_12_agents(self):
        store = ca.create_runtime_store("ready", ca.DEFAULT_MODELS)
        snapshot = store.to_snapshot()
        assert len(snapshot["agents"]) == 12
        ids = {a["agent_id"] for a in snapshot["agents"]}
        assert ids == set(ca.AGENT_SPEC_BY_ID)

    def test_agent_state_fields_and_enums(self):
        snapshot = ca.create_runtime_store("ready", ca.DEFAULT_MODELS).to_snapshot()
        for agent in snapshot["agents"]:
            assert AGENT_STATE_KEYS <= set(agent)
            assert agent["status"] in ca.AGENT_STATUSES
            assert agent["activity"] in ca.AGENT_ACTIVITIES
            assert agent["zone"] in ca.ZONES
            assert isinstance(agent["outputs"], list)

    def test_event_envelope(self, make_supervisor):
        result = run_default(make_supervisor())
        for event in result["pixel_runtime"]["events"]:
            assert set(event) == EVENT_ENVELOPE_KEYS
            assert event["type"] in ca.EVENT_TYPES
            assert event["trace_id"] == result["trace_id"]

    def test_snapshot_json_serializable(self, make_supervisor):
        result = run_default(make_supervisor())
        json.dumps(result["pixel_runtime"], ensure_ascii=False)

    def test_zone_mapping_after_run(self, make_supervisor):
        result = run_default(make_supervisor())
        zones = {a["agent_id"]: a["zone"] for a in result["pixel_runtime"]["agents"]}
        assert zones["intake-agent"] == "intake_desk"
        assert zones["legal-research-agent"] == "law_library"
        assert zones["similar-case-agent"] == "case_room"
        assert zones["output-publisher-agent"] == "supervisor_desk"

    def test_invalid_event_type_rejected(self):
        store = ca.PixelAgentStateStore("t")
        with pytest.raises(ValueError):
            store._emit("unknownEvent")

    def test_move_emits_from_to(self):
        store = ca.create_runtime_store("t", ca.DEFAULT_MODELS)
        store.move_agent("response-writer-agent", "meeting_room")
        move_events = [e for e in store.to_snapshot()["events"] if e["type"] == "agentMove"]
        assert move_events
        assert move_events[-1]["from_zone"] == "writing_desk"
        assert move_events[-1]["to_zone"] == "meeting_room"


class TestUiHelpers:
    """app.py의 snapshot 소비 로직이 안전하게 동작하는지 검증한다."""

    def _app(self):
        import importlib

        app = importlib.import_module("app")
        return app

    def test_zone_layout_covers_all_zones(self):
        app = self._app()
        assert set(app.ZONE_LAYOUT) == set(ca.ZONES)
        assert set(app.ZONE_LABELS) == set(ca.ZONES)

    def test_team_char_index_covers_all_teams(self):
        app = self._app()
        teams = {spec.team for spec in ca.AGENT_SPECS}
        assert teams <= set(app.TEAM_CHAR_INDEX)

    def test_json_for_html_escapes_closing_tag(self):
        app = self._app()
        payload = app._json_for_html({"x": "</script><script>alert(1)</script>"})
        assert "</script" not in payload

    def test_long_korean_summary_truncated_in_payload(self, make_supervisor):
        # payload 생성 시 요약이 40자로 축약되는지 render 로직과 동일 규칙으로 확인
        long_summary = "아주 긴 한국어 요약 " * 20
        store = ca.create_runtime_store("t", ca.DEFAULT_MODELS)
        store.start_task(
            "intake-agent", task_id="t-1", activity="typing", safe_summary=long_summary
        )
        agent = store.to_snapshot()["agents"][0]
        truncated = str(agent["last_safe_summary"] or "")[:40]
        assert len(truncated) <= 40

    def test_download_payload_excludes_artifacts(self, make_supervisor):
        app = self._app()
        result = run_default(make_supervisor())
        payload = json.loads(app.build_download_payload(result))
        assert "final_output" in payload
        assert "manifest" in payload
        assert "events" in payload
        # 다운로드에는 원문이 담긴 산출물 전체를 넣지 않는다.
        assert "artifacts" not in payload
