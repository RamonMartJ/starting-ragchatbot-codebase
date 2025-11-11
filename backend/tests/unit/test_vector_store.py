"""
Unit tests for VectorStore - test vector database operations.

Tests cover:
- Search functionality with and without filters
- Article metadata management
- Article content chunking
- People management (CRUD operations)
- Error handling and edge cases

Run with: pytest tests/unit/test_vector_store.py -v
"""

import pytest
from models import Article, ArticleChunk, Person


class TestVectorStoreBasics:
    """Test basic VectorStore initialization and operations."""

    def test_vector_store_initializes(self, test_vector_store):
        """Verify VectorStore can be initialized."""
        assert test_vector_store is not None
        assert hasattr(test_vector_store, "article_catalog")
        assert hasattr(test_vector_store, "article_content")

    def test_collections_are_created(self, test_vector_store):
        """Verify both collections exist after initialization."""
        assert test_vector_store.article_catalog is not None
        assert test_vector_store.article_content is not None


class TestArticleMetadata:
    """Test article metadata storage and retrieval."""

    def test_add_article_metadata(self, test_vector_store):
        """Verify article metadata can be added."""
        article = Article(
            title="Test Article",
            content="Test content",
            article_link="https://example.com/test",
            people=[],
        )

        # Should not raise exception
        test_vector_store.add_article_metadata(article)

        # Verify it was added
        count = test_vector_store.get_article_count()
        assert count == 1

    def test_add_article_with_people(self, test_vector_store):
        """Verify article metadata with people can be added."""
        people = [
            Person(
                nombre="Dr. Jane Smith",
                cargo="Researcher",
                organizacion="Tech University",
                datos_interes="AI expert",
            ),
            Person(
                nombre="John Doe",
                cargo="CTO",
                organizacion="AI Corp",
                datos_interes="Pioneer",
            ),
        ]

        article = Article(
            title="AI Technology Article",
            content="Content about AI",
            article_link="https://example.com/ai",
            people=people,
        )

        test_vector_store.add_article_metadata(article)

        # Verify people were stored
        retrieved_people = test_vector_store.get_people_from_article(
            "AI Technology Article"
        )
        assert len(retrieved_people) == 2
        assert retrieved_people[0]["nombre"] == "Dr. Jane Smith"
        assert retrieved_people[1]["nombre"] == "John Doe"

    def test_get_existing_article_titles(self, test_vector_store):
        """Verify retrieval of all article titles."""
        articles = [
            Article(title="Article 1", content="Content 1", article_link="", people=[]),
            Article(title="Article 2", content="Content 2", article_link="", people=[]),
            Article(title="Article 3", content="Content 3", article_link="", people=[]),
        ]

        for article in articles:
            test_vector_store.add_article_metadata(article)

        titles = test_vector_store.get_existing_article_titles()
        assert len(titles) == 3
        assert "Article 1" in titles
        assert "Article 2" in titles
        assert "Article 3" in titles

    def test_get_article_link(self, test_vector_store):
        """Verify article link retrieval."""
        article = Article(
            title="Linked Article",
            content="Content",
            article_link="https://example.com/linked",
            people=[],
        )

        test_vector_store.add_article_metadata(article)

        link = test_vector_store.get_article_link("Linked Article")
        assert link == "https://example.com/linked"

    def test_get_article_link_nonexistent(self, test_vector_store):
        """Verify None is returned for non-existent article."""
        link = test_vector_store.get_article_link("Nonexistent Article")
        assert link is None


class TestArticleContent:
    """Test article content storage and chunking."""

    def test_add_article_content(self, test_vector_store):
        """Verify article content chunks can be added."""
        chunks = [
            ArticleChunk(
                article_title="Test Article",
                chunk_index=0,
                content="This is chunk 0 of the test article.",
            ),
            ArticleChunk(
                article_title="Test Article",
                chunk_index=1,
                content="This is chunk 1 of the test article.",
            ),
        ]

        # Should not raise exception
        test_vector_store.add_article_content(chunks)

        # Verify chunks were added (collection count should increase)
        count = test_vector_store.article_content.count()
        assert count == 2

    def test_add_empty_chunks_list(self, test_vector_store):
        """Verify empty chunks list is handled gracefully."""
        # Should not raise exception
        test_vector_store.add_article_content([])

        # Count should remain 0
        count = test_vector_store.article_content.count()
        assert count == 0


class TestSearch:
    """Test vector search functionality."""

    def test_search_with_data(self, test_vector_store):
        """Verify search works when data exists."""
        # Add test article
        article = Article(
            title="Machine Learning Basics",
            content="Introduction to neural networks and deep learning",
            article_link="https://example.com/ml",
            people=[],
        )
        test_vector_store.add_article_metadata(article)

        # Add content chunks
        chunks = [
            ArticleChunk(
                article_title="Machine Learning Basics",
                chunk_index=0,
                content="Neural networks are the foundation of deep learning",
            )
        ]
        test_vector_store.add_article_content(chunks)

        # Search for content
        results = test_vector_store.search(query="neural networks", limit=5)

        assert results is not None
        assert results.error is None
        assert not results.is_empty()
        assert len(results.documents) > 0

    def test_search_empty_database(self, test_vector_store):
        """Verify search on empty database returns empty results."""
        results = test_vector_store.search(query="test query", limit=5)

        assert results is not None
        # Empty results are valid (not an error)
        assert results.is_empty()

    def test_search_with_article_filter(self, test_vector_store):
        """Verify search with article title filter."""
        # Add two articles
        article1 = Article(
            title="Article About AI", content="AI content", article_link="", people=[]
        )
        article2 = Article(
            title="Article About ML", content="ML content", article_link="", people=[]
        )

        test_vector_store.add_article_metadata(article1)
        test_vector_store.add_article_metadata(article2)

        # Add content for both
        chunks1 = [
            ArticleChunk(
                article_title="Article About AI", chunk_index=0, content="AI technology"
            )
        ]
        chunks2 = [
            ArticleChunk(
                article_title="Article About ML", chunk_index=0, content="ML algorithms"
            )
        ]

        test_vector_store.add_article_content(chunks1)
        test_vector_store.add_article_content(chunks2)

        # Search with filter
        results = test_vector_store.search(
            query="technology", article_title="Article About AI"
        )

        assert results is not None
        # Should resolve title correctly
        if not results.is_empty():
            # All results should be from the filtered article
            for meta in results.metadata:
                assert meta.get("article_title") == "Article About AI"

    def test_search_nonexistent_article(self, test_vector_store):
        """Verify search for non-existent article returns error."""
        results = test_vector_store.search(
            query="test", article_title="Nonexistent Article"
        )

        assert results is not None
        assert results.error is not None
        assert "No article found matching" in results.error


class TestPeopleManagement:
    """Test people-related functionality."""

    def test_get_people_from_article(self, test_vector_store):
        """Verify retrieval of people from specific article."""
        people = [
            Person(
                nombre="Alice",
                cargo="CEO",
                organizacion="TechCorp",
                datos_interes="Founder",
            ),
            Person(
                nombre="Bob",
                cargo="CTO",
                organizacion="TechCorp",
                datos_interes="Engineer",
            ),
        ]

        article = Article(
            title="TechCorp News",
            content="Company announcement",
            article_link="",
            people=people,
        )

        test_vector_store.add_article_metadata(article)

        retrieved = test_vector_store.get_people_from_article("TechCorp News")
        assert len(retrieved) == 2
        assert retrieved[0]["nombre"] == "Alice"
        assert retrieved[0]["cargo"] == "CEO"

    def test_get_people_from_nonexistent_article(self, test_vector_store):
        """Verify empty list returned for non-existent article."""
        people = test_vector_store.get_people_from_article("Nonexistent")
        assert people == []

    def test_find_articles_by_person(self, test_vector_store):
        """Verify finding articles mentioning a person."""
        person1 = Person(
            nombre="Dr. Smith", cargo="Researcher", organizacion="", datos_interes=""
        )
        person2 = Person(
            nombre="Dr. Jones", cargo="Professor", organizacion="", datos_interes=""
        )

        article1 = Article(
            title="Research Paper", content="", article_link="url1", people=[person1]
        )
        article2 = Article(
            title="Conference Talk", content="", article_link="url2", people=[person1]
        )
        article3 = Article(
            title="Book Review", content="", article_link="url3", people=[person2]
        )

        test_vector_store.add_article_metadata(article1)
        test_vector_store.add_article_metadata(article2)
        test_vector_store.add_article_metadata(article3)

        # Find articles mentioning Dr. Smith
        articles = test_vector_store.find_articles_by_person("Dr. Smith")
        assert len(articles) == 2
        titles = [a["title"] for a in articles]
        assert "Research Paper" in titles
        assert "Conference Talk" in titles

    def test_find_articles_by_person_case_insensitive(self, test_vector_store):
        """Verify person search is case-insensitive."""
        person = Person(
            nombre="John Doe", cargo="Developer", organizacion="", datos_interes=""
        )
        article = Article(
            title="Tech Article", content="", article_link="", people=[person]
        )

        test_vector_store.add_article_metadata(article)

        # Search with different case
        articles = test_vector_store.find_articles_by_person("john doe")
        assert len(articles) == 1
        assert articles[0]["title"] == "Tech Article"

    def test_find_people_by_role(self, test_vector_store):
        """Verify finding people by their role."""
        people1 = [
            Person(
                nombre="Alice", cargo="CEO", organizacion="CompanyA", datos_interes=""
            ),
            Person(
                nombre="Bob",
                cargo="Developer",
                organizacion="CompanyA",
                datos_interes="",
            ),
        ]
        people2 = [
            Person(
                nombre="Charlie", cargo="CEO", organizacion="CompanyB", datos_interes=""
            )
        ]

        article1 = Article(
            title="Article 1", content="", article_link="", people=people1
        )
        article2 = Article(
            title="Article 2", content="", article_link="", people=people2
        )

        test_vector_store.add_article_metadata(article1)
        test_vector_store.add_article_metadata(article2)

        # Find all CEOs
        ceos = test_vector_store.find_people_by_role("CEO")
        assert len(ceos) == 2
        names = [p["nombre"] for p in ceos]
        assert "Alice" in names
        assert "Charlie" in names

    def test_get_all_people_with_frequency(self, test_vector_store):
        """Verify getting all people sorted by frequency."""
        person_alice = Person(
            nombre="Alice", cargo="CEO", organizacion="", datos_interes=""
        )
        person_bob = Person(
            nombre="Bob", cargo="CTO", organizacion="", datos_interes=""
        )

        # Alice appears in 2 articles, Bob in 1
        article1 = Article(
            title="A1", content="", article_link="l1", people=[person_alice]
        )
        article2 = Article(
            title="A2", content="", article_link="l2", people=[person_alice, person_bob]
        )

        test_vector_store.add_article_metadata(article1)
        test_vector_store.add_article_metadata(article2)

        all_people = test_vector_store.get_all_people_with_frequency()

        assert len(all_people) == 2
        # Should be sorted by frequency (Alice first with 2, Bob second with 1)
        assert all_people[0]["nombre"] == "Alice"
        assert all_people[0]["frecuencia"] == 2
        assert all_people[1]["nombre"] == "Bob"
        assert all_people[1]["frecuencia"] == 1


class TestDataClearing:
    """Test data clearing functionality."""

    def test_clear_all_data(self, test_vector_store):
        """Verify all data can be cleared."""
        # Add some data
        article = Article(title="Test", content="Content", article_link="", people=[])
        test_vector_store.add_article_metadata(article)

        chunks = [ArticleChunk(article_title="Test", chunk_index=0, content="Content")]
        test_vector_store.add_article_content(chunks)

        # Verify data exists
        assert test_vector_store.get_article_count() > 0

        # Clear all data
        test_vector_store.clear_all_data()

        # Verify data is cleared
        assert test_vector_store.get_article_count() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
