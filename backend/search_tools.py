from abc import ABC, abstractmethod
from typing import Any

from logger import get_logger
from vector_store import SearchResults, VectorStore

# Initialize logger for this module
logger = get_logger(__name__)


class Tool(ABC):
    """Abstract base class for all tools"""

    @abstractmethod
    def get_tool_definition(self) -> dict[str, Any]:
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

    def get_tool_definition(self) -> dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_news_content",
            "description": "Buscar en artículos de noticias con coincidencia semántica de títulos",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Qué buscar en el contenido de las noticias",
                    },
                    "article_title": {
                        "type": "string",
                        "description": "Título del artículo para filtrar (coincidencias parciales funcionan)",
                    },
                },
                "required": ["query"],
            },
        }

    def execute(self, query: str, article_title: str | None = None) -> str:
        """
        Execute the search tool with given parameters.

        Args:
            query: What to search for
            article_title: Optional article title filter

        Returns:
            Formatted search results or error message
        """
        # Log the search execution
        logger.info(
            f"ArticleSearchTool.execute(query='{query[:50]}...', article_title='{article_title}')"
        )

        # Use the vector store's unified search interface
        results = self.store.search(query=query, article_title=article_title)

        # Handle errors
        if results.error:
            logger.warning(f"Search error: {results.error}")
            return results.error

        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if article_title:
                filter_info += f" en artículo '{article_title}'"
            logger.info(f"No results found for query='{query[:50]}...'")
            return f"No se encontró contenido relevante{filter_info}."

        # Format and return results
        logger.info(f"Found {len(results.documents)} documents for query")
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

        for idx, (doc, meta) in enumerate(
            zip(results.documents, results.metadata, strict=True), start=1
        ):
            article_title = meta.get("article_title", "unknown")

            # Build context header for Claude
            header = f"[Artículo: {article_title}]"

            # Build source text for UI display
            source_text = f"Artículo: {article_title}"

            # Retrieve article link from VectorStore
            article_link = self.store.get_article_link(article_title)

            # Store source as dict with text, optional URL, and sequential index
            sources.append(
                {
                    "text": source_text,
                    "url": article_link,  # None if no link available
                    "index": idx,  # Sequential index for academic citations [1], [2], etc.
                }
            )

            formatted.append(f"{header}\n{doc}")

        # Store sources for retrieval by ToolManager
        # Now contains List[Dict[str, Optional[str]]]
        self.last_sources = sources

        return "\n\n".join(formatted)


class PeopleSearchTool(Tool):
    """
    Tool for searching and managing people mentioned in news articles.

    Funcionalidad:
    - Listar personas mencionadas en un artículo específico
    - Buscar artículos que mencionan una persona determinada
    - Obtener detalles completos de una persona
    - Buscar personas por cargo/rol (ej: todos los periodistas)
    """

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search

    def get_tool_definition(self) -> dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_people_in_articles",
            "description": "Buscar personas mencionadas en artículos de noticias. Sin parámetros: devuelve todas las personas ordenadas por frecuencia de aparición. Con parámetros: permite listar personas de un artículo específico, buscar artículos por persona, o encontrar personas por cargo/rol.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "article_title": {
                        "type": "string",
                        "description": "Título del artículo para listar todas las personas mencionadas (opcional)",
                    },
                    "person_name": {
                        "type": "string",
                        "description": "Nombre de la persona para buscar en qué artículos aparece (opcional)",
                    },
                    "role": {
                        "type": "string",
                        "description": "Cargo o rol para buscar personas (ej: 'Periodista', 'Presidente') (opcional)",
                    },
                },
                "required": [],  # All parameters are optional - no params returns all people by frequency
            },
        }

    def execute(
        self,
        article_title: str | None = None,
        person_name: str | None = None,
        role: str | None = None,
    ) -> str:
        """
        Execute the people search tool with given parameters.

        Workflow:
        1. If no parameters: Return all people ordered by frequency
        2. If article_title provided: List all people in that article
        3. If person_name provided: Find all articles mentioning that person
        4. If role provided: Find all people with that role across articles
        5. If multiple params: Combine results
        6. Store sources for UI display

        Args:
            article_title: Optional article title to filter by
            person_name: Optional person name to search for
            role: Optional role/cargo to search for

        Returns:
            Formatted results with person information and article context
        """
        logger.info(
            f"PeopleSearchTool.execute(article_title={article_title}, person_name={person_name}, role={role})"
        )

        # Reset sources for new search
        self.last_sources = []

        # Case 0: No parameters provided - return all people by frequency
        if not article_title and not person_name and not role:
            logger.debug("No parameters - returning all people by frequency")
            all_people = self.store.get_all_people_with_frequency()
            if all_people:
                logger.info(f"Found {len(all_people)} total people across all articles")
                return self._format_all_people(all_people)
            else:
                logger.info("No people found in any articles")
                return "No se encontraron personas registradas en las noticias."

        results = []

        # Case 1: List people from a specific article
        if article_title:
            logger.debug(f"Searching people in article: {article_title}")
            people_list = self.store.get_people_from_article(article_title)
            logger.info(f"Found {len(people_list)} people in article")
            if people_list:
                article_link = self.store.get_article_link(article_title)
                result = self._format_people_in_article(
                    article_title, article_link, people_list
                )
                results.append(result)

                # Store source for UI
                self.last_sources.append(
                    {
                        "text": f"Personas en: {article_title}",
                        "url": article_link,
                        "index": len(self.last_sources) + 1,
                    }
                )
            else:
                logger.warning(f"No people found in article '{article_title}'")
                return f"No se encontraron personas registradas en el artículo '{article_title}'."

        # Case 2: Find articles mentioning a specific person
        if person_name:
            logger.debug(f"Searching articles mentioning: {person_name}")
            articles = self.store.find_articles_by_person(person_name)
            logger.info(f"Found {len(articles)} articles mentioning '{person_name}'")
            if articles:
                for article in articles:
                    # Get people details from each article
                    people_list = self.store.get_people_from_article(article["title"])
                    # Filter to only show the requested person
                    matching_person = [
                        p
                        for p in people_list
                        if person_name.lower() in p.get("nombre", "").lower()
                    ]

                    if matching_person:
                        result = self._format_person_in_context(
                            matching_person[0], article["title"], article.get("link")
                        )
                        results.append(result)

                        # Store source for UI
                        self.last_sources.append(
                            {
                                "text": f"{person_name} en: {article['title']}",
                                "url": article.get("link"),
                                "index": len(self.last_sources) + 1,
                            }
                        )
            else:
                logger.warning(f"No articles found mentioning '{person_name}'")
                return f"No se encontraron artículos que mencionen a '{person_name}'."

        # Case 3: Find people by role
        if role:
            logger.debug(f"Searching people with role: {role}")
            people = self.store.find_people_by_role(role)
            logger.info(f"Found {len(people)} people with role '{role}'")
            if people:
                result = self._format_people_by_role(role, people)
                results.append(result)

                # Store sources for each person's article
                for person in people:
                    self.last_sources.append(
                        {
                            "text": f"{person.get('nombre')} en: {person.get('article_title')}",
                            "url": person.get("article_link"),
                            "index": len(self.last_sources) + 1,
                        }
                    )
            else:
                logger.warning(f"No people found with role '{role}'")
                return f"No se encontraron personas con el cargo '{role}'."

        final_result = (
            "\n\n".join(results) if results else "No se encontraron resultados."
        )
        logger.info(
            f"Returning {len(results)} results, {len(self.last_sources)} sources"
        )
        return final_result

    def _format_people_in_article(
        self,
        article_title: str,
        article_link: str | None,
        people: list[dict[str, Any]],
    ) -> str:
        """
        Format list of people mentioned in an article.

        Returns:
            Formatted string with article info and people list
        """
        lines = [f"[Artículo: {article_title}]"]
        if article_link:
            lines.append(f"Enlace: {article_link}")
        lines.append(f"\nPersonas mencionadas ({len(people)}):")

        for person in people:
            lines.append(f"- {person.get('nombre')}")
            if person.get("cargo"):
                lines.append(f"  Cargo: {person.get('cargo')}")
            if person.get("organizacion"):
                lines.append(f"  Organización: {person.get('organizacion')}")
            if person.get("datos_interes"):
                lines.append(f"  Datos: {person.get('datos_interes')}")

        return "\n".join(lines)

    def _format_person_in_context(
        self, person: dict[str, Any], article_title: str, article_link: str | None
    ) -> str:
        """
        Format a person's information with article context.

        Returns:
            Formatted string with person details and article reference
        """
        lines = [f"[Persona: {person.get('nombre')}]"]
        lines.append(f"Artículo: {article_title}")
        if article_link:
            lines.append(f"Enlace: {article_link}")

        if person.get("cargo"):
            lines.append(f"Cargo: {person.get('cargo')}")
        if person.get("organizacion"):
            lines.append(f"Organización: {person.get('organizacion')}")
        if person.get("datos_interes"):
            lines.append(f"Datos de interés: {person.get('datos_interes')}")

        return "\n".join(lines)

    def _format_people_by_role(self, role: str, people: list[dict[str, Any]]) -> str:
        """
        Format list of people filtered by role.

        Returns:
            Formatted string with people grouped by role
        """
        lines = [f"[Personas con cargo: {role}]"]
        lines.append(f"Total encontradas: {len(people)}\n")

        for person in people:
            lines.append(f"- {person.get('nombre')}")
            if person.get("organizacion"):
                lines.append(f"  Organización: {person.get('organizacion')}")
            lines.append(f"  Artículo: {person.get('article_title')}")
            if person.get("article_link"):
                lines.append(f"  Enlace: {person.get('article_link')}")
            if person.get("datos_interes"):
                lines.append(f"  Datos: {person.get('datos_interes')}")
            lines.append("")  # Empty line between people

        return "\n".join(lines)

    def _format_all_people(self, people: list[dict[str, Any]]) -> str:
        """
        Format all people ordered by frequency of appearance.

        Workflow:
        1. Create header with total count
        2. For each person (already sorted by frequency):
           - Show name and frequency
           - List unique roles and organizations
           - List articles where they appear
           - Add interesting facts
        3. Generate sources for UI with article links

        Args:
            people: List of people with frequency data (from VectorStore)

        Returns:
            Formatted string with all people information
        """
        lines = ["[Todas las Personas Mencionadas]"]
        lines.append(f"Total de personas: {len(people)}\n")

        for person in people:
            nombre = person.get("nombre")
            frecuencia = person.get("frecuencia", 0)
            cargos = person.get("cargos", [])
            organizaciones = person.get("organizaciones", [])
            articulos = person.get("articulos", [])
            datos = person.get("datos_interes", [])

            # Person header with frequency
            lines.append(
                f"- {nombre} (mencionado en {frecuencia} artículo{'s' if frecuencia > 1 else ''})"
            )

            # Show roles
            if cargos:
                lines.append(f"  Cargo(s): {', '.join(cargos)}")

            # Show organizations
            if organizaciones:
                lines.append(f"  Organización(es): {', '.join(organizaciones)}")

            # Show articles
            if articulos:
                lines.append("  Aparece en:")
                for idx, articulo in enumerate(articulos, 1):
                    article_title = articulo.get("title")
                    article_link = articulo.get("link")

                    lines.append(f"    {idx}. {article_title}")

                    # Store source for UI
                    source_idx = len(self.last_sources) + 1
                    self.last_sources.append(
                        {
                            "text": f"{nombre} en: {article_title}",
                            "url": article_link,
                            "index": source_idx,
                        }
                    )

            # Show interesting facts
            if datos:
                lines.append("  Datos de interés:")
                for dato in datos:
                    lines.append(f"    - {dato}")

            lines.append("")  # Empty line between people

        return "\n".join(lines)


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
            if hasattr(tool, "last_sources") and tool.last_sources:
                return tool.last_sources
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, "last_sources"):
                tool.last_sources = []
