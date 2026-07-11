from __future__ import annotations

from unittest.mock import Mock

import pytest

import complaint_agents as ca


def test_openrouter_web_search_extracts_url_citations(monkeypatch):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "검색 결과",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "url": "https://www.law.go.kr/example",
                                "title": "국가공무원법",
                                "content": "육아휴직 관련 조문",
                            },
                        }
                    ],
                }
            }
        ]
    }
    monkeypatch.setattr(ca.requests, "post", lambda *args, **kwargs: response)

    client = ca.OpenRouterClient("sk-or-test")
    results = client.web_search(
        model="deepseek/deepseek-chat",
        query="국가공무원법 육아휴직",
        max_results=5,
    )

    assert results == [
        {
            "title": "국가공무원법",
            "url": "https://www.law.go.kr/example",
            "snippet": "육아휴직 관련 조문",
            "provider": "openrouter-web-search",
        }
    ]


def test_resilient_search_prefers_openrouter(monkeypatch):
    client = Mock()
    client.web_search.return_value = [
        {"title": "공식 근거", "url": "https://law.go.kr/a", "snippet": "근거"}
    ]
    duck = Mock(side_effect=AssertionError("OpenRouter 성공 시 DuckDuckGo를 호출하면 안 됩니다."))
    monkeypatch.setattr(ca, "duckduckgo_search", duck)

    search = ca.build_resilient_search_fn(client, "deepseek/deepseek-chat")
    assert search("질의", max_results=3)[0]["url"] == "https://law.go.kr/a"
    duck.assert_not_called()


def test_resilient_search_falls_back_after_openrouter_error(monkeypatch):
    client = Mock()
    client.web_search.side_effect = ca.OpenRouterError("일시 오류")
    duck_results = [{"title": "대체 결과", "url": "https://example.com", "snippet": ""}]
    monkeypatch.setattr(ca, "duckduckgo_search", Mock(return_value=duck_results))

    search = ca.build_resilient_search_fn(client, "deepseek/deepseek-chat")
    assert search("질의", max_results=3) == duck_results


def test_duckduckgo_challenge_is_not_treated_as_empty_results(monkeypatch):
    response = Mock()
    response.status_code = 202
    response.text = "<html><title>DuckDuckGo</title><p>anomaly challenge for bots</p></html>"
    response.apparent_encoding = "utf-8"
    response.encoding = "utf-8"
    response.raise_for_status.return_value = None
    monkeypatch.setattr(ca.requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(ca.SearchProviderBlocked):
        ca.duckduckgo_search("질의")


def test_resilient_search_returns_empty_when_all_providers_unavailable(monkeypatch):
    client = Mock()
    client.web_search.return_value = []
    monkeypatch.setattr(
        ca,
        "duckduckgo_search",
        Mock(side_effect=ca.SearchProviderBlocked("challenge")),
    )

    search = ca.build_resilient_search_fn(client, "deepseek/deepseek-chat")
    assert search("질의", max_results=3) == []
