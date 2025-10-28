from typing import List, Dict, Optional
from pydantic import BaseModel

# ============================================================================
# DOMAIN MODELS - Represent course structure and content
# ============================================================================
# These models represent the core domain entities for course materials.
# Used by DocumentProcessor to parse course documents and by VectorStore
# to organize content in ChromaDB collections.

class Lesson(BaseModel):
    """
    Represents a single lesson within a course.

    Workflow:
    1. DocumentProcessor extracts lesson metadata from course text files
    2. Lesson objects are stored in Course.lessons list
    3. Metadata used for filtering searches by lesson number
    """
    lesson_number: int  # Sequential lesson number (0, 1, 2, etc.)
    title: str          # Lesson title (e.g., "Introduction to RAG")
    lesson_link: Optional[str] = None  # URL link to the lesson video/page

class Course(BaseModel):
    """
    Represents a complete course with metadata and its lessons.

    Workflow:
    1. DocumentProcessor parses course document header (title, instructor, link)
    2. Course object created with empty lessons list
    3. Lessons added as document is processed
    4. Course stored in VectorStore.course_catalog for semantic matching
    5. Used to resolve partial course names (e.g., "MCP" → full title)
    """
    title: str                          # Full course title (used as unique ID)
    course_link: Optional[str] = None   # URL link to the course homepage
    instructor: Optional[str] = None    # Course instructor name
    lessons: List[Lesson] = []          # List of lessons in chronological order

class CourseChunk(BaseModel):
    """
    Represents a text chunk from course content for vector search.

    Workflow:
    1. DocumentProcessor.chunk_text() splits lesson content into chunks
    2. Each chunk includes metadata (course_title, lesson_number, position)
    3. Chunks stored in VectorStore.course_content collection
    4. Embeddings generated via sentence-transformers
    5. Used for semantic search during RAG queries

    Chunking strategy:
    - Sentence-based splitting (preserves semantic meaning)
    - ~800 characters per chunk with 100 char overlap
    - First chunk of lesson includes "Lesson N content:" prefix for context
    """
    content: str                        # The actual text content with context
    course_title: str                   # Which course this belongs to (for filtering)
    lesson_number: Optional[int] = None # Which lesson (for filtering by lesson)
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
    1. CourseSearchTool retrieves lesson links from ChromaDB
    2. Each source includes text (display name), optional URL, and index
    3. Index used for academic-style citations [1], [2] in response text
    4. Frontend renders inline citations with tooltips showing full source
    5. Links open in new tab when clicked

    Example:
    {
        "text": "Building Towards Computer Use - Lesson 4",
        "url": "https://learn.deeplearning.ai/courses/.../lesson/...",
        "index": 1
    }
    """
    text: str                    # Display text for the source (e.g., "Course X - Lesson N")
    url: Optional[str] = None    # Lesson video URL (None if no link available)
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

class CourseStats(BaseModel):
    """
    Response model for GET /api/courses endpoint.

    Workflow:
    1. Frontend requests course statistics on page load
    2. RAGSystem.get_course_analytics() queries VectorStore
    3. Returns count and titles of all loaded courses
    4. Frontend displays in sidebar for user reference

    Example:
    {
        "total_courses": 4,
        "course_titles": [
            "Building Towards Computer Use with Anthropic",
            "MCP: Build Rich-Context AI Apps",
            ...
        ]
    }
    """
    total_courses: int       # Total number of courses in vector store
    course_titles: List[str] # List of all course titles (chronological order)