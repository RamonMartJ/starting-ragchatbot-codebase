# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **RAG (Retrieval-Augmented Generation) system** for querying course materials. It uses ChromaDB for vector storage, Anthropic's Claude for AI generation with autonomous tool calling, and FastAPI with a static HTML/JS frontend.

## Essential Commands

### Setup
```bash
# Install dependencies
uv sync

# Configure API key (create .env file in root)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### Running the Application
```bash
# Quick start (from project root)
./run.sh

# Manual start
cd backend && uv run uvicorn app:app --reload --port 8000

# Access points:
# - Web UI: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

### Development
```bash
# Clear vector database and reload documents
rm -rf backend/chroma_db/
./run.sh

# Run with debug logging
cd backend && uv run uvicorn app:app --reload --port 8000 --log-level debug
```

## Architecture: Key Non-Obvious Decisions

### 1. Tool-Based RAG vs. Traditional Retrieval

**Critical Design**: This system uses **Claude's autonomous tool calling** instead of always retrieving before answering.

- Claude receives tool definitions but decides when to use them
- General knowledge questions → answered directly (no search)
- Course-specific questions → Claude calls `search_course_content` tool autonomously
- System prompt in `ai_generator.py:8-30` guides this behavior

**Why it matters**: Reduces unnecessary vector searches and latency while maintaining accuracy for course queries.

**Implementation flow**:
```
User Query → Claude (with tools available)
           ↓
    [Claude decides]
           ↓
  Need search? → Yes → Execute CourseSearchTool → Vector Search
           ↓                                             ↓
           No                          Results returned to Claude
           ↓                                             ↓
    Answer directly ←─────────────────────── Synthesize answer
```

### 2. Dual ChromaDB Collections Strategy

**Two separate collections** (`vector_store.py:51-52`):

1. **`course_catalog`**: Course metadata (one doc per course)
   - Purpose: Semantic matching for partial course names
   - Example: "MCP" → resolves to full title "MCP: Build Rich-Context AI Apps..."
   - Uses course title as document ID for fast lookup
   - Stores serialized lessons JSON in metadata

2. **`course_content`**: Actual lesson chunks (many docs per course)
   - Purpose: Semantic search over lesson content
   - Metadata: `course_title`, `lesson_number`, `chunk_index`

**Why dual collections**: Enables fuzzy course name resolution without polluting content search results. See `vector_store.py:102-116` for resolution logic.

### 3. Sentence-Based Chunking with Overlap

**Not character-based chunking** (`document_processor.py:25-91`):

- Splits text by sentence boundaries (regex handles abbreviations)
- Builds chunks from complete sentences up to `CHUNK_SIZE` (800 chars)
- Overlaps last N sentences between chunks (`CHUNK_OVERLAP` = 100 chars)

**Why**: Preserves semantic meaning, better embedding quality, maintains context across chunk boundaries.

### 4. Conversation History in System Prompt

**Session management** (`session_manager.py`):
- In-memory only (ephemeral, lost on restart)
- Circular buffer: keeps last `MAX_HISTORY * 2` messages (default: 4 messages)
- History formatted as plain text and injected into Claude's system prompt

**Location**: `ai_generator.py:61-64` - history appended to system content.

### 5. Document Format: Structured Text Parsing

**Expected format** for files in `/docs`:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [instructor]

Lesson 0: [lesson_title]
Lesson Link: [url]
[natural language content...]

Lesson 1: [lesson_title]
...
```

**Parsing logic**: `document_processor.py:97-259` uses regex to extract metadata and detect lesson boundaries.

## Component Responsibilities

### `rag_system.py` - Main Orchestrator
- Coordinates all components (don't put business logic here)
- Entry point: `query(query, session_id)` at line 102
- Manages session history → AI generation → tool execution → source tracking

### `ai_generator.py` - Claude API Wrapper
- **Static system prompt** (line 8): Guides tool usage behavior
- Pre-built base API params for performance (line 37-41)
- Two-phase tool execution (line 89-135):
  1. Initial call with tools → Claude decides
  2. If tool_use → execute tools → final call with results

### `vector_store.py` - ChromaDB Interface
- **Main search method**: `search()` at line 61
- Course name resolution: `_resolve_course_name()` uses semantic matching
- Filter building: `_build_filter()` handles course + lesson combinations
- Add operations: `add_course_metadata()` and `add_course_content()`

### `search_tools.py` - Tool Definitions
- `CourseSearchTool`: Implements abstract `Tool` interface
- **Tracks sources** in `last_sources` attribute for UI display (line 25)
- `ToolManager`: Registry pattern for extensible tool system
- Tool definitions must match Anthropic's tool schema

### `document_processor.py` - Document Parsing
- Regex-based metadata extraction (lines 116-139)
- Lesson boundary detection via "Lesson N:" pattern (line 166)
- Sentence-based chunking with overlap (lines 25-91)
- Returns `(Course, List[CourseChunk])` tuples

### `session_manager.py` - Conversation State
- Simple in-memory dict: `sessions[session_id] = List[Message]`
- Auto-creates sessions if needed
- Formats history as "User: ...\nAssistant: ..." strings

## Configuration (`backend/config.py`)

Critical settings:
```python
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"  # Model version
EMBEDDING_MODEL = "all-MiniLM-L6-v2"          # Sentence transformers
CHUNK_SIZE = 800                               # Max chunk characters
CHUNK_OVERLAP = 100                            # Overlap between chunks
MAX_RESULTS = 5                                # Vector search results
MAX_HISTORY = 2                                # Conversation exchanges kept
CHROMA_PATH = "./chroma_db"                   # Vector DB location
```

**AI generation settings** (`ai_generator.py:38-40`):
- `temperature = 0`: Deterministic responses (critical for RAG)
- `max_tokens = 800`: Response length limit
- `tool_choice = "auto"`: Claude decides tool usage

## API Contract

### POST `/api/query`
```json
Request:  {"query": "What is MCP?", "session_id": "session_1"}
Response: {"answer": "...", "sources": ["Course X - Lesson Y"], "session_id": "session_1"}
```

### GET `/api/courses`
```json
Response: {"total_courses": 4, "course_titles": ["Course 1", ...]}
```

## Frontend Integration (`frontend/script.js`)

- Maintains `currentSessionId` for conversation continuity
- Uses `marked.js` for markdown rendering
- Sources displayed in collapsible `<details>` element
- Loading states handled with animated dots

## Startup Behavior

**Important**: `app.py:88-98` - On startup, automatically loads all documents from `../docs` folder:
```python
@app.on_event("startup")
async def startup_event():
    rag_system.add_course_folder(docs_path, clear_existing=False)
```

This means adding new `.txt` files to `/docs` requires a server restart to be indexed.

## Adding New Courses

1. Create `.txt` file in `/docs` with expected format (see "Document Format" above)
2. Restart server (documents auto-loaded on startup)
3. Verify via `GET /api/courses` or check console logs

## Extending the Tool System

To add new tools:

1. **Create tool class** in `search_tools.py`:
```python
class MyNewTool(Tool):
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": "my_tool",
            "description": "What the tool does",
            "input_schema": {...}
        }

    def execute(self, **kwargs) -> str:
        # Tool implementation
        return result_string
```

2. **Register in RAGSystem** (`rag_system.py:24`):
```python
my_tool = MyNewTool()
self.tool_manager.register_tool(my_tool)
```

3. **Update system prompt** in `ai_generator.py` to guide Claude on when to use it

## Python Version & Dependencies

- **Required**: Python 3.13+ (specified in `.python-version`)
- **Package manager**: `uv` (not pip) - fast, Rust-based
- **Lock file**: `uv.lock` ensures reproducible builds
- **Dependencies**: See `pyproject.toml` - includes chromadb, anthropic, sentence-transformers, fastapi

## Common Issues

**"ANTHROPIC_API_KEY not found"**:
- Check `.env` file exists in project root (not in `backend/`)
- Verify format: `ANTHROPIC_API_KEY=sk-ant-...` (no quotes, no spaces)

**Port 8000 in use**:
```bash
cd backend && uv run uvicorn app:app --reload --port 8080
```

**ChromaDB corruption**:
```bash
rm -rf backend/chroma_db/
./run.sh  # Recreates and reloads documents
```

**Sessions lost between restarts**:
- Expected behavior (in-memory only)
- For persistent sessions, modify `session_manager.py` to use database

## Important File References

- **Main orchestration**: `backend/rag_system.py:102` - `query()` method
- **Tool execution loop**: `backend/ai_generator.py:89-135` - `_handle_tool_execution()`
- **Vector search logic**: `backend/vector_store.py:61-100` - `search()` method
- **Chunking algorithm**: `backend/document_processor.py:25-91` - `chunk_text()`
- **System prompt**: `backend/ai_generator.py:8-30` - guides Claude's behavior
- **API endpoints**: `backend/app.py:56-86`
- Always use uv as a package manager, do NOT use pip at all.
- use uv to run any Python files.
- Add comments above every new functionality explaining workflow process and functionality.