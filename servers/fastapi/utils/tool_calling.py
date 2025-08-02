import json
import logging
from typing import List, Dict, Any, Optional, Callable
from services.web_search_service import web_search_service
from services.source_citation_service import citation_service

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry for LLM tools that can be called during presentation generation"""
    
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.tool_functions: Dict[str, Callable] = {}
        self.current_presentation_id: Optional[str] = None
        self._register_default_tools()
    
    def set_presentation_context(self, presentation_id: str):
        """Set the current presentation context for citation tracking"""
        self.current_presentation_id = presentation_id
    
    def _register_default_tools(self):
        """Register default tools available for LLM"""
        
        # Web search tool
        self.register_tool(
            name="web_search",
            description="Search the web for current information, facts, statistics, or recent developments on a topic",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant information"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            },
            function=self._web_search_tool
        )
    
    def register_tool(self, name: str, description: str, parameters: Dict[str, Any], function: Callable):
        """Register a new tool"""
        self.tools[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        }
        self.tool_functions[name] = function
        logger.info(f"Registered tool: {name}")
    
    async def _web_search_tool(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Web search tool implementation with citation tracking"""
        try:
            results = await web_search_service.comprehensive_search(query, max_results)
            
            if not results:
                return {
                    "success": False,
                    "message": "No search results found",
                    "results": []
                }
            
            # Add citations to presentation if context is available
            if self.current_presentation_id:
                citation_service.add_search_results_to_presentation(
                    self.current_presentation_id, results, query
                )
                logger.info(f"WEB SEARCH EXECUTED - Query: '{query}' | Results: {len(results)} | Presentation: {self.current_presentation_id}")
            
            # Format results for LLM consumption
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "content": result.get("content", "")[:500],  # Limit content length
                    "source": result.get("source", ""),
                    "url": result.get("url", "")
                })
            
            return {
                "success": True,
                "message": f"Found {len(formatted_results)} search results",
                "results": formatted_results
            }
            
        except Exception as e:
            logger.error(f"Web search tool error: {e}")
            return {
                "success": False,
                "message": f"Search failed: {str(e)}",
                "results": []
            }
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible tools schema"""
        return list(self.tools.values())
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments"""
        if tool_name not in self.tool_functions:
            return {
                "success": False,
                "message": f"Tool '{tool_name}' not found",
                "results": []
            }
        
        try:
            tool_function = self.tool_functions[tool_name]
            result = await tool_function(**arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution error for '{tool_name}': {e}")
            return {
                "success": False,
                "message": f"Tool execution failed: {str(e)}",
                "results": []
            }

# Global tool registry instance
tool_registry = ToolRegistry()

async def handle_tool_calls(tool_calls: List[Any]) -> List[Dict[str, Any]]:
    """
    Handle tool calls from LLM response
    Returns list of tool results
    """
    results = []
    
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool arguments: {e}")
            results.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": json.dumps({
                    "success": False,
                    "message": "Invalid tool arguments",
                    "results": []
                })
            })
            continue
        
        # Execute the tool
        tool_result = await tool_registry.execute_tool(tool_name, arguments)
        
        results.append({
            "tool_call_id": tool_call.id,
            "role": "tool", 
            "content": json.dumps(tool_result)
        })
    
    return results

def should_use_web_search(prompt: str) -> bool:
    """
    Determine if web search should be used based on the prompt content
    """
    web_search_indicators = [
        "current", "recent", "latest", "2024", "2025", "today",
        "statistics", "data", "facts", "trends", "market",
        "news", "updates", "developments", "what is happening",
        "research", "study", "report", "analysis"
    ]
    
    prompt_lower = prompt.lower()
    
    # Check if prompt contains indicators that suggest current information is needed
    for indicator in web_search_indicators:
        if indicator in prompt_lower:
            return True
    
    return False