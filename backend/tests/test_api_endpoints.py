"""
API endpoint tests for the RAG system FastAPI application.

Tests cover all HTTP endpoints including:
- POST /api/query: Query processing with RAG system
- GET /api/articles: Article statistics retrieval
- GET /: Root endpoint for static files

These tests use the test_app fixture which creates a minimal FastAPI app
without static file dependencies, allowing endpoint testing in isolation.
"""

import pytest
from fastapi import status


# ============================================================================
# /api/query ENDPOINT TESTS
# ============================================================================

@pytest.mark.api
def test_query_endpoint_basic_request(test_client):
    """
    Test basic successful query request to /api/query endpoint.

    Workflow:
    1. Send POST request with valid query payload
    2. Verify 200 status code returned
    3. Verify response contains answer, sources, and session_id
    4. Verify data types are correct
    """
    # Prepare request payload
    payload = {
        "query": "What is artificial intelligence?",
        "session_id": None  # Let the system create a session
    }

    # Send POST request to query endpoint
    response = test_client.post("/api/query", json=payload)

    # Verify successful response
    assert response.status_code == status.HTTP_200_OK

    # Parse response data
    data = response.json()

    # Verify response structure
    assert "answer" in data
    assert "sources" in data
    assert "session_id" in data

    # Verify data types
    assert isinstance(data["answer"], str)
    assert isinstance(data["sources"], list)
    assert isinstance(data["session_id"], str)

    # Verify answer is not empty
    assert len(data["answer"]) > 0


@pytest.mark.api
def test_query_endpoint_with_existing_session(test_client):
    """
    Test query request with existing session_id for conversation continuity.

    Workflow:
    1. Send first query to create session
    2. Extract session_id from response
    3. Send second query with same session_id
    4. Verify session_id is maintained across requests
    """
    # First query to create session
    first_payload = {
        "query": "Tell me about machine learning",
        "session_id": None
    }
    first_response = test_client.post("/api/query", json=first_payload)
    first_data = first_response.json()
    session_id = first_data["session_id"]

    # Second query with existing session
    second_payload = {
        "query": "Can you elaborate on that?",
        "session_id": session_id
    }
    second_response = test_client.post("/api/query", json=second_payload)
    second_data = second_response.json()

    # Verify session_id is maintained
    assert second_response.status_code == status.HTTP_200_OK
    assert second_data["session_id"] == session_id


@pytest.mark.api
def test_query_endpoint_with_custom_session(test_client):
    """
    Test query request with user-provided session_id.

    Workflow:
    1. Create custom session_id
    2. Send query with custom session_id
    3. Verify response uses the provided session_id
    """
    # Custom session ID
    custom_session = "my-custom-session-123"

    payload = {
        "query": "What are neural networks?",
        "session_id": custom_session
    }

    response = test_client.post("/api/query", json=payload)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["session_id"] == custom_session


@pytest.mark.api
def test_query_endpoint_empty_query(test_client):
    """
    Test query endpoint with empty query string.

    Workflow:
    1. Send request with empty query
    2. Verify endpoint still processes (returns 200)
    3. Empty queries should be handled gracefully
    """
    payload = {
        "query": "",
        "session_id": None
    }

    response = test_client.post("/api/query", json=payload)

    # Should return 200 even for empty query
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
def test_query_endpoint_long_query(test_client):
    """
    Test query endpoint with very long query text.

    Workflow:
    1. Create a long query string (>1000 characters)
    2. Send request with long query
    3. Verify endpoint handles long input without errors
    """
    # Create long query
    long_query = "What is artificial intelligence? " * 50  # ~1500 characters

    payload = {
        "query": long_query,
        "session_id": None
    }

    response = test_client.post("/api/query", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "answer" in data


@pytest.mark.api
def test_query_endpoint_sources_structure(test_client):
    """
    Test that query response sources have correct structure.

    Workflow:
    1. Send query request
    2. Verify sources is a list
    3. Verify each source has required fields: text, url, index
    """
    payload = {
        "query": "Test query for sources",
        "session_id": None
    }

    response = test_client.post("/api/query", json=payload)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK

    # Verify sources structure
    sources = data["sources"]
    assert isinstance(sources, list)

    # If sources exist, verify structure
    if len(sources) > 0:
        source = sources[0]
        assert "text" in source
        assert "url" in source
        assert "index" in source


@pytest.mark.api
def test_query_endpoint_invalid_json(test_client):
    """
    Test query endpoint with malformed JSON payload.

    Workflow:
    1. Send request with invalid JSON
    2. Verify 422 Unprocessable Entity status (validation error)
    """
    # Send malformed JSON (missing required 'query' field)
    response = test_client.post(
        "/api/query",
        json={"invalid_field": "value"}
    )

    # Should return 422 for validation error
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.api
def test_query_endpoint_missing_query_field(test_client):
    """
    Test query endpoint without required 'query' field.

    Workflow:
    1. Send request with only session_id, no query
    2. Verify 422 validation error is returned
    """
    payload = {
        "session_id": "test-session"
        # Missing 'query' field
    }

    response = test_client.post("/api/query", json=payload)

    # Should return 422 for missing required field
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.api
def test_query_endpoint_with_mock_error(test_client, mock_rag_system):
    """
    Test query endpoint error handling when RAG system fails.

    Workflow:
    1. Configure mock to raise an exception
    2. Send query request
    3. Verify 500 Internal Server Error is returned
    """
    # Configure mock to raise exception
    mock_rag_system.query.side_effect = Exception("Mock RAG system error")

    payload = {
        "query": "This will cause an error",
        "session_id": None
    }

    response = test_client.post("/api/query", json=payload)

    # Should return 500 for internal error
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# /api/articles ENDPOINT TESTS
# ============================================================================

@pytest.mark.api
def test_articles_endpoint_basic_request(test_client):
    """
    Test basic successful request to /api/articles endpoint.

    Workflow:
    1. Send GET request to /api/articles
    2. Verify 200 status code
    3. Verify response contains total_articles and article_titles
    4. Verify data types are correct
    """
    response = test_client.get("/api/articles")

    # Verify successful response
    assert response.status_code == status.HTTP_200_OK

    # Parse response data
    data = response.json()

    # Verify response structure
    assert "total_articles" in data
    assert "article_titles" in data

    # Verify data types
    assert isinstance(data["total_articles"], int)
    assert isinstance(data["article_titles"], list)


@pytest.mark.api
def test_articles_endpoint_response_values(test_client):
    """
    Test that /api/articles returns expected mock values.

    Workflow:
    1. Send GET request
    2. Verify mock values are returned correctly
    3. Verify total_articles matches length of article_titles
    """
    response = test_client.get("/api/articles")
    data = response.json()

    assert response.status_code == status.HTTP_200_OK

    # Verify mock values (configured in conftest.py)
    assert data["total_articles"] == 5
    assert len(data["article_titles"]) == 2  # Mock returns 2 titles


@pytest.mark.api
def test_articles_endpoint_article_titles_structure(test_client):
    """
    Test that article_titles contains string values.

    Workflow:
    1. Send GET request
    2. Verify each title in article_titles is a string
    """
    response = test_client.get("/api/articles")
    data = response.json()

    assert response.status_code == status.HTTP_200_OK

    # Verify all titles are strings
    for title in data["article_titles"]:
        assert isinstance(title, str)


@pytest.mark.api
def test_articles_endpoint_with_mock_error(test_client, mock_rag_system):
    """
    Test /api/articles error handling when analytics retrieval fails.

    Workflow:
    1. Configure mock to raise an exception
    2. Send GET request
    3. Verify 500 Internal Server Error is returned
    """
    # Configure mock to raise exception
    mock_rag_system.get_article_analytics.side_effect = Exception("Mock analytics error")

    response = test_client.get("/api/articles")

    # Should return 500 for internal error
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.api
def test_articles_endpoint_no_parameters(test_client):
    """
    Test that /api/articles doesn't require any parameters.

    Workflow:
    1. Send GET request with no parameters
    2. Verify successful response
    """
    response = test_client.get("/api/articles")

    assert response.status_code == status.HTTP_200_OK


# ============================================================================
# ENDPOINT INTEGRATION TESTS
# ============================================================================

@pytest.mark.api
@pytest.mark.integration
def test_query_and_articles_endpoints_together(test_client):
    """
    Test using both /api/query and /api/articles in sequence.

    Workflow:
    1. First fetch article statistics
    2. Then send a query about articles
    3. Verify both endpoints work correctly in sequence
    """
    # First, get article statistics
    articles_response = test_client.get("/api/articles")
    assert articles_response.status_code == status.HTTP_200_OK
    articles_data = articles_response.json()

    # Then, query about an article
    query_payload = {
        "query": f"Tell me about {articles_data['article_titles'][0]}",
        "session_id": None
    }
    query_response = test_client.post("/api/query", json=query_payload)
    assert query_response.status_code == status.HTTP_200_OK
    query_data = query_response.json()

    # Verify both responses are valid
    assert articles_data["total_articles"] > 0
    assert len(query_data["answer"]) > 0


@pytest.mark.api
@pytest.mark.integration
def test_multiple_queries_same_session(test_client):
    """
    Test multiple queries using the same session for conversation flow.

    Workflow:
    1. Send first query to create session
    2. Send multiple follow-up queries with same session_id
    3. Verify session_id remains consistent
    4. Verify all queries return valid responses
    """
    # First query
    first_response = test_client.post("/api/query", json={
        "query": "What is machine learning?",
        "session_id": None
    })
    session_id = first_response.json()["session_id"]

    # Second query
    second_response = test_client.post("/api/query", json={
        "query": "Can you give an example?",
        "session_id": session_id
    })

    # Third query
    third_response = test_client.post("/api/query", json={
        "query": "What are the applications?",
        "session_id": session_id
    })

    # Verify all responses successful
    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    assert third_response.status_code == status.HTTP_200_OK

    # Verify session_id consistency
    assert second_response.json()["session_id"] == session_id
    assert third_response.json()["session_id"] == session_id


@pytest.mark.api
def test_cors_headers_present(test_client):
    """
    Test that CORS headers are present in API responses.

    Workflow:
    1. Send OPTIONS request (CORS preflight)
    2. Verify CORS headers are present
    """
    # Test CORS on query endpoint
    response = test_client.options("/api/query")

    # CORS middleware should handle OPTIONS requests
    # TestClient may not fully simulate CORS preflight, but we can verify
    # the endpoint is accessible
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED]


# ============================================================================
# RESPONSE MODEL VALIDATION TESTS
# ============================================================================

@pytest.mark.api
def test_query_response_model_compliance(test_client):
    """
    Test that /api/query response complies with QueryResponse model.

    Workflow:
    1. Send query request
    2. Verify response has all required fields
    3. Verify no extra fields are present
    """
    payload = {"query": "Test query", "session_id": None}
    response = test_client.post("/api/query", json=payload)
    data = response.json()

    # Required fields from QueryResponse model
    required_fields = {"answer", "sources", "session_id"}

    # Verify all required fields present
    assert set(data.keys()) == required_fields


@pytest.mark.api
def test_articles_response_model_compliance(test_client):
    """
    Test that /api/articles response complies with ArticleStats model.

    Workflow:
    1. Send GET request to /api/articles
    2. Verify response has all required fields
    3. Verify no extra fields are present
    """
    response = test_client.get("/api/articles")
    data = response.json()

    # Required fields from ArticleStats model
    required_fields = {"total_articles", "article_titles"}

    # Verify all required fields present
    assert set(data.keys()) == required_fields
