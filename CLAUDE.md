# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **RAG (Retrieval-Augmented Generation) system** for querying news articles (branded as Antena3 news assistant). It uses ChromaDB for vector storage, Anthropic's Claude for AI generation with autonomous tool calling, and FastAPI with a static HTML/JS frontend.

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
- Article-specific questions → Claude calls `search_news_content` tool autonomously
- System prompt in `ai_generator.py:8-35` guides this behavior (in Spanish)

**Why it matters**: Reduces unnecessary vector searches and latency while maintaining accuracy for article queries.

**Implementation flow**:
```
User Query → Claude (with tools available)
           ↓
    [Claude decides]
           ↓
  Need search? → Yes → Execute ArticleSearchTool → Vector Search
           ↓                                             ↓
           No                          Results returned to Claude
           ↓                                             ↓
    Answer directly ←─────────────────────── Synthesize answer
```

### 2. Dual ChromaDB Collections Strategy

**Two separate collections** (`vector_store.py:51-52`):

1. **`article_catalog`**: Article metadata (one doc per article)
   - Purpose: Semantic matching for partial article titles
   - Example: "Carlos Mazón" → resolves to full title "El abogado Carlos Lacaci advierte sobre la situación de Carlos Mazón..."
   - Uses article title as document ID for fast lookup
   - Stores article link in metadata

2. **`article_content`**: Actual article chunks (many docs per article)
   - Purpose: Semantic search over article content
   - Metadata: `article_title`, `chunk_index`
   - Each chunk includes article context prefix for better search relevance

**Why dual collections**: Enables fuzzy article title resolution without polluting content search results. See `vector_store.py:100-114` for resolution logic.

### 3. Sentence-Based Chunking with Overlap

**Not character-based chunking** (`document_processor.py:24-94`):

- Splits text by sentence boundaries (regex handles abbreviations)
- Builds chunks from complete sentences up to `CHUNK_SIZE` (800 chars)
- Overlaps last N sentences between chunks (`CHUNK_OVERLAP` = 100 chars)
- Each chunk prefixed with article title for context: `"Artículo '{title}': {content}"`

**Why**: Preserves semantic meaning, better embedding quality, maintains context across chunk boundaries.

### 4. Conversation History in System Prompt

**Session management** (`session_manager.py`):
- In-memory only (ephemeral, lost on restart)
- Circular buffer: keeps last `MAX_HISTORY * 2` messages (default: 4 messages)
- History formatted as plain text and injected into Claude's system prompt

**Location**: `ai_generator.py:66-69` - history appended to system content.

### 5. Document Format: News Article Structure

**Expected format** for files in `/docs`:
```
Titular: [article headline]
[article content - summary and body]
Enlace: [article URL]
```

**Example** (`noticia_1.txt`):
```
Titular: El abogado Carlos Lacaci advierte sobre la situación de Carlos Mazón...
[Article body paragraphs]
Enlace: https://www.antena3.com/noticias/...
```

**Parsing logic**: `document_processor.py:96-177` uses regex to extract:
- `Titular:` line → article title (required)
- `Enlace:` line → article link (optional)
- All other non-empty lines → article content

### 6. Citation System with Clickable Links

**Academic-style citations** (`search_tools.py:80-122`):

- Search results include sequential index numbers [1], [2], [3]...
- Claude's system prompt instructs it to use these citations in responses
- Frontend replaces `[1]` with clickable tooltips showing source text
- Sources displayed as badges below answers with links to original articles

**Data flow**:
1. `ArticleSearchTool.execute()` retrieves matching chunks
2. For each result, fetches article link from `article_catalog` collection
3. Builds sources list: `[{"text": "Artículo: [title]", "url": "[link]", "index": 1}, ...]`
4. Stores in `last_sources` attribute for UI retrieval
5. Frontend renders inline citations `[1]` with tooltips and clickable badges

## Component Responsibilities

### `rag_system.py` - Main Orchestrator
- Coordinates all components (don't put business logic here)
- Entry point: `query(query, session_id)` at line 102
- Manages session history → AI generation → tool execution → source tracking
- Prompt construction at line 114 (in Spanish)

### `ai_generator.py` - Claude API Wrapper
- **Static system prompt** (lines 8-35): Guides tool usage behavior (Spanish instructions)
- Pre-built base API params for performance (lines 42-46)
- Two-phase tool execution (lines 88-140):
  1. Initial call with tools → Claude decides
  2. If tool_use → execute tools → final call with results

### `vector_store.py` - ChromaDB Interface
- **Main search method**: `search()` at line 61
- Article title resolution: `_resolve_article_title()` uses semantic matching (line 100)
- Filter building: `_build_filter()` handles article filtering (line 116)
- Add operations: `add_article_metadata()` and `add_article_content()`
- Article link retrieval: `get_article_link()` for source citations (line 200)

### `search_tools.py` - Tool Definitions
- `ArticleSearchTool`: Implements abstract `Tool` interface
- **Tool name**: `search_news_content` (Spanish description at line 31)
- **Tracks sources** in `last_sources` attribute with URLs for UI display (line 25)
- `ToolManager`: Registry pattern for extensible tool system
- Tool definitions must match Anthropic's tool schema

### `document_processor.py` - Document Parsing
- Regex-based metadata extraction (lines 128-145)
- `Titular:` pattern matching for article title (line 128)
- `Enlace:` pattern matching for article URL (line 135)
- Sentence-based chunking with overlap (lines 24-94)
- Returns `(Article, List[ArticleChunk])` tuples

### `session_manager.py` - Conversation State
- Simple in-memory dict: `sessions[session_id] = List[Message]`
- Auto-creates sessions if needed
- Formats history as "User: ...\nAssistant: ..." strings

### `models.py` - Data Models
- **Domain models**: `Article`, `ArticleChunk` (lines 11-47)
- **API models**: `QueryRequest`, `QueryResponse`, `ArticleStats` (lines 77-141)
- **Source model**: `Source` with `text`, `url`, `index` fields for citations (lines 55-75)
- Comprehensive inline documentation explaining workflow for each model

### `app.py` - FastAPI Application
- **Lifespan context manager** (lines 23-65): Replaces deprecated `@app.on_event`
- Auto-loads documents from `../docs` on startup (line 57)
- **Custom static files handler**: `DevStaticFiles` disables caching for development (lines 189-218)
- CORS and TrustedHost middleware for development (lines 83-100)
- API endpoints: `/api/query` and `/api/articles`

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

**AI generation settings** (`ai_generator.py:42-46`):
- `temperature = 0`: Deterministic responses (critical for RAG)
- `max_tokens = 800`: Response length limit
- `tool_choice = "auto"`: Claude decides tool usage

## API Contract

### POST `/api/query`
```json
Request:  {"query": "¿Qué dijo Carlos Mazón?", "session_id": "session_1"}
Response: {
  "answer": "...",
  "sources": [
    {"text": "Artículo: El abogado Carlos Lacaci...", "url": "https://...", "index": 1}
  ],
  "session_id": "session_1"
}
```

### GET `/api/articles`
```json
Response: {
  "total_articles": 5,
  "article_titles": [
    "El abogado Carlos Lacaci advierte sobre la situación de Carlos Mazón...",
    "..."
  ]
}
```

## Frontend Integration (`frontend/script.js`)

- Maintains `currentSessionId` for conversation continuity
- Uses `marked.js` for markdown rendering
- Sources displayed as collapsible details with clickable badges (lines 167-173)
- Loading states handled with animated dots (lines 103-116)
- Citation links with tooltips: replaces `[1]` with hover tooltips (lines 189-217)
- Duplicate source removal using Map (lines 137-149)

## Startup Behavior

**Important**: `app.py:23-65` - On startup (lifespan context manager), automatically loads all documents from `../docs` folder:
```python
articles, chunks = rag_system.add_articles_folder(docs_path, clear_existing=False)
```

This means adding new `.txt` files to `/docs` requires a server restart to be indexed.

## Adding New Articles

1. Create `.txt` file in `/docs` with expected format:
   ```
   Titular: [headline]
   [content]
   Enlace: [url]
   ```
2. Restart server (documents auto-loaded on startup)
3. Verify via `GET /api/articles` or check console logs
4. Duplicate detection: existing articles (by title) are skipped automatically (`rag_system.py:87-96`)

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

2. **Register in RAGSystem** (`rag_system.py:24-25`):
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
- **ALWAYS use `uv`** - never use pip for package management
- **Run Python files with `uv`**: `uv run python script.py`

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

## Development Guidelines

- **Comments**: Add comments above every new functionality explaining workflow process and functionality
- **Language**: System prompt and user-facing text are in Spanish (Antena3 news context)
- **Execution**: Don't auto-run files - provide instructions for the user to run them
- **Package manager**: Always use `uv`, never pip

## Important File References

- **Main orchestration**: `backend/rag_system.py:102` - `query()` method
- **Tool execution loop**: `backend/ai_generator.py:94-140` - `_handle_tool_execution()`
- **Vector search logic**: `backend/vector_store.py:61-98` - `search()` method
- **Chunking algorithm**: `backend/document_processor.py:24-94` - `chunk_text()`
- **System prompt**: `backend/ai_generator.py:8-35` - guides Claude's behavior (Spanish)
- **API endpoints**: `backend/app.py:108-178`
- **Document parsing**: `backend/document_processor.py:96-177` - article structure extraction
- **Citation system**: `search_tools.py:80-122` - source formatting with URLs
