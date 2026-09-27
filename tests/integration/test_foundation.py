from fastapi.testclient import TestClient

from app.config import Settings
from app.graph.graph import build_foundation_graph
from app.llm.router import LLMRouter
from app.main import create_app


def test_api_graph_success(providers):
    application = create_app(Settings(_env_file=None))
    with TestClient(application) as client:
        application.state.graph = build_foundation_graph(LLMRouter(*providers))
        assert client.get("/health").json() == {"status": "ok"}
        response = client.post("/api/v1/foundation/check", json={"prompt": "check"})
        assert response.status_code == 200
        assert response.json()["result"] == {"message": "primary"}
        assert response.json()["research_run_id"]
        assert client.post("/api/v1/foundation/check", json={"prompt": ""}).status_code == 422


def test_api_provider_failure_is_sanitized(providers):
    for provider in providers:
        provider.invoke.side_effect = RuntimeError("sensitive provider details")
    application = create_app(Settings(_env_file=None))
    with TestClient(application) as client:
        application.state.graph = build_foundation_graph(LLMRouter(*providers))
        response = client.post("/api/v1/foundation/check", json={"prompt": "check"})
        assert response.status_code == 502
        assert "sensitive" not in response.text
