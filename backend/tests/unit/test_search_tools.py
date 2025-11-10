"""
Unit tests for search_tools module.

Tests cover:
- ArticleSearchTool execution and source tracking
- PeopleSearchTool execution and source tracking
- ToolManager registration and execution
- Tool definition schema validation
- Error handling for edge cases

Run with: pytest tests/unit/test_search_tools.py -v
"""

import pytest
from unittest.mock import Mock
from search_tools import ArticleSearchTool, PeopleSearchTool, ToolManager, Tool
from vector_store import SearchResults


# ============================================================================
# ARTICLE SEARCH TOOL TESTS
# ============================================================================

class TestArticleSearchTool:
    """Test ArticleSearchTool functionality."""

    def test_get_tool_definition(self):
        """
        Verify tool definition has correct schema for Anthropic.

        Workflow:
        1. Create ArticleSearchTool with mock VectorStore
        2. Get tool definition
        3. Verify all required fields are present
        """
        # Setup: Create tool with mock store
        mock_store = Mock()
        tool = ArticleSearchTool(mock_store)

        # Execute: Get definition
        definition = tool.get_tool_definition()

        # Verify: Schema is correct
        assert definition["name"] == "search_news_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["type"] == "object"
        assert "query" in definition["input_schema"]["properties"]
        assert "article_title" in definition["input_schema"]["properties"]
        assert "query" in definition["input_schema"]["required"]

    def test_execute_with_valid_results(self):
        """
        Test execute() returns formatted results when search succeeds.

        Workflow:
        1. Mock VectorStore to return valid SearchResults
        2. Execute search tool
        3. Verify formatted results are returned
        4. Verify sources are tracked
        """
        # Setup: Mock VectorStore with results
        mock_store = Mock()
        search_results = SearchResults(
            documents=["Test content from article"],
            metadata=[{"article_title": "Test Article"}],
            distances=[0.5],
            error=None
        )
        mock_store.search.return_value = search_results
        mock_store.get_article_link.return_value = "https://example.com/test"

        tool = ArticleSearchTool(mock_store)

        # Execute: Run search
        result = tool.execute(query="test query")

        # Verify: Results are formatted
        assert result is not None
        assert "Test Article" in result
        assert "Test content from article" in result
        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["text"] == "Art�culo: Test Article"
        assert tool.last_sources[0]["url"] == "https://example.com/test"
        assert tool.last_sources[0]["index"] == 1

    def test_execute_with_empty_results(self):
        """
        Test execute() returns appropriate message when no results found.

        Workflow:
        1. Mock VectorStore to return empty SearchResults
        2. Execute search tool
        3. Verify "no content found" message is returned
        """
        # Setup: Mock empty results
        mock_store = Mock()
        search_results = SearchResults.empty("")
        search_results.error = None  # No error, just empty
        mock_store.search.return_value = search_results

        tool = ArticleSearchTool(mock_store)

        # Execute: Run search
        result = tool.execute(query="test query")

        # Verify: Empty message returned
        assert "No se encontr� contenido relevante" in result

    def test_execute_with_error(self):
        """
        Test execute() returns error message when search fails.

        Workflow:
        1. Mock VectorStore to return error in SearchResults
        2. Execute search tool
        3. Verify error message is returned
        """
        # Setup: Mock error results
        mock_store = Mock()
        search_results = SearchResults.empty("Database connection error")
        mock_store.search.return_value = search_results

        tool = ArticleSearchTool(mock_store)

        # Execute: Run search
        result = tool.execute(query="test query")

        # Verify: Error message returned
        assert "Database connection error" in result

    def test_execute_with_article_filter(self):
        """
        Test execute() passes article_title filter to VectorStore.

        Workflow:
        1. Mock VectorStore
        2. Execute search with article_title
        3. Verify article_title was passed to VectorStore.search()
        """
        # Setup: Mock store
        mock_store = Mock()
        search_results = SearchResults(
            documents=["Content"],
            metadata=[{"article_title": "Filtered Article"}],
            distances=[0.3],
            error=None
        )
        mock_store.search.return_value = search_results
        mock_store.get_article_link.return_value = None

        tool = ArticleSearchTool(mock_store)

        # Execute: Search with filter
        result = tool.execute(query="test", article_title="Filtered Article")

        # Verify: article_title was passed to search
        mock_store.search.assert_called_once_with(
            query="test",
            article_title="Filtered Article"
        )

    def test_format_results_tracks_sources(self):
        """
        Test that _format_results correctly tracks sources with URLs.

        Workflow:
        1. Create tool and mock VectorStore
        2. Mock search results with multiple documents
        3. Execute search
        4. Verify sources are tracked with correct indices
        """
        # Setup: Mock multiple results
        mock_store = Mock()
        search_results = SearchResults(
            documents=["Doc 1", "Doc 2", "Doc 3"],
            metadata=[
                {"article_title": "Article 1"},
                {"article_title": "Article 2"},
                {"article_title": "Article 3"}
            ],
            distances=[0.1, 0.2, 0.3],
            error=None
        )
        mock_store.search.return_value = search_results
        mock_store.get_article_link.side_effect = [
            "https://example.com/1",
            "https://example.com/2",
            None  # Third article has no link
        ]

        tool = ArticleSearchTool(mock_store)

        # Execute: Run search
        result = tool.execute(query="test")

        # Verify: Sources tracked with sequential indices
        assert len(tool.last_sources) == 3
        assert tool.last_sources[0]["index"] == 1
        assert tool.last_sources[1]["index"] == 2
        assert tool.last_sources[2]["index"] == 3
        assert tool.last_sources[0]["url"] == "https://example.com/1"
        assert tool.last_sources[1]["url"] == "https://example.com/2"
        assert tool.last_sources[2]["url"] is None


# ============================================================================
# PEOPLE SEARCH TOOL TESTS
# ============================================================================

class TestPeopleSearchTool:
    """Test PeopleSearchTool functionality."""

    def test_get_tool_definition(self):
        """
        Verify tool definition has correct schema for Anthropic.

        Workflow:
        1. Create PeopleSearchTool
        2. Get tool definition
        3. Verify schema is correct (all params optional)
        """
        # Setup: Create tool
        mock_store = Mock()
        tool = PeopleSearchTool(mock_store)

        # Execute: Get definition
        definition = tool.get_tool_definition()

        # Verify: Schema is correct
        assert definition["name"] == "search_people_in_articles"
        assert "description" in definition
        assert "input_schema" in definition
        assert "article_title" in definition["input_schema"]["properties"]
        assert "person_name" in definition["input_schema"]["properties"]
        assert "role" in definition["input_schema"]["properties"]
        assert definition["input_schema"]["required"] == []  # All optional

    def test_execute_with_article_title(self):
        """
        Test execute() with article_title parameter.

        Workflow:
        1. Mock VectorStore to return people for article
        2. Execute with article_title
        3. Verify people list is formatted correctly
        4. Verify sources are tracked
        """
        # Setup: Mock people in article
        mock_store = Mock()
        mock_store.get_people_from_article.return_value = [
            {
                "nombre": "Alice Smith",
                "cargo": "CEO",
                "organizacion": "TechCorp",
                "datos_interes": "Founder"
            }
        ]
        mock_store.get_article_link.return_value = "https://example.com/article"

        tool = PeopleSearchTool(mock_store)

        # Execute: Search by article
        result = tool.execute(article_title="Test Article")

        # Verify: Results formatted correctly
        assert "Alice Smith" in result
        assert "CEO" in result
        assert "TechCorp" in result
        assert len(tool.last_sources) == 1
        assert "Test Article" in tool.last_sources[0]["text"]

    def test_execute_with_person_name(self):
        """
        Test execute() with person_name parameter.

        Workflow:
        1. Mock VectorStore to return articles for person
        2. Execute with person_name
        3. Verify articles are listed correctly
        4. Verify sources are tracked
        """
        # Setup: Mock articles mentioning person
        mock_store = Mock()
        mock_store.find_articles_by_person.return_value = [
            {"title": "Article 1", "link": "https://example.com/1"}
        ]
        mock_store.get_people_from_article.return_value = [
            {
                "nombre": "Bob Jones",
                "cargo": "CTO",
                "organizacion": "StartupX",
                "datos_interes": "Tech lead"
            }
        ]

        tool = PeopleSearchTool(mock_store)

        # Execute: Search by person
        result = tool.execute(person_name="Bob Jones")

        # Verify: Results include person and article
        assert "Bob Jones" in result
        assert "Article 1" in result
        assert len(tool.last_sources) == 1

    def test_execute_with_role(self):
        """
        Test execute() with role parameter.

        Workflow:
        1. Mock VectorStore to return people with role
        2. Execute with role
        3. Verify people with role are listed
        4. Verify sources are tracked
        """
        # Setup: Mock people by role
        mock_store = Mock()
        mock_store.find_people_by_role.return_value = [
            {
                "nombre": "Charlie Brown",
                "cargo": "CEO",
                "organizacion": "CompanyA",
                "article_title": "News Article",
                "article_link": "https://example.com/news",
                "datos_interes": "Industry leader"
            }
        ]

        tool = PeopleSearchTool(mock_store)

        # Execute: Search by role
        result = tool.execute(role="CEO")

        # Verify: Results include people with role
        assert "Charlie Brown" in result
        assert "CEO" in result
        assert len(tool.last_sources) == 1

    def test_execute_no_parameters_returns_all_people(self):
        """
        Test execute() without parameters returns all people by frequency.

        Workflow:
        1. Mock VectorStore to return all people
        2. Execute without parameters
        3. Verify all people are listed with frequency
        """
        # Setup: Mock all people
        mock_store = Mock()
        mock_store.get_all_people_with_frequency.return_value = [
            {
                "nombre": "Person A",
                "frecuencia": 3,
                "cargos": ["CEO"],
                "organizaciones": ["CompanyX"],
                "articulos": [
                    {"title": "Article 1", "link": "url1"},
                    {"title": "Article 2", "link": "url2"}
                ],
                "datos_interes": ["Fact 1"]
            }
        ]

        tool = PeopleSearchTool(mock_store)

        # Execute: No parameters
        result = tool.execute()

        # Verify: All people returned
        assert "Person A" in result
        assert "3 art�culo" in result
        assert "CEO" in result
        mock_store.get_all_people_with_frequency.assert_called_once()

    def test_execute_no_results(self):
        """
        Test execute() returns appropriate message when no results found.

        Workflow:
        1. Mock VectorStore to return empty lists
        2. Execute with various parameters
        3. Verify "not found" messages are returned
        """
        # Setup: Mock empty results
        mock_store = Mock()
        mock_store.get_people_from_article.return_value = []
        mock_store.find_articles_by_person.return_value = []
        mock_store.find_people_by_role.return_value = []

        tool = PeopleSearchTool(mock_store)

        # Test article_title with no people
        result1 = tool.execute(article_title="Empty Article")
        assert "No se encontraron personas" in result1

        # Test person_name with no articles
        result2 = tool.execute(person_name="Unknown Person")
        assert "No se encontraron art�culos" in result2

        # Test role with no people
        result3 = tool.execute(role="NonexistentRole")
        assert "No se encontraron personas con el cargo" in result3

    def test_sources_reset_between_searches(self):
        """
        Test that sources are reset between consecutive searches.

        Workflow:
        1. Execute first search with results
        2. Execute second search with results
        3. Verify sources from first search are cleared
        """
        # Setup: Mock store
        mock_store = Mock()
        mock_store.find_articles_by_person.return_value = [
            {"title": "Article", "link": "url"}
        ]
        mock_store.get_people_from_article.return_value = [
            {"nombre": "Person", "cargo": "Role", "organizacion": "", "datos_interes": ""}
        ]

        tool = PeopleSearchTool(mock_store)

        # Execute: First search
        tool.execute(person_name="Person1")
        first_sources = len(tool.last_sources)

        # Execute: Second search
        tool.execute(person_name="Person2")
        second_sources = len(tool.last_sources)

        # Verify: Sources were reset (should be same count, not accumulated)
        assert first_sources == second_sources


# ============================================================================
# TOOL MANAGER TESTS
# ============================================================================

class TestToolManager:
    """Test ToolManager functionality."""

    def test_register_tool(self):
        """
        Test that tools can be registered.

        Workflow:
        1. Create ToolManager
        2. Register a tool
        3. Verify tool is in registry
        """
        # Setup: Create manager and mock tool
        manager = ToolManager()
        mock_tool = Mock(spec=Tool)
        mock_tool.get_tool_definition.return_value = {
            "name": "test_tool",
            "description": "Test tool"
        }

        # Execute: Register tool
        manager.register_tool(mock_tool)

        # Verify: Tool is registered
        assert "test_tool" in manager.tools
        assert manager.tools["test_tool"] == mock_tool

    def test_register_tool_without_name_raises_error(self):
        """
        Test that registering tool without name raises error.

        Workflow:
        1. Create mock tool with no name in definition
        2. Try to register it
        3. Verify ValueError is raised
        """
        # Setup: Mock tool without name
        manager = ToolManager()
        mock_tool = Mock(spec=Tool)
        mock_tool.get_tool_definition.return_value = {
            "description": "No name tool"
        }

        # Execute & Verify: Should raise error
        with pytest.raises(ValueError, match="Tool must have a 'name'"):
            manager.register_tool(mock_tool)

    def test_get_tool_definitions(self):
        """
        Test that get_tool_definitions returns all registered tools.

        Workflow:
        1. Register multiple tools
        2. Get all definitions
        3. Verify all tool definitions are returned
        """
        # Setup: Register multiple tools
        manager = ToolManager()

        tool1 = Mock(spec=Tool)
        tool1.get_tool_definition.return_value = {"name": "tool1", "desc": "Tool 1"}

        tool2 = Mock(spec=Tool)
        tool2.get_tool_definition.return_value = {"name": "tool2", "desc": "Tool 2"}

        manager.register_tool(tool1)
        manager.register_tool(tool2)

        # Execute: Get definitions
        definitions = manager.get_tool_definitions()

        # Verify: All definitions returned
        assert len(definitions) == 2
        names = [d["name"] for d in definitions]
        assert "tool1" in names
        assert "tool2" in names

    def test_execute_tool(self):
        """
        Test that execute_tool calls the correct tool.

        Workflow:
        1. Register tool with execute method
        2. Call execute_tool
        3. Verify tool's execute was called with correct params
        """
        # Setup: Register tool
        manager = ToolManager()
        mock_tool = Mock(spec=Tool)
        mock_tool.get_tool_definition.return_value = {"name": "search_tool"}
        mock_tool.execute.return_value = "Search results"

        manager.register_tool(mock_tool)

        # Execute: Run tool
        result = manager.execute_tool("search_tool", query="test", limit=5)

        # Verify: Tool was executed with params
        mock_tool.execute.assert_called_once_with(query="test", limit=5)
        assert result == "Search results"

    def test_execute_nonexistent_tool(self):
        """
        Test that executing non-existent tool returns error message.

        Workflow:
        1. Try to execute tool that doesn't exist
        2. Verify error message is returned
        """
        # Setup: Empty manager
        manager = ToolManager()

        # Execute: Try to run non-existent tool
        result = manager.execute_tool("nonexistent_tool", param="value")

        # Verify: Error message returned
        assert "Tool 'nonexistent_tool' not found" in result

    def test_get_last_sources(self):
        """
        Test that get_last_sources retrieves sources from tools.

        Workflow:
        1. Register tool with last_sources attribute
        2. Set sources on tool
        3. Call get_last_sources
        4. Verify sources are returned
        """
        # Setup: Tool with sources
        manager = ToolManager()
        mock_tool = Mock(spec=Tool)
        mock_tool.get_tool_definition.return_value = {"name": "tool_with_sources"}
        mock_tool.last_sources = [{"text": "Source 1", "url": "url1", "index": 1}]

        manager.register_tool(mock_tool)

        # Execute: Get sources
        sources = manager.get_last_sources()

        # Verify: Sources returned
        assert len(sources) == 1
        assert sources[0]["text"] == "Source 1"

    def test_get_last_sources_empty_when_no_sources(self):
        """
        Test that get_last_sources returns empty list when no sources.

        Workflow:
        1. Register tool without sources
        2. Call get_last_sources
        3. Verify empty list returned
        """
        # Setup: Tool without sources
        manager = ToolManager()
        mock_tool = Mock(spec=Tool)
        mock_tool.get_tool_definition.return_value = {"name": "tool_no_sources"}
        mock_tool.last_sources = []

        manager.register_tool(mock_tool)

        # Execute: Get sources
        sources = manager.get_last_sources()

        # Verify: Empty list
        assert sources == []

    def test_reset_sources(self):
        """
        Test that reset_sources clears sources from all tools.

        Workflow:
        1. Register tools with sources
        2. Call reset_sources
        3. Verify all tool sources are cleared
        """
        # Setup: Tools with sources
        manager = ToolManager()

        tool1 = Mock(spec=Tool)
        tool1.get_tool_definition.return_value = {"name": "tool1"}
        tool1.last_sources = [{"text": "Source 1"}]

        tool2 = Mock(spec=Tool)
        tool2.get_tool_definition.return_value = {"name": "tool2"}
        tool2.last_sources = [{"text": "Source 2"}]

        manager.register_tool(tool1)
        manager.register_tool(tool2)

        # Execute: Reset sources
        manager.reset_sources()

        # Verify: All sources cleared
        assert tool1.last_sources == []
        assert tool2.last_sources == []


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestToolIntegration:
    """Test tools working together with ToolManager."""

    def test_article_search_tool_integration(self):
        """
        Test ArticleSearchTool integration with ToolManager.

        Workflow:
        1. Create ArticleSearchTool and register with manager
        2. Execute through manager
        3. Verify results and sources
        """
        # Setup: Create and register tool
        mock_store = Mock()
        search_results = SearchResults(
            documents=["Test content"],
            metadata=[{"article_title": "Integration Test"}],
            distances=[0.5],
            error=None
        )
        mock_store.search.return_value = search_results
        mock_store.get_article_link.return_value = "https://example.com/test"

        tool = ArticleSearchTool(mock_store)
        manager = ToolManager()
        manager.register_tool(tool)

        # Execute: Run through manager
        result = manager.execute_tool("search_news_content", query="test")

        # Verify: Works correctly
        assert "Integration Test" in result
        sources = manager.get_last_sources()
        assert len(sources) == 1
        assert sources[0]["text"] == "Art�culo: Integration Test"

    def test_people_search_tool_integration(self):
        """
        Test PeopleSearchTool integration with ToolManager.

        Workflow:
        1. Create PeopleSearchTool and register with manager
        2. Execute through manager
        3. Verify results and sources
        """
        # Setup: Create and register tool
        mock_store = Mock()
        mock_store.find_articles_by_person.return_value = [
            {"title": "Person Article", "link": "url"}
        ]
        mock_store.get_people_from_article.return_value = [
            {"nombre": "Test Person", "cargo": "Role", "organizacion": "", "datos_interes": ""}
        ]

        tool = PeopleSearchTool(mock_store)
        manager = ToolManager()
        manager.register_tool(tool)

        # Execute: Run through manager
        result = manager.execute_tool("search_people_in_articles", person_name="Test Person")

        # Verify: Works correctly
        assert "Test Person" in result
        sources = manager.get_last_sources()
        assert len(sources) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
