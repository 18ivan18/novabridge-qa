import math

from novabridge_qa.retrieval.embedder import FakeEmbedder


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_embedder_is_deterministic_and_normalized() -> None:
    embedder = FakeEmbedder()

    vector = embedder.embed_query("ACME sells anvils")

    assert vector == FakeEmbedder().embed_documents(["ACME sells anvils"])[0]
    assert len(vector) == embedder.dimension
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0)


def test_fake_embedder_scores_shared_words_higher() -> None:
    embedder = FakeEmbedder()
    query = embedder.embed_query("anvil revenue")

    related = embedder.embed_query("revenue from anvil sales")
    unrelated = embedder.embed_query("the warehouse roof leaks")

    assert cosine(query, related) > cosine(query, unrelated)


def test_fake_embedder_handles_empty_text() -> None:
    assert FakeEmbedder(dimension=4).embed_query("") == [0.0] * 4
