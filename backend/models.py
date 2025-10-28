from typing import List, Dict, Optional
from pydantic import BaseModel

# ============================================================================
# DOMAIN MODELS - Represent news article structure and content
# ============================================================================
# These models represent the core domain entities for news articles.
# Used by DocumentProcessor to parse article documents and by VectorStore
# to organize content in ChromaDB collections.

class Article(BaseModel):
    """
    Represents a news article with metadata.

    Workflow:
    1. DocumentProcessor parses article document (title, link)
    2. Article object created from document header
    3. Article stored in VectorStore.article_catalog for semantic matching
    4. Used to resolve partial article titles during search

    Format expected in .txt files:
    - Titular: [título]
    - [contenido]
    - Enlace: [url]
    """
    title: str                          # Article headline (used as unique ID)
    article_link: Optional[str] = None  # URL link to the original article

class ArticleChunk(BaseModel):
    """
    Represents a text chunk from article content for vector search.

    Workflow:
    1. DocumentProcessor.chunk_text() splits article content into chunks
    2. Each chunk includes metadata (article_title, chunk position)
    3. Chunks stored in VectorStore.article_content collection
    4. Embeddings generated via sentence-transformers
    5. Used for semantic search during RAG queries

    Chunking strategy:
    - Sentence-based splitting (preserves semantic meaning)
    - ~800 characters per chunk with 100 char overlap
    - Maintains article title context for filtering
    """
    content: str                        # The actual text content
    article_title: str                  # Which article this belongs to (for filtering)
    chunk_index: int                    # Sequential position in document

# ============================================================================
# API REQUEST/RESPONSE MODELS - FastAPI endpoint contracts
# ============================================================================
# These models define the API contract between frontend and backend.
# Used for request validation, response serialization, and API documentation.

class Source(BaseModel):
    """
    Represents a source citation with optional clickable link.

    Workflow:
    1. ArticleSearchTool retrieves article links from ChromaDB
    2. Each source includes text (display name), optional URL, and index
    3. Index used for academic-style citations [1], [2] in response text
    4. Frontend renders inline citations with tooltips showing full source
    5. Links open in new tab when clicked

    Example:
    {
        "text": "Artículo: La jefa del 112 admite que el Gobierno Central...",
        "url": "https://www.antena3.com/noticias/...",
        "index": 1
    }
    """
    text: str                    # Display text for the source (e.g., "Artículo: [título]")
    url: Optional[str] = None    # Article URL (None if no link available)
    index: int                   # Citation number for academic-style references [1], [2]

class QueryRequest(BaseModel):
    """
    Request model for POST /api/query endpoint.

    Workflow:
    1. Frontend sends user question via fetch() POST request
    2. FastAPI validates request against this schema
    3. session_id allows conversation continuity (maintained in SessionManager)
    4. If session_id is None, new session created automatically

    Example:
    {
        "query": "What is prompt caching?",
        "session_id": "session_1"  // optional
    }
    """
    query: str                      # User's question or search query
    session_id: Optional[str] = None  # Optional session ID for conversation history

class QueryResponse(BaseModel):
    """
    Response model for POST /api/query endpoint.

    Workflow:
    1. RAGSystem processes query (retrieval + AI generation)
    2. Response includes AI-generated answer from Claude
    3. sources list contains course/lesson references with clickable links
    4. session_id returned to frontend for subsequent requests

    Example:
    {
        "answer": "Prompt caching retains results of processing...",
        "sources": [
            {"text": "Course X - Lesson 4", "url": "https://..."},
            {"text": "Course Y - Lesson 2", "url": "https://..."}
        ],
        "session_id": "session_1"
    }
    """
    answer: str           # AI-generated response from Claude
    sources: List[Source] # List of source citations with optional URLs
    session_id: str       # Session ID for maintaining conversation context

class ArticleStats(BaseModel):
    """
    Response model for GET /api/articles endpoint.

    Workflow:
    1. Frontend requests article statistics on page load
    2. RAGSystem.get_article_analytics() queries VectorStore
    3. Returns count and titles of all loaded articles
    4. Frontend displays in sidebar for user reference

    Example:
    {
        "total_articles": 4,
        "article_titles": [
            "La jefa del 112 admite que el Gobierno Central...",
            "Titular de otra noticia...",
            ...
        ]
    }
    """
    total_articles: int       # Total number of articles in vector store
    article_titles: List[str] # List of all article titles (chronological order)