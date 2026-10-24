from __future__ import annotations

import json

import httpx
import pytest
from prompt_enhance_mcp.server import Backend, create_server, identifier


@pytest.mark.asyncio
async def test_registered_mcp_tools_forward_exact_enhancement_contract():
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/v1/enhance":
            return httpx.Response(200, json={
                "schema_version": 1, "request_id": "req_7", "prompt_revision": 4,
                "type": "autocomplete", "insert_at": 4, "text": " next",
            })
        return httpx.Response(404, json={"error": {"message": "not found"}})

    server = create_server(Backend("http://127.0.0.1:8000", httpx.MockTransport(handler)))
    names = {tool.name for tool in await server.list_tools()}
    assert {"enhance_prompt", "enhancement_sources", "search_knowledge", "read_knowledge",
            "preview_knowledge", "save_knowledge", "open_refinement_panel"} <= names

    result = await server.call_tool("enhance_prompt", {
        "request_id": "req_7", "prompt": "Test", "prompt_revision": 4, "cursor_position": 4,
    })
    assert result is not None
    assert len(captured) == 1
    assert captured[0].method == "POST"
    assert captured[0].url.path == "/v1/enhance"
    assert json.loads(captured[0].content) == {
        "request_id": "req_7", "prompt": "Test", "prompt_revision": 4, "cursor_position": 4,
    }


@pytest.mark.asyncio
async def test_backend_errors_never_echo_upstream_payloads():
    marker = "SECRET_OR_PROMPT_MARKER"
    backend = Backend("http://127.0.0.1:8000", httpx.MockTransport(
        lambda request: httpx.Response(503, text=marker),
    ))
    with pytest.raises(ValueError) as caught:
        await backend.call("POST", "/v1/enhance", json={"prompt": marker})
    assert marker not in str(caught.value)
    assert "503" in str(caught.value)


@pytest.mark.parametrize("value", ["../activity", "a/b", "x?token=secret", "", "has space"])
def test_path_identifiers_are_restricted(value: str):
    with pytest.raises(ValueError):
        identifier(value)


def test_runtime_does_not_log_http_query_values(monkeypatch, caplog):
    import logging

    from prompt_enhance_mcp import server

    monkeypatch.setattr(server.uvicorn, "run", lambda *args, **kwargs: None)
    with caplog.at_level(logging.INFO):
        server.main()
        logging.getLogger("httpx").info("HTTP Request: GET /knowledge?q=PRIVATE_QUERY_MARKER")
        logging.getLogger("httpcore").info("PRIVATE_TRANSPORT_MARKER")
        logging.getLogger("mcp.server").error("PRIVATE_TOOL_ARGUMENT_MARKER")
    assert "PRIVATE_QUERY_MARKER" not in caplog.text
    assert "PRIVATE_TRANSPORT_MARKER" not in caplog.text
    assert "PRIVATE_TOOL_ARGUMENT_MARKER" not in caplog.text
