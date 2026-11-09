"""An app wired to fakes: no network, no API keys, no model download."""

from pathlib import Path

import pytest
from api_helpers import ClientFactory, StubRetriever, make_passage
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scripted_llm import FakeLLM

from novabridge_qa.api.deps import get_qa_service
from novabridge_qa.config import Settings
from novabridge_qa.main import create_app
from novabridge_qa.qa.service import GroundedQueryEngine


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return create_app(Settings(_env_file=None, data_dir=tmp_path))


@pytest.fixture
def retriever() -> StubRetriever:
    return StubRetriever([make_passage(1), make_passage(2), make_passage(3)])


@pytest.fixture
def make_client(app: FastAPI, retriever: StubRetriever) -> ClientFactory:
    """Return a client whose LLM replies with the given script."""

    def factory(*replies: str | Exception) -> TestClient:
        service = GroundedQueryEngine(
            retriever=retriever,
            llm=FakeLLM(list(replies)),
            top_k=6,
            min_relevance=0.5,
            max_tokens=100,
        )
        app.dependency_overrides[get_qa_service] = lambda: service
        # False, so a crash shows up as the 500 a real client would get.
        return TestClient(app, raise_server_exceptions=False)

    return factory
