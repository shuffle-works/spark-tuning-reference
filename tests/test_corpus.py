from scripts.corpus import CORPORA, SPARK, META


def test_corpora_registered():
    assert set(CORPORA) == {"spark", "meta"}
    assert CORPORA["spark"] is SPARK
    assert CORPORA["meta"] is META


def test_spark_profile_matches_todays_defaults():
    assert SPARK.collection_name == "spark_docs"
    assert SPARK.embedding_model == "multi-qa-mpnet-base-dot-v1"
    assert SPARK.references_dir.name == "references"
    assert SPARK.index_path == SPARK.references_dir / "index.yaml"
    assert SPARK.chroma_path.name == ".chromadb"
    assert SPARK.questions_path.name == "questions.yaml"
    assert SPARK.questions_path.parent.name == "research"
    assert SPARK.answers_q_dir.name == "q"
    assert SPARK.answers_dir.name == "answers"
    assert SPARK.content_state_path.name == "content-state.yaml"
    assert SPARK.manifest_path.name == "manifest.yaml"


def test_meta_profile_is_fully_independent_of_spark():
    assert META.collection_name == "meta_docs"
    assert META.embedding_model == "all-mpnet-base-v2"
    assert META.references_dir.name == "references-meta"
    assert META.chroma_path.name == ".chromadb-meta"
    assert META.questions_path == SPARK.questions_path.parent / "meta" / "questions.yaml"
    assert META.answers_q_dir == SPARK.questions_path.parent / "meta" / "answers" / "q"
    assert META.manifest_path.name == "manifest.yaml"
    assert META.manifest_path.parent.name == "meta"
    # no shared paths between the two profiles
    assert META.chroma_path != SPARK.chroma_path
    assert META.questions_path != SPARK.questions_path
    assert META.manifest_path != SPARK.manifest_path
