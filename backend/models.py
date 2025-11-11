from pydantic import BaseModel

# ============================================================================
# DOMAIN MODELS - Represent news article structure and content
# ============================================================================
# These models represent the core domain entities for news articles.
# Used by DocumentProcessor to parse article documents and by VectorStore
# to organize content in ChromaDB collections.


class Person(BaseModel):
    """
    Represents a person mentioned in a news article.

    Workflow:
    1. DocumentProcessor parses "Personas Mencionadas:" section in article
    2. Each line format: "- Nombre | Cargo | Organización | Datos"
    3. Person objects created and added to Article.people list
    4. Stored in VectorStore.article_catalog metadata as serialized JSON
    5. Used by PeopleSearchTool for person-based queries

    Fields:
    - nombre: Full name of the person (required)
    - cargo: Role or job title (e.g., "Periodista", "Presidente")
    - organizacion: Organization or entity affiliation
    - datos_interes: Additional contextual information
    """

    nombre: str  # Full name (required)
    cargo: str | None = None  # Role/occupation
    organizacion: str | None = None  # Organization/entity
    datos_interes: str | None = None  # Additional relevant data


class Article(BaseModel):
    """
    Represents a news article with metadata.

    Workflow:
    1. DocumentProcessor parses article document (title, link, people)
    2. Article object created from document header
    3. Article stored in VectorStore.article_catalog for semantic matching
    4. Used to resolve partial article titles during search

    Format expected in .txt files:
    - Titular: [título]
    - Personas Mencionadas:
      - Nombre | Cargo | Organización | Datos
    - [contenido]
    - Enlace: [url]
    """

    title: str  # Article headline (used as unique ID)
    article_link: str | None = None  # URL link to the original article
    people: list["Person"] = []  # List of people mentioned in the article


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

    content: str  # The actual text content
    article_title: str  # Which article this belongs to (for filtering)
    chunk_index: int  # Sequential position in document


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

    text: str  # Display text for the source (e.g., "Artículo: [título]")
    url: str | None = None  # Article URL (None if no link available)
    index: int  # Citation number for academic-style references [1], [2]


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

    query: str  # User's question or search query
    session_id: str | None = None  # Optional session ID for conversation history


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

    answer: str  # AI-generated response from Claude
    sources: list[Source]  # List of source citations with optional URLs
    session_id: str  # Session ID for maintaining conversation context


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

    total_articles: int  # Total number of articles in vector store
    article_titles: list[str]  # List of all article titles (chronological order)
