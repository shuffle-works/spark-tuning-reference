"""Unit tests for scripts.ask.retrieve() with a stubbed model + collection.

No real SentenceTransformer (~420 MB) is loaded and no real ChromaDB is opened:
retrieve() takes injected `model`, `collection`, and `urls`, so the heavy
imports never run. These tests pin the behavior the CLI formatter depends on.
"""
from scripts.ask import retrieve, QuestionResult, Chunk


class FakeEmbeddings(list):
    """Stand-in for the numpy array model.encode() returns."""

    def tolist(self):
        return [list(row) for row in self]


class FakeModel:
    def __init__(self):
        self.calls = []

    def encode(self, questions, normalize_embeddings):
        self.calls.append((list(questions), normalize_embeddings))
        return FakeEmbeddings([[0.0, 0.0, 0.0] for _ in questions])


class FakeCollection:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def query(self, query_embeddings, n_results, where):
        self.calls.append({"n_results": n_results, "where": where})
        return self.result


# Three chunks: a duplicate source_id (rank 1 and 2) then a distinct one, so the
# dedup-in-rank-order behavior is exercised.
FAKE_RESULT = {
    "documents": [["chunk A", "chunk B", "chunk C"]],
    "metadatas": [[
        {"source_id": "spark-tuning", "version_bucket": "3.5",
         "local_path": "references/a.md", "section_path": "Tuning > Shuffle"},
        {"source_id": "spark-tuning", "version_bucket": "3.5",
         "local_path": "references/a.md", "section_path": "Tuning > Memory"},
        {"source_id": "blog-x", "version_bucket": "n/a",
         "local_path": "references/b.md", "section_path": "Intro"},
    ]],
    "distances": [[0.2, 0.5, 1.3]],
}


def _retrieve_one(**kwargs):
    model = FakeModel()
    collection = FakeCollection(FAKE_RESULT)
    results = retrieve(
        ["how to tune shuffle?"],
        model=model,
        collection=collection,
        urls={},
        **kwargs,
    )
    return results, model, collection


def test_returns_one_result_per_question():
    results, _, _ = _retrieve_one()
    assert isinstance(results, list) and len(results) == 1
    assert isinstance(results[0], QuestionResult)
    assert results[0].question == "how to tune shuffle?"


def test_chunks_carry_text_meta_and_relevance():
    results, _, _ = _retrieve_one()
    chunks = results[0].chunks
    assert [c.text for c in chunks] == ["chunk A", "chunk B", "chunk C"]
    assert isinstance(chunks[0], Chunk)
    # relevance = 1 - distance
    assert chunks[0].relevance == 1 - 0.2
    assert chunks[1].relevance == 1 - 0.5
    assert chunks[2].relevance == 1 - 1.3
    # metadata preserved
    assert chunks[0].meta["section_path"] == "Tuning > Shuffle"
    assert chunks[0].source_id == "spark-tuning"
    assert chunks[0].rank == 1 and chunks[2].rank == 3


def test_source_ids_deduped_in_rank_order():
    results, _, _ = _retrieve_one()
    assert results[0].source_ids == ["spark-tuning", "blog-x"]


def test_encode_normalizes_embeddings():
    _, model, _ = _retrieve_one()
    (questions, normalize), = model.calls
    assert normalize is True
    assert questions == ["how to tune shuffle?"]


def test_version_filter_builds_bucket_plus_na_where_clause():
    _, _, collection = _retrieve_one(version="3.5")
    assert collection.calls[0]["where"] == {"version_bucket": {"$in": ["3.5", "n/a"]}}


def test_no_version_means_no_where_clause():
    _, _, collection = _retrieve_one()
    assert collection.calls[0]["where"] is None


def test_k_is_passed_through_as_n_results():
    _, _, collection = _retrieve_one(k=7)
    assert collection.calls[0]["n_results"] == 7


def test_url_resolved_from_urls_map():
    model = FakeModel()
    collection = FakeCollection(FAKE_RESULT)
    urls = {"spark-tuning": "https://example.com/tuning"}
    results = retrieve(["q"], model=model, collection=collection, urls=urls)
    chunks = results[0].chunks
    assert chunks[0].url == "https://example.com/tuning"
    assert chunks[2].url == "n/a"  # blog-x absent -> default
