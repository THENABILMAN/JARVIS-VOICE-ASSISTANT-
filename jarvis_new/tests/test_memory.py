import pytest

from memory import Mem0Error, MemoryService


class FakeMemoryClient:
    def __init__(self) -> None:
        self.added: list[tuple[object, str]] = []
        self.queries: list[tuple[str, str]] = []

    def add(self, messages: object, *, user_id: str) -> dict[str, str]:
        self.added.append((messages, user_id))
        return {"status": "success"}

    def search(self, query: str, *, user_id: str) -> dict[str, list[dict[str, str]]]:
        self.queries.append((query, user_id))
        memory = (
            "The user's name is Nabil."
            if "name" in query
            else "The user prefers Bengali music."
        )
        return {"results": [{"memory": memory}]}


@pytest.fixture
def configured_memory(monkeypatch: pytest.MonkeyPatch) -> tuple[MemoryService, FakeMemoryClient]:
    monkeypatch.setenv("MEM0_API_KEY", "test-key")
    monkeypatch.setenv("MEM0_USER_ID", "test-user")
    service = MemoryService()
    client = FakeMemoryClient()
    service._client = client
    return service, client


def test_remember_uses_configured_user(configured_memory) -> None:
    service, client = configured_memory

    assert service.remember("I prefer Bengali music.") == "{'status': 'success'}"
    assert client.added == [
        ([{"role": "user", "content": "I prefer Bengali music."}], "test-user")
    ]


def test_recall_summarizes_mem0_results(configured_memory) -> None:
    service, client = configured_memory

    assert service.summarize(service.recall("music preference")) == (
        "The user prefers Bengali music."
    )
    assert client.queries == [("music preference", "test-user")]


def test_recall_for_session_targets_identity_and_preferences(configured_memory) -> None:
    service, client = configured_memory

    assert service.recall_for_session() == (
        "The user's name is Nabil. The user prefers Bengali music."
    )
    assert [query for query, _ in client.queries] == [
        "the user's name and identity",
        "the user's preferences and important facts",
    ]


def test_missing_configuration_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delenv("MEM0_USER_ID", raising=False)

    with pytest.raises(Mem0Error, match="MEM0_API_KEY and MEM0_USER_ID"):
        MemoryService().recall("preferences")
