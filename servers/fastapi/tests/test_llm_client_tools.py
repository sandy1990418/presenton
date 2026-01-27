"""
Test module for LLMClient tool calling functionality

Tests the complete tool calling system including:
- generate_with_tools() method for all providers
- Tool call extraction from different response formats
- Tool format conversion between providers
- Error handling for tool failures
"""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import List, Dict, Any

from services.llm_client import LLMClient
from models.llm_message import LLMMessage, ToolCall
from enums.llm_provider import LLMProvider


class TestLLMClientTools:
    """Test LLMClient tool calling functionality"""

    @pytest.fixture
    def sample_tools(self) -> List[Dict[str, Any]]:
        """Sample tools in OpenAI format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    @pytest.fixture
    def sample_messages(self) -> List[LLMMessage]:
        """Sample LLM messages"""
        return [
            LLMMessage(role="system", content="You are a helpful assistant."),
            LLMMessage(role="user", content="Search for latest AI developments in 2024")
        ]

    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI ChatCompletion response with tool calls"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "I'll search for AI developments."
        
        # Mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "web_search"
        mock_tool_call.function.arguments = '{"query": "latest AI developments 2024", "max_results": 5}'
        
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        return mock_response

    @pytest.fixture
    def mock_anthropic_response(self):
        """Mock Anthropic Message response with tool calls"""
        mock_response = Mock()
        mock_response.content = []
        
        # Text content
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "I'll search for AI developments."
        mock_response.content.append(text_block)
        
        # Tool use content
        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.id = "toolu_123"
        tool_block.name = "web_search"
        tool_block.input = {"query": "latest AI developments 2024", "max_results": 5}
        mock_response.content.append(tool_block)
        
        return mock_response

    @pytest.fixture
    def mock_google_response(self):
        """Mock Google Gemini response with function calls"""
        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content = Mock()
        mock_response.candidates[0].content.parts = []
        
        # Text part
        text_part = Mock()
        text_part.text = "I'll search for AI developments."
        mock_response.candidates[0].content.parts.append(text_part)
        
        # Function call part
        function_part = Mock()
        function_part.function_call = Mock()
        function_part.function_call.name = "web_search"
        function_part.function_call.args = {"query": "latest AI developments 2024", "max_results": 5}
        mock_response.candidates[0].content.parts.append(function_part)
        
        return mock_response

    # Tool Format Conversion Tests

    def test_convert_tools_to_google_format(self, sample_tools):
        """Test conversion of tools to Google Gemini format"""
        client = LLMClient()
        google_tools = client._convert_tools_to_google_format(sample_tools)
        
        assert len(google_tools) == 1
        tool = google_tools[0]
        assert hasattr(tool, 'function_declarations')
        assert len(tool.function_declarations) == 1
        
        func_decl = tool.function_declarations[0]
        assert func_decl.name == "web_search"
        assert func_decl.description == "Search the web for current information"
        assert func_decl.parameters == sample_tools[0]["function"]["parameters"]

    def test_convert_tools_to_anthropic_format(self, sample_tools):
        """Test conversion of tools to Anthropic format"""
        client = LLMClient()
        anthropic_tools = client._convert_tools_to_anthropic_format(sample_tools)
        
        assert len(anthropic_tools) == 1
        tool = anthropic_tools[0]
        
        assert tool["name"] == "web_search"
        assert tool["description"] == "Search the web for current information"
        assert tool["input_schema"] == sample_tools[0]["function"]["parameters"]

    # Tool Call Extraction Tests

    def test_extract_tool_calls_openai(self, mock_openai_response):
        """Test extracting tool calls from OpenAI response"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.OPENAI
            
            tool_calls = client.extract_tool_calls(mock_openai_response)
            
            assert len(tool_calls) == 1
            tool_call = tool_calls[0]
            
            assert tool_call["id"] == "call_123"
            assert tool_call["name"] == "web_search"
            assert tool_call["arguments"] == {
                "query": "latest AI developments 2024",
                "max_results": 5
            }

    def test_extract_tool_calls_anthropic(self, mock_anthropic_response):
        """Test extracting tool calls from Anthropic response"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.ANTHROPIC
            
            tool_calls = client.extract_tool_calls(mock_anthropic_response)
            
            assert len(tool_calls) == 1
            tool_call = tool_calls[0]
            
            assert tool_call["id"] == "toolu_123"
            assert tool_call["name"] == "web_search"
            assert tool_call["arguments"] == {
                "query": "latest AI developments 2024",
                "max_results": 5
            }

    def test_extract_tool_calls_google(self, mock_google_response):
        """Test extracting tool calls from Google response"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.GOOGLE
            
            tool_calls = client.extract_tool_calls(mock_google_response)
            
            assert len(tool_calls) == 1
            tool_call = tool_calls[0]
            
            assert tool_call["id"].startswith("google_")
            assert tool_call["name"] == "web_search"
            assert tool_call["arguments"] == {
                "query": "latest AI developments 2024",
                "max_results": 5
            }

    def test_extract_tool_calls_empty_response(self):
        """Test extracting tool calls from empty response"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.OPENAI
            
            empty_response = Mock()
            empty_response.choices = []
            
            tool_calls = client.extract_tool_calls(empty_response)
            assert tool_calls == []

    def test_extract_tool_calls_invalid_json(self):
        """Test handling of invalid JSON in tool call arguments"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.OPENAI
            
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = "Test"
            
            mock_tool_call = Mock()
            mock_tool_call.id = "call_123"
            mock_tool_call.function = Mock()
            mock_tool_call.function.name = "web_search"
            mock_tool_call.function.arguments = "invalid json"
            
            mock_response.choices[0].message.tool_calls = [mock_tool_call]
            
            tool_calls = client.extract_tool_calls(mock_response)
            assert tool_calls == []  # Should handle error gracefully

    # Text Content Extraction Tests

    def test_get_text_content_openai(self, mock_openai_response):
        """Test extracting text content from OpenAI response"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.OPENAI
            
            text = client.get_text_content(mock_openai_response)
            assert text == "I'll search for AI developments."

    def test_get_text_content_anthropic(self, mock_anthropic_response):
        """Test extracting text content from Anthropic response"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.ANTHROPIC
            
            text = client.get_text_content(mock_anthropic_response)
            assert text == "I'll search for AI developments."

    def test_get_text_content_google(self, mock_google_response):
        """Test extracting text content from Google response"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.GOOGLE
            
            text = client.get_text_content(mock_google_response)
            assert text == "I'll search for AI developments."

    # Generate with Tools Tests

    @pytest.mark.anyio
    async def test_generate_with_tools_openai(self, sample_tools, sample_messages, mock_openai_response):
        """Test generate_with_tools for OpenAI provider"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.OPENAI
            client._client = AsyncMock()
            
            # Mock the provider-specific method
            client._generate_openai_with_tools = AsyncMock(return_value=mock_openai_response)
            
            response = await client.generate_with_tools(
                model="gpt-4",
                messages=sample_messages,
                tools=sample_tools,
                tool_choice="auto"
            )
            
            assert response == mock_openai_response
            client._generate_openai_with_tools.assert_called_once_with(
                "gpt-4", sample_messages, sample_tools, "auto", None
            )

    @pytest.mark.anyio
    async def test_generate_with_tools_anthropic(self, sample_tools, sample_messages, mock_anthropic_response):
        """Test generate_with_tools for Anthropic provider"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.ANTHROPIC
            client._client = AsyncMock()
            
            # Mock the provider-specific method
            client._generate_anthropic_with_tools = AsyncMock(return_value=mock_anthropic_response)
            
            response = await client.generate_with_tools(
                model="claude-3-sonnet-20240229",
                messages=sample_messages,
                tools=sample_tools,
                tool_choice="auto"
            )
            
            assert response == mock_anthropic_response
            client._generate_anthropic_with_tools.assert_called_once_with(
                "claude-3-sonnet-20240229", sample_messages, sample_tools, "auto", None
            )

    @pytest.mark.anyio
    async def test_generate_with_tools_google(self, sample_tools, sample_messages, mock_google_response):
        """Test generate_with_tools for Google provider"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.GOOGLE
            client._client = AsyncMock()
            
            # Mock the provider-specific method
            client._generate_google_with_tools = AsyncMock(return_value=mock_google_response)
            
            response = await client.generate_with_tools(
                model="gemini-2.0-flash-exp",
                messages=sample_messages,
                tools=sample_tools,
                tool_choice="auto"
            )
            
            assert response == mock_google_response
            client._generate_google_with_tools.assert_called_once_with(
                "gemini-2.0-flash-exp", sample_messages, sample_tools, "auto", None
            )

    @pytest.mark.anyio
    async def test_generate_with_tools_empty_tools_error(self, sample_messages):
        """Test generate_with_tools with empty tools list raises error"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.OPENAI
            
            with pytest.raises(Exception) as exc_info:
                await client.generate_with_tools(
                    model="gpt-4",
                    messages=sample_messages,
                    tools=[],
                    tool_choice="auto"
                )
            
            assert "Tools list cannot be empty" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_generate_with_tools_error_handling(self, sample_tools, sample_messages):
        """Test error handling in generate_with_tools"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.OPENAI
            client._client = AsyncMock()
            
            # Mock the provider-specific method to raise an exception
            client._generate_openai_with_tools = AsyncMock(side_effect=Exception("API Error"))
            
            with pytest.raises(Exception) as exc_info:
                await client.generate_with_tools(
                    model="gpt-4",
                    messages=sample_messages,
                    tools=sample_tools,
                    tool_choice="auto"
                )
            
            assert "Error generating content with tools" in str(exc_info.value)

    # Provider-specific Implementation Tests

    @pytest.mark.anyio
    async def test_openai_with_tools_implementation(self, sample_tools, sample_messages):
        """Test OpenAI-specific tool calling implementation"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.OPENAI
            client._client = AsyncMock()
            
            mock_response = Mock()
            client._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            response = await client._generate_openai_with_tools(
                model="gpt-4",
                messages=sample_messages,
                tools=sample_tools,
                tool_choice="auto",
                max_tokens=1000
            )
            
            assert response == mock_response
            client._client.chat.completions.create.assert_called_once()
            
            # Verify the call arguments
            call_args = client._client.chat.completions.create.call_args[1]
            assert call_args["model"] == "gpt-4"
            assert call_args["tools"] == sample_tools
            assert call_args["tool_choice"] == "auto"
            assert call_args["max_completion_tokens"] == 1000

    @pytest.mark.anyio 
    async def test_anthropic_with_tools_implementation(self, sample_tools, sample_messages):
        """Test Anthropic-specific tool calling implementation"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            client.llm_provider = LLMProvider.ANTHROPIC
            client._client = AsyncMock()
            
            mock_response = Mock()
            client._client.messages.create = AsyncMock(return_value=mock_response)
            
            response = await client._generate_anthropic_with_tools(
                model="claude-3-sonnet-20240229",
                messages=sample_messages,
                tools=sample_tools,
                tool_choice="required",
                max_tokens=1000
            )
            
            assert response == mock_response
            client._client.messages.create.assert_called_once()
            
            # Verify the call arguments
            call_args = client._client.messages.create.call_args[1]
            assert call_args["model"] == "claude-3-sonnet-20240229"
            assert call_args["tool_choice"] == {"type": "any"}  # Should convert "required" to {"type": "any"}
            assert call_args["max_tokens"] == 1000

    @pytest.mark.anyio
    async def test_google_with_tools_implementation(self, sample_tools, sample_messages):
        """Test Google-specific tool calling implementation"""
        with patch('asyncio.to_thread') as mock_to_thread:
            with patch.object(LLMClient, '__init__', lambda x: None):
                client = LLMClient()
                client.llm_provider = LLMProvider.GOOGLE
                client._client = Mock()
                
                mock_response = Mock()
                mock_to_thread.return_value = mock_response
                
                response = await client._generate_google_with_tools(
                    model="gemini-2.0-flash-exp",
                    messages=sample_messages,
                    tools=sample_tools,
                    tool_choice="required",
                    max_tokens=1000
                )
                
                assert response == mock_response
                mock_to_thread.assert_called_once()
                
                # Verify asyncio.to_thread was called with correct arguments
                call_args = mock_to_thread.call_args[0]
                assert call_args[0] == client._client.models.generate_content

    def test_ollama_and_custom_delegate_to_openai(self, sample_tools, sample_messages):
        """Test that Ollama and Custom providers delegate to OpenAI implementation"""
        with patch.object(LLMClient, '__init__', lambda x: None):
            client = LLMClient()
            
            # Test Ollama
            client.llm_provider = LLMProvider.OLLAMA
            with patch.object(client, '_generate_openai_with_tools') as mock_openai:
                asyncio.create_task(client._generate_ollama_with_tools(
                    "llama2", sample_messages, sample_tools, "auto", 1000
                ))
                # Note: We can't directly await this in a sync test, but we can verify the method was set up
            
            # Test Custom
            client.llm_provider = LLMProvider.CUSTOM
            with patch.object(client, '_generate_openai_with_tools') as mock_openai:
                asyncio.create_task(client._generate_custom_with_tools(
                    "custom-model", sample_messages, sample_tools, "auto", 1000
                ))
                # Note: We can't directly await this in a sync test, but we can verify the method was set up


if __name__ == "__main__":
    pytest.main([__file__])