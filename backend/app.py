import warnings
warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import os

from config import config
from rag_system import RAGSystem
from models import QueryRequest, QueryResponse, CourseStats

# ============================================================================
# RAG SYSTEM INITIALIZATION
# ============================================================================
# Initialize RAG system globally before app startup to enable document loading
# during lifespan context. This ensures all components are ready before
# the lifespan startup phase executes.
rag_system = RAGSystem(config)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI startup and shutdown events.

    Replaces deprecated @app.on_event decorators with modern async context
    manager pattern. Handles application lifecycle events:

    Startup Phase (before yield):
    1. Check if ../docs directory exists
    2. Load all course documents from folder
    3. DocumentProcessor parses each .txt file
    4. Extract course metadata and lessons
    5. Chunk lesson content (sentence-based, with overlap)
    6. Generate embeddings via sentence-transformers
    7. Store in ChromaDB (course_catalog + course_content collections)
    8. Print summary of loaded courses

    Shutdown Phase (after yield):
    - Currently just logs shutdown message
    - Can be extended for cleanup (close DB connections, save state, etc.)

    Workflow:
    - Called automatically when uvicorn starts the app
    - Runs before any requests are processed
    - Ensures vector store is populated before API is available
    """
    # STARTUP: Load initial documents into vector store
    docs_path = "../docs"
    if os.path.exists(docs_path):
        print("Loading initial documents...")
        try:
            # Process all .txt files in docs folder
            # Returns: (num_courses: int, num_chunks: int)
            courses, chunks = rag_system.add_course_folder(docs_path, clear_existing=False)
            print(f"Loaded {courses} courses with {chunks} chunks")
        except Exception as e:
            print(f"Error loading documents: {e}")

    yield  # Application is now running and serving requests

    # SHUTDOWN: Cleanup resources (extend as needed)
    print("Shutting down...")

# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================
# Initialize FastAPI app with lifespan context manager for proper startup/shutdown
app = FastAPI(
    title="Course Materials RAG System",
    root_path="",
    lifespan=lifespan
)

# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================
# Middleware layers are executed in reverse order of addition (last added = first executed).
# Current setup is for development - production should restrict allowed_hosts and origins.

# Trusted Host Middleware: Accept requests from any host (for proxy compatibility)
# In production: Restrict to specific domains
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Allow all hosts (development only)
)

# CORS Middleware: Enable cross-origin requests from any origin
# Required for frontend to communicate with backend API during development
# In production: Restrict allow_origins to specific frontend URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Allow all origins (development only)
    allow_credentials=True,        # Allow cookies/auth headers
    allow_methods=["*"],           # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],           # Allow all request headers
    expose_headers=["*"],          # Expose all response headers to frontend
)

# ============================================================================
# API ENDPOINTS
# ============================================================================
# FastAPI endpoints for handling user queries and course statistics.
# All Pydantic models are defined in models.py for centralized management.

@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    Process a user query using the RAG system with conversation context.

    Workflow:
    1. Receive query and optional session_id from frontend
    2. Create new session if none provided (for conversation continuity)
    3. RAGSystem.query() orchestrates:
       - Retrieve conversation history from SessionManager
       - Send query to Claude with tool definitions
       - Claude autonomously decides to use search tool if needed
       - VectorStore performs semantic search in ChromaDB
       - Claude synthesizes answer from search results
       - Update conversation history
    4. Return answer, sources, and session_id to frontend

    Args:
        request: QueryRequest with user's question and optional session_id

    Returns:
        QueryResponse with AI-generated answer, source citations, and session_id

    Raises:
        HTTPException: 500 error if RAG processing fails
    """
    try:
        # Create session if not provided (enables conversation continuity)
        session_id = request.session_id
        if not session_id:
            session_id = rag_system.session_manager.create_session()

        # Process query using RAG system (retrieval + AI generation)
        # Returns: (answer: str, sources: List[str])
        answer, sources = rag_system.query(request.query, session_id)

        return QueryResponse(
            answer=answer,
            sources=sources,
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses", response_model=CourseStats)
async def get_course_stats():
    """
    Get statistics about loaded courses in the system.

    Workflow:
    1. Frontend requests course stats on page load (sidebar display)
    2. RAGSystem.get_course_analytics() queries VectorStore
    3. VectorStore.get_course_count() counts documents in course_catalog
    4. VectorStore.get_existing_course_titles() retrieves all course IDs
    5. Return statistics to frontend for display

    Returns:
        CourseStats with total count and list of course titles

    Raises:
        HTTPException: 500 error if analytics retrieval fails
    """
    try:
        # Query RAG system for course analytics
        analytics = rag_system.get_course_analytics()
        return CourseStats(
            total_courses=analytics["total_courses"],
            course_titles=analytics["course_titles"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# STATIC FILE SERVING
# ============================================================================
# Serves frontend HTML/CSS/JS files from ../frontend directory.
# Mounted at root "/" so frontend is accessible at http://localhost:8000

from fastapi.responses import FileResponse


class DevStaticFiles(StaticFiles):
    """
    Custom static file handler that disables caching for development.

    Purpose:
    - During development, browser caching can serve stale HTML/CSS/JS files
    - This class adds no-cache headers to all static file responses
    - Ensures developers always see latest frontend changes after refresh

    Workflow:
    1. Client requests static file (e.g., /index.html)
    2. Parent StaticFiles class resolves and reads file
    3. This class intercepts response and adds no-cache headers
    4. Browser forced to re-fetch file on every request

    Production:
    - Remove this class and use standard StaticFiles
    - Enable caching for better performance (Cache-Control: max-age=3600)
    """
    async def get_response(self, path: str, scope):
        # Get response from parent StaticFiles class
        response = await super().get_response(path, scope)

        # Add no-cache headers to force browser to always fetch fresh files
        if isinstance(response, FileResponse):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"  # HTTP/1.0 compatibility
            response.headers["Expires"] = "0"        # Force immediate expiration

        return response


# Mount frontend static files at root path
# - directory="../frontend": Serves files from frontend folder
# - html=True: Automatically serves index.html for directory requests
# - name="static": Internal route name for FastAPI
# Result: http://localhost:8000/ → serves frontend/index.html
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")