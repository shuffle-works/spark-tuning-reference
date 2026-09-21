"""Unit tests for scripts.mcp_server's ask_spark_docs tool.

_resources() is monkeypatched to return injected fakes, mirroring
test_retrieve.py's approach: no real SentenceTransformer (~420 MB) or
ChromaDB collection is loaded.
"""
import asyncio

from scripts import mcp_server


class FakeEmbeddings(list):
    """Stand-in for the numpy array model.encode() returns."""

    def tolist(self):
        return [list(row) for row in self]


class FakeModel:
    def encode(self, questions, normalize_embeddings):
        return FakeEmbeddings([[0.0, 0.0, 0.0] for _ in questions])


class FakeCollection:
    def __init__(self, result):
        self.result = result

    def query(self, query_embeddings, n_results, where):
        return self.result


FAKE_RESULT = {
    "documents": [["chunk A", "chunk B"]],
    "metadatas": [[
        {"source_id": "spark-tuning", "version_bucket": "3.5",
         "local_path": "references/a.md", "section_path": "Tuning > Shuffle"},
        {"source_id": "blog-x", "version_bucket": "n/a",
         "local_path": "references/b.md", "section_path": "Intro"},
    ]],
    "distances": [[0.2, 1.3]],
}


def test_ask_spark_docs_returns_chunks_and_citable_source_ids(monkeypatch):
    monkeypatch.setattr(
        mcp_server, "_resources",
        lambda corpus: (
            FakeModel(),
            FakeCollection(FAKE_RESULT),
            {"spark-tuning": "https://example.com/tuning"},
        ),
    )

    result = mcp_server.ask_spark_docs("how to tune shuffle?", k=3)

    assert result["question"] == "how to tune shuffle?"
    assert result["version_filter"] is None
    assert result["citable_source_ids"] == ["spark-tuning", "blog-x"]

    top = result["chunks"][0]
    assert top["rank"] == 1
    assert top["source_id"] == "spark-tuning"
    assert top["version_bucket"] == "3.5"
    assert top["relevance"] == 1 - 0.2
    assert top["local_path"] == "references/a.md"
    assert top["section_path"] == "Tuning > Shuffle"
    assert top["url"] == "https://example.com/tuning"
    assert top["text"] == "chunk A"

    # blog-x has no entry in the injected urls map -> falls back to "n/a"
    assert result["chunks"][1]["url"] == "n/a"


def test_ask_spark_docs_is_registered_as_an_mcp_tool():
    assert isinstance(mcp_server.mcp, mcp_server.MCPServer)
    tools = asyncio.run(mcp_server.mcp.list_tools())
    assert any(tool.name == "ask_spark_docs" for tool in tools)
