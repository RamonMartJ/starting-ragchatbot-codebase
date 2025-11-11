"""
Unit tests for AIGenerator class.

Tests cover:
- Response generation without tools
- Response generation with tools (autonomous tool calling)
- Two-phase tool execution workflow
- Tool result handling
- Error handling
- System prompt and conversation history

Run with: pytest tests/unit/test_ai_generator.py -v
"""

from unittest.mock import Mock, patch

import pytest
from ai_generator import AIGenerator

# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


class TestAIGeneratorInitialization:
    """Test AIGenerator initialization."""

    def test_initialization(self):
        """
        Verify AIGenerator initializes correctly.

        Workflow:
        1. Create AIGenerator with API key and model
        2. Verify client and model are set
        3. Verify base_params are configured
        """
        # Execute: Initialize generator
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="claude-3-sonnet")

        # Verify: Initialization correct
        assert generator.model == "claude-3-sonnet"
        assert generator.base_params["model"] == "claude-3-sonnet"
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800

    def test_system_prompt_exists(self):
        """
        Verify AIGenerator has static system prompt.

        Workflow:
        1. Check SYSTEM_PROMPT class variable exists
        2. Verify it contains key instructions
        """
        # Verify: System prompt exists and has content
        assert hasattr(AIGenerator, "SYSTEM_PROMPT")
        assert len(AIGenerator.SYSTEM_PROMPT) > 0
        assert "herramientas" in AIGenerator.SYSTEM_PROMPT.lower()


# ============================================================================
# RESPONSE GENERATION TESTS (NO TOOLS)
# ============================================================================


class TestGenerateResponseNoTools:
    """Test response generation without tools."""

    def test_generate_response_without_tools(self, mock_anthropic_response):
        """
        Test generate_response without tools returns direct response.

        Workflow:
        1. Mock Anthropic client to return text response
        2. Generate response without tools
        3. Verify response text is returned
        """
        # Setup: Mock client
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Execute: Generate response
            result = generator.generate_response(query="What is AI?")

        # Verify: Response returned
        assert result == "This is a test response from Claude"
        mock_client.messages.create.assert_called_once()

    def test_generate_response_with_conversation_history(self, mock_anthropic_response):
        """
        Test that conversation history is included in system prompt.

        Workflow:
        1. Mock client
        2. Generate response with history
        3. Verify system content includes history
        """
        # Setup: Mock client
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Execute: Generate with history
            history = "User: Previous question\nAssistant: Previous answer"
            _result = generator.generate_response(
                query="New question", conversation_history=history
            )

        # Verify: History was included in system prompt
        call_args = mock_client.messages.create.call_args
        system_content = call_args.kwargs.get("system")
        assert "Previous conversation:" in system_content
        assert history in system_content

    def test_generate_response_includes_query_in_messages(
        self, mock_anthropic_response
    ):
        """
        Test that user query is included in messages.

        Workflow:
        1. Mock client
        2. Generate response
        3. Verify messages contain user query
        """
        # Setup: Mock client
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Execute: Generate response
            _result = generator.generate_response(query="Test query")

        # Verify: Query in messages
        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs.get("messages")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Test query"


# ============================================================================
# RESPONSE GENERATION WITH TOOLS (NO TOOL USE)
# ============================================================================


class TestGenerateResponseWithToolsNoUse:
    """Test response generation with tools available but not used."""

    def test_generate_response_with_tools_but_no_use(self, mock_anthropic_response):
        """
        Test generate_response when tools are available but Claude doesn't use them.

        Workflow:
        1. Mock client to return text response (not tool_use)
        2. Provide tools to generator
        3. Verify response is returned directly without tool execution
        """
        # Setup: Mock client with text response
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Mock tool and manager
            mock_tool_manager = Mock()
            tools = [{"name": "test_tool", "description": "A test tool"}]

            # Execute: Generate with tools
            result = generator.generate_response(
                query="General knowledge question",
                tools=tools,
                tool_manager=mock_tool_manager,
            )

        # Verify: Response returned, no tool execution
        assert result == "This is a test response from Claude"
        mock_tool_manager.execute_tool.assert_not_called()

    def test_tools_included_in_api_call(self, mock_anthropic_response):
        """
        Test that tools are included in API call when provided.

        Workflow:
        1. Mock client
        2. Generate response with tools
        3. Verify tools and tool_choice in API params
        """
        # Setup: Mock client
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Prepare tools
            tools = [{"name": "search_tool", "description": "Search tool"}]

            # Execute: Generate with tools
            _result = generator.generate_response(query="Test", tools=tools)

        # Verify: Tools in API call
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs.get("tools") == tools
        assert call_args.kwargs.get("tool_choice") == {"type": "auto"}


# ============================================================================
# TOOL EXECUTION TESTS (TWO-PHASE)
# ============================================================================


class TestToolExecution:
    """Test two-phase tool execution workflow."""

    def test_generate_response_with_tool_use(
        self, mock_anthropic_tool_use_response, mock_anthropic_response
    ):
        """
        Test generate_response when Claude uses tools (two-phase workflow).

        Workflow:
        1. Mock first API call to return tool_use
        2. Mock tool execution
        3. Mock second API call to return final response
        4. Verify both phases execute correctly
        """
        # Setup: Mock client with two-phase responses
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # First call returns tool_use, second returns text
            mock_client.messages.create.side_effect = [
                mock_anthropic_tool_use_response,
                mock_anthropic_response,
            ]
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Mock tool manager
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.return_value = "Tool execution result"

            tools = [{"name": "search_news_content", "description": "Search tool"}]

            # Execute: Generate response with tool use
            result = generator.generate_response(
                query="Question requiring search",
                tools=tools,
                tool_manager=mock_tool_manager,
            )

        # Verify: Tool was executed and final response returned
        mock_tool_manager.execute_tool.assert_called_once()
        assert result == "This is a test response from Claude"
        assert mock_client.messages.create.call_count == 2

    def test_tool_execution_passes_correct_parameters(
        self, mock_anthropic_tool_use_response
    ):
        """
        Test that tool execution receives correct parameters from Claude.

        Workflow:
        1. Mock tool_use response with specific parameters
        2. Execute generation
        3. Verify tool_manager.execute_tool called with correct params
        """
        # Setup: Mock responses
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # Configure tool_use response with parameters
            tool_use_response = Mock()
            tool_use_response.stop_reason = "tool_use"

            tool_block = Mock()
            tool_block.type = "tool_use"
            tool_block.name = "search_news_content"
            tool_block.id = "tool_123"
            tool_block.input = {"query": "test search", "article_title": "Test Article"}

            tool_use_response.content = [tool_block]

            # Second response
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_text = Mock()
            final_text.text = "Final answer"
            final_response.content = [final_text]

            mock_client.messages.create.side_effect = [
                tool_use_response,
                final_response,
            ]
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Mock tool manager
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.return_value = "Search results"

            tools = [{"name": "search_news_content"}]

            # Execute: Generate
            _result = generator.generate_response(
                query="Test query", tools=tools, tool_manager=mock_tool_manager
            )

        # Verify: Tool called with correct parameters
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_news_content", query="test search", article_title="Test Article"
        )

    def test_multiple_tool_uses_in_single_response(self):
        """
        Test that multiple tool uses are handled correctly.

        Workflow:
        1. Mock response with multiple tool_use blocks
        2. Execute generation
        3. Verify all tools are executed
        """
        # Setup: Mock multiple tool uses
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # First response with multiple tools
            tool_use_response = Mock()
            tool_use_response.stop_reason = "tool_use"

            tool1 = Mock()
            tool1.type = "tool_use"
            tool1.name = "tool1"
            tool1.id = "tool_1"
            tool1.input = {"param": "value1"}

            tool2 = Mock()
            tool2.type = "tool_use"
            tool2.name = "tool2"
            tool2.id = "tool_2"
            tool2.input = {"param": "value2"}

            tool_use_response.content = [tool1, tool2]

            # Final response
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_text = Mock()
            final_text.text = "Final result"
            final_response.content = [final_text]

            mock_client.messages.create.side_effect = [
                tool_use_response,
                final_response,
            ]
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Mock tool manager
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.side_effect = ["Result 1", "Result 2"]

            tools = [{"name": "tool1"}, {"name": "tool2"}]

            # Execute: Generate
            _result = generator.generate_response(
                query="Test", tools=tools, tool_manager=mock_tool_manager
            )

        # Verify: Both tools executed
        assert mock_tool_manager.execute_tool.call_count == 2

    def test_tool_results_included_in_second_api_call(
        self, mock_anthropic_tool_use_response
    ):
        """
        Test that tool results are included in second API call.

        Workflow:
        1. Mock tool_use and execution
        2. Execute generation
        3. Verify second API call includes tool results
        """
        # Setup: Mock responses
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # Final response
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_text = Mock()
            final_text.text = "Answer with tool results"
            final_response.content = [final_text]

            mock_client.messages.create.side_effect = [
                mock_anthropic_tool_use_response,
                final_response,
            ]
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Mock tool manager
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.return_value = "Tool result content"

            tools = [{"name": "search_news_content"}]

            # Execute: Generate
            _result = generator.generate_response(
                query="Test", tools=tools, tool_manager=mock_tool_manager
            )

        # Verify: Second API call includes tool results
        second_call = mock_client.messages.create.call_args_list[1]
        messages = second_call.kwargs.get("messages")

        # Should have: user message, assistant with tool_use, user with tool_results
        assert len(messages) == 3
        assert messages[2]["role"] == "user"
        assert any("tool_result" in str(content) for content in messages[2]["content"])


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test error handling in AIGenerator."""

    def test_generate_response_handles_api_error(self):
        """
        Test that API errors are handled and raised.

        Workflow:
        1. Mock client to raise exception
        2. Try to generate response
        3. Verify exception is raised
        """
        # Setup: Mock client with error
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API Error")
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Execute & Verify: Exception raised
            with pytest.raises(Exception, match="API Error"):
                generator.generate_response(query="Test")

    def test_tool_execution_handles_errors(self):
        """
        Test that errors during tool execution are handled.

        Workflow:
        1. Mock tool_use response
        2. Mock tool execution to raise error
        3. Verify error is handled properly
        """
        # Setup: Mock tool error
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = Mock(
                stop_reason="tool_use",
                content=[
                    Mock(type="tool_use", name="test_tool", id="tool_1", input={})
                ],
            )
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Mock tool manager with error
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.side_effect = Exception(
                "Tool execution failed"
            )

            tools = [{"name": "test_tool"}]

            # Execute & Verify: Exception raised
            with pytest.raises(Exception, match="Tool execution failed"):
                generator.generate_response(
                    query="Test", tools=tools, tool_manager=mock_tool_manager
                )


# ============================================================================
# BASE PARAMETERS TESTS
# ============================================================================


class TestBaseParameters:
    """Test that base parameters are used correctly."""

    def test_base_params_applied_to_api_call(self, mock_anthropic_response):
        """
        Test that base_params (temperature, max_tokens) are applied.

        Workflow:
        1. Initialize AIGenerator
        2. Generate response
        3. Verify base_params in API call
        """
        # Setup: Mock client
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Execute: Generate response
            _result = generator.generate_response(query="Test")

        # Verify: Base params in call
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs.get("temperature") == 0
        assert call_args.kwargs.get("max_tokens") == 800
        assert call_args.kwargs.get("model") == "test-model"

    def test_system_prompt_always_included(self, mock_anthropic_response):
        """
        Test that system prompt is always included in API calls.

        Workflow:
        1. Generate response without history
        2. Generate response with history
        3. Verify system prompt in both calls
        """
        # Setup: Mock client
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")

            # Execute: Without history
            generator.generate_response(query="Test 1")
            call1_system = mock_client.messages.create.call_args.kwargs.get("system")

            # Execute: With history
            generator.generate_response(
                query="Test 2", conversation_history="Previous conversation"
            )
            call2_system = mock_client.messages.create.call_args.kwargs.get("system")

        # Verify: System prompt in both
        assert AIGenerator.SYSTEM_PROMPT in call1_system
        assert AIGenerator.SYSTEM_PROMPT in call2_system


# ============================================================================
# SEQUENTIAL TOOL CALLING TESTS (NEW)
# ============================================================================


class TestSequentialToolCalling:
    """Test sequential tool calling capability (up to 2 rounds)."""

    def test_two_sequential_tool_calls(self):
        """
        Test that Claude can make 2 sequential tool calls.

        Workflow:
        1. First API call → tool_use (round 1)
        2. Execute tools → add results to messages
        3. Second API call → tool_use (round 2)
        4. Execute tools → add results to messages
        5. Third API call → text response (final)
        6. Verify 3 API calls made and correct response returned
        """
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # Round 1: tool_use
            round1_response = Mock()
            round1_response.stop_reason = "tool_use"
            round1_tool = Mock(
                type="tool_use",
                name="search_people_in_articles",
                id="t1",
                input={"role": "Periodista"},
            )
            round1_response.content = [round1_tool]

            # Round 2: tool_use
            round2_response = Mock()
            round2_response.stop_reason = "tool_use"
            round2_tool = Mock(
                type="tool_use",
                name="search_news_content",
                id="t2",
                input={"query": "Maribel Vilaplana"},
            )
            round2_response.content = [round2_tool]

            # Round 3: final answer
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_text = Mock()
            final_text.text = "Combined answer from both searches"
            final_response.content = [final_text]

            mock_client.messages.create.side_effect = [
                round1_response,
                round2_response,
                final_response,
            ]
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.side_effect = [
                "Result from search_people",
                "Result from search_content",
            ]

            tools = [
                {"name": "search_people_in_articles"},
                {"name": "search_news_content"},
            ]

            # Execute
            result = generator.generate_response(
                query="Complex query requiring multiple searches",
                tools=tools,
                tool_manager=mock_tool_manager,
            )

            # Verify
            assert result == "Combined answer from both searches"
            assert mock_client.messages.create.call_count == 3
            assert mock_tool_manager.execute_tool.call_count == 2

    def test_max_rounds_enforced(self):
        """
        Test that tool calling stops after 2 rounds.

        Workflow:
        1. Round 1: tool_use
        2. Round 2: tool_use
        3. Force final call without tools
        4. Verify exactly 3 API calls (2 tool rounds + 1 final)
        """
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # Both rounds return tool_use
            tool_response = Mock()
            tool_response.stop_reason = "tool_use"
            tool_block = Mock(type="tool_use", name="tool", id="t", input={})
            tool_response.content = [tool_block]

            # Final response
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_text = Mock()
            final_text.text = "Final answer after max rounds"
            final_response.content = [final_text]

            mock_client.messages.create.side_effect = [
                tool_response,  # Round 1
                tool_response,  # Round 2
                final_response,  # Forced final
            ]
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.return_value = "Tool result"

            # Execute
            result = generator.generate_response(
                query="Query", tools=[{"name": "tool"}], tool_manager=mock_tool_manager
            )

            # Verify: 3 calls total, final call has no tools
            assert mock_client.messages.create.call_count == 3
            assert result == "Final answer after max rounds"

            # Check last call had tools=None (forced final)
            last_call = mock_client.messages.create.call_args_list[2]
            assert last_call.kwargs.get("tools") is None

    def test_early_termination_no_tool_use(self):
        """
        Test early termination when Claude doesn't use tools.

        Workflow:
        1. Round 1: text response (no tool_use)
        2. Should terminate immediately
        3. Verify only 1 API call made
        """
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            response = Mock()
            response.stop_reason = "end_turn"
            text = Mock()
            text.text = "Direct answer without tools"
            response.content = [text]

            mock_client.messages.create.return_value = response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")
            mock_tool_manager = Mock()

            # Execute
            result = generator.generate_response(
                query="Simple question",
                tools=[{"name": "tool"}],
                tool_manager=mock_tool_manager,
            )

            # Verify: Only 1 API call, no tool execution
            assert result == "Direct answer without tools"
            assert mock_client.messages.create.call_count == 1
            mock_tool_manager.execute_tool.assert_not_called()

    def test_message_accumulation_across_rounds(self):
        """
        Test that messages accumulate correctly across tool rounds.

        Workflow:
        1. Verify initial messages: [user_query]
        2. After round 1: [user, assistant_tool, user_results]
        3. After round 2: [user, asst_tool1, user_res1, asst_tool2, user_res2]

        Note: We capture message state at each call by making copies,
        since the messages list is mutated in place.
        """
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # Storage for captured message states
            captured_messages = []

            # Round 1
            r1 = Mock(stop_reason="tool_use")
            r1.content = [Mock(type="tool_use", name="t1", id="1", input={})]

            # Round 2
            r2 = Mock(stop_reason="tool_use")
            r2.content = [Mock(type="tool_use", name="t2", id="2", input={})]

            # Final
            r3 = Mock(stop_reason="end_turn")
            r3.content = [Mock(text="Done")]

            def capture_messages(**kwargs):
                # Capture a COPY of messages at this call
                captured_messages.append(len(kwargs.get("messages", [])))
                # Return appropriate response based on call count
                if len(captured_messages) == 1:
                    return r1
                elif len(captured_messages) == 2:
                    return r2
                else:
                    return r3

            mock_client.messages.create.side_effect = capture_messages
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.return_value = "Result"

            # Execute
            generator.generate_response(
                query="Query",
                tools=[{"name": "t1"}, {"name": "t2"}],
                tool_manager=mock_tool_manager,
            )

            # Verify message progression using captured states
            assert captured_messages[0] == 1  # Call 1: Initial user query
            assert captured_messages[1] == 3  # Call 2: user, asst_tool, user_results
            assert captured_messages[2] == 5  # Call 3: Full conversation

    def test_tool_execution_error_fail_fast(self):
        """
        Test that tool execution errors propagate immediately (fail-fast).

        Workflow:
        1. Round 1: tool_use
        2. Tool execution raises exception
        3. Verify exception is propagated immediately
        4. Verify no further API calls are made
        """
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # Round 1: tool_use
            tool_response = Mock()
            tool_response.stop_reason = "tool_use"
            tool_block = Mock(type="tool_use", name="tool", id="t1", input={})
            tool_response.content = [tool_block]

            mock_client.messages.create.return_value = tool_response
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.side_effect = Exception("Tool failed")

            # Execute & Verify: Exception propagated
            with pytest.raises(Exception, match="Tool failed"):
                generator.generate_response(
                    query="Query",
                    tools=[{"name": "tool"}],
                    tool_manager=mock_tool_manager,
                )

            # Verify: Only 1 API call (no second round after error)
            assert mock_client.messages.create.call_count == 1

    def test_adaptive_system_prompt(self):
        """
        Test that system prompts adapt based on round number.

        Workflow:
        1. Execute query that triggers 2 rounds
        2. Verify round 1 uses "[Ronda 1/2]" prompt
        3. Verify round 2 uses "[Ronda 2/2 - FINAL]" prompt
        """
        with patch("ai_generator.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()

            # Round 1: tool_use
            r1 = Mock(stop_reason="tool_use")
            r1.content = [Mock(type="tool_use", name="tool", id="1", input={})]

            # Round 2: text response
            r2 = Mock(stop_reason="end_turn")
            r2.content = [Mock(text="Final answer")]

            mock_client.messages.create.side_effect = [r1, r2]
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(api_key="test-key", model="test-model")
            mock_tool_manager = Mock()
            mock_tool_manager.execute_tool.return_value = "Result"

            # Execute
            generator.generate_response(
                query="Query", tools=[{"name": "tool"}], tool_manager=mock_tool_manager
            )

            # Verify: Round 1 system prompt
            call1_system = mock_client.messages.create.call_args_list[0].kwargs[
                "system"
            ]
            assert "[Ronda 1/2]" in call1_system

            # Verify: Round 2 system prompt
            call2_system = mock_client.messages.create.call_args_list[1].kwargs[
                "system"
            ]
            assert "[Ronda 2/2 - FINAL]" in call2_system


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
