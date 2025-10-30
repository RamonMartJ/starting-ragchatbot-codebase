from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from vector_store import VectorStore, SearchResults


class Tool(ABC):
    """Abstract base class for all tools"""
    
    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class ArticleSearchTool(Tool):
    """Tool for searching news article content with semantic title matching"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_news_content",
            "description": "Buscar en artículos de noticias con coincidencia semántica de títulos",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Qué buscar en el contenido de las noticias"
                    },
                    "article_title": {
                        "type": "string",
                        "description": "Título del artículo para filtrar (coincidencias parciales funcionan)"
                    }
                },
                "required": ["query"]
            }
        }

    def execute(self, query: str, article_title: Optional[str] = None) -> str:
        """
        Execute the search tool with given parameters.

        Args:
            query: What to search for
            article_title: Optional article title filter

        Returns:
            Formatted search results or error message
        """

        # Use the vector store's unified search interface
        results = self.store.search(
            query=query,
            article_title=article_title
        )

        # Handle errors
        if results.error:
            return results.error

        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if article_title:
                filter_info += f" en artículo '{article_title}'"
            return f"No se encontró contenido relevante{filter_info}."

        # Format and return results
        return self._format_results(results)
    
    def _format_results(self, results: SearchResults) -> str:
        """
        Format search results with article context.

        Workflow:
        1. Iterate through search results with metadata
        2. Extract article title from metadata
        3. Retrieve article link from ChromaDB using VectorStore.get_article_link()
        4. Build source dict with text (display) and url (clickable link)
        5. Store sources as List[Dict] for frontend rendering

        Returns:
            Formatted string for Claude with context headers
        """
        formatted = []
        sources = []  # Track sources with URLs for the UI

        for idx, (doc, meta) in enumerate(zip(results.documents, results.metadata), start=1):
            article_title = meta.get('article_title', 'unknown')

            # Build context header for Claude
            header = f"[Artículo: {article_title}]"

            # Build source text for UI display
            source_text = f"Artículo: {article_title}"

            # Retrieve article link from VectorStore
            article_link = self.store.get_article_link(article_title)

            # Store source as dict with text, optional URL, and sequential index
            sources.append({
                "text": source_text,
                "url": article_link,  # None if no link available
                "index": idx  # Sequential index for academic citations [1], [2], etc.
            })

            formatted.append(f"{header}\n{doc}")

        # Store sources for retrieval by ToolManager
        # Now contains List[Dict[str, Optional[str]]]
        self.last_sources = sources

        return "\n\n".join(formatted)

class ToolManager:
    """Manages available tools for the AI"""
    
    def __init__(self):
        self.tools = {}
    
    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    
    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]
    
    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"
        
        return self.tools[tool_name].execute(**kwargs)
    
    def get_last_sources(self) -> list:
        """Get sources from the last search operation"""
        # Check all tools for last_sources attribute
        for tool in self.tools.values():
            if hasattr(tool, 'last_sources') and tool.last_sources:
                return tool.last_sources
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, 'last_sources'):
                tool.last_sources = []