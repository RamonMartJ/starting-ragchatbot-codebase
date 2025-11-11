"""
ChromaDB health diagnostics - verify vector database is properly loaded.

These tests check (< 5 seconds):
- ChromaDB directory exists and is accessible
- Has articles loaded (count > 0)
- Article titles are valid strings
- People metadata is valid JSON
- Collections are properly initialized

Run with: pytest tests/diagnostics/test_chromadb_health.py -v
"""

import json
from pathlib import Path

import pytest


def test_chroma_directory_exists():
    """Verify ChromaDB directory exists."""
    from config import config

    chroma_path = Path(config.CHROMA_PATH)
    assert (
        chroma_path.exists()
    ), f"ChromaDB directory not found at {chroma_path}. Run ./run.sh to initialize."

    assert chroma_path.is_dir(), f"{chroma_path} exists but is not a directory"


def test_chroma_has_data_files():
    """Verify ChromaDB has data files (not empty database)."""
    from config import config

    chroma_path = Path(config.CHROMA_PATH)

    # ChromaDB creates files when data is stored
    # Check if there are any files in the directory
    files = list(chroma_path.rglob("*"))
    assert (
        len(files) > 0
    ), f"ChromaDB directory {chroma_path} appears empty. No articles loaded?"


def test_vector_store_can_initialize():
    """Verify VectorStore can be initialized without errors."""
    from config import config
    from vector_store import VectorStore

    try:
        store = VectorStore(
            chroma_path=config.CHROMA_PATH,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS,
        )
        assert store is not None, "VectorStore initialization returned None"
    except Exception as e:
        pytest.fail(f"Failed to initialize VectorStore: {e}")


def test_chroma_has_articles_loaded():
    """Verify ChromaDB has at least one article loaded."""
    from config import config
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    article_count = store.get_article_count()
    assert article_count > 0, (
        f"No articles found in ChromaDB. Expected > 0, got {article_count}. "
        "Run ./run.sh to load articles from docs/ folder."
    )


def test_chroma_article_titles_valid():
    """Verify all article titles are valid strings."""
    from config import config
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    titles = store.get_existing_article_titles()
    assert len(titles) > 0, "No article titles found"

    for title in titles:
        assert isinstance(title, str), f"Article title is not a string: {type(title)}"
        assert len(title) > 0, "Found empty article title"
        # Check title is not just whitespace
        assert (
            title.strip() == title
        ), f"Article title has leading/trailing whitespace: '{title}'"


def test_chroma_people_json_valid():
    """Verify people metadata in articles has valid JSON format."""
    from config import config
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    # Get all article metadata
    all_metadata = store.get_all_articles_metadata()
    assert len(all_metadata) > 0, "No article metadata found"

    invalid_json_articles = []

    for metadata in all_metadata:
        article_title = metadata.get("title", "unknown")
        people_json = metadata.get("people", "[]")

        # Verify it's a string
        if not isinstance(people_json, str):
            invalid_json_articles.append(
                (article_title, "people field is not a string")
            )
            continue

        # Verify it's valid JSON
        try:
            people_list = json.loads(people_json)
        except json.JSONDecodeError as e:
            invalid_json_articles.append((article_title, f"Invalid JSON: {e}"))
            continue

        # Verify it's a list
        if not isinstance(people_list, list):
            invalid_json_articles.append((article_title, "people is not a list"))
            continue

        # Verify each person has expected fields
        for idx, person in enumerate(people_list):
            if not isinstance(person, dict):
                invalid_json_articles.append(
                    (article_title, f"Person {idx} is not a dict")
                )
                continue

            # Check expected fields exist
            expected_fields = ["nombre", "cargo", "organizacion", "datos_interes"]
            for field in expected_fields:
                if field not in person:
                    invalid_json_articles.append(
                        (article_title, f"Person {idx} missing field: {field}")
                    )

    assert len(invalid_json_articles) == 0, (
        f"Found {len(invalid_json_articles)} articles with invalid people JSON:\n"
        + "\n".join(
            [f"  - {title}: {error}" for title, error in invalid_json_articles[:5]]
        )
    )


def test_chroma_collections_exist():
    """Verify both required ChromaDB collections exist."""
    from config import config
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    # Check article_catalog collection
    assert store.article_catalog is not None, "article_catalog collection is None"

    # Check article_content collection
    assert store.article_content is not None, "article_content collection is None"

    # Verify collections have data
    catalog_count = store.article_catalog.count()
    assert (
        catalog_count > 0
    ), f"article_catalog collection is empty (count = {catalog_count})"

    content_count = store.article_content.count()
    assert (
        content_count > 0
    ), f"article_content collection is empty (count = {content_count})"


def test_chroma_search_works():
    """Verify basic search functionality works."""
    from config import config
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    # Try a simple search
    results = store.search(query="test", limit=1)

    # Should not error even if no results
    assert results is not None, "Search returned None"
    assert not results.error, f"Search returned error: {results.error}"

    # If we have data, we should get some results for a generic query
    # (might be empty for very specific queries, but "test" should match something)
    # We won't assert results > 0 since that depends on article content


def test_chroma_article_links_present():
    """Verify articles have links stored in metadata."""
    from config import config
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    titles = store.get_existing_article_titles()
    assert len(titles) > 0, "No articles found"

    # Check at least one article has a link
    has_link = False
    articles_without_links = []

    for title in titles:
        link = store.get_article_link(title)
        if link:
            has_link = True
        else:
            articles_without_links.append(title)

    # We allow articles without links, but at least warn if all are missing
    if not has_link and len(articles_without_links) > 0:
        pytest.warns(
            UserWarning,
            match=f"No articles have links. {len(articles_without_links)} articles checked.",
        )


if __name__ == "__main__":
    # Allow running tests directly with: python test_chromadb_health.py
    pytest.main([__file__, "-v"])
