import logging
from typing import Optional
from google.genai.types import GenerateContentConfig
from openai.types.chat.chat_completion_chunk import ChoiceDelta

from utils.async_iterator import iterator_to_async
from utils.get_dynamic_models import get_presentation_outline_model_with_n_slides
from utils.llm_provider import (
    get_google_llm_client,
    get_large_model,
    get_llm_client,
    is_google_selected,
)
from utils.tool_calling import tool_registry, handle_tool_calls, should_use_web_search
from pydantic import BaseModel

logger = logging.getLogger(__name__)

system_prompt = """
You are an expert presentation creator. Generate structured presentations based on user requirements and format them according to the specified JSON schema with markdown content.

## Core Requirements

### Input Processing
1. **Extract key information** from the user's prompt:
   - Main topic/subject matter
   - Required number of slides
   - Target language for output
   - Specific content requirements or focus areas
   - Target audience (if specified)
   - Presentation style or tone preferences

## Content Generation Guidelines

### Presentation Title
- Create a **concise, descriptive title** that captures the essence of the topic
- Use **plain text format** (no markdown formatting)
- Make it **engaging and professional**
- Ensure it reflects the main theme and target audience

### Slide Titles
- Generate **clear, specific titles** for each slide
- Use **plain text format** (no markdown, no "Slide 1", "Slide 2" prefixes)
- Make each title **descriptive and informative**
- Ensure titles create a **logical flow** through the presentation
- Keep titles **concise but meaningful**

### Slide Body Content
- Use **structured markdown format** with topic headings and bullet points
- Structure should be: "## Topic\n- first point\n- second point"
- Make content **comprehensive and detailed** rather than single-line summaries
- Ensure each slide has **3-5 key points** under relevant topic headings
- Use **hierarchical structure** with H2 headings for main topics and bullet points for details

### Mermaid Diagram Integration
- **Automatically include mermaid diagrams** when content involves:
  - Processes, workflows, or step-by-step procedures
  - Organizational structures or hierarchies
  - Decision trees or conditional logic
  - System architectures or data flows
  - Timelines or project phases
- **Supported Mermaid formats**: graph LR/TD/TB, flowchart LR/TD, sequenceDiagram, classDiagram, gitgraph, timeline, journey
- Keep diagrams **simple and readable** with clear node connections
- Use **descriptive, concise node labels** (avoid long text in nodes)
- **Syntax requirements**: 
  - Proper node declarations: A[Text], B{Decision}, C((Circle))
  - Valid connections: -->, ---|, ==>, -.->
  - Escape special characters in labels
- For mermaid slides, set slide body to: "This slide contains a [diagram type] showing [brief description]"

## Special Considerations

### Slide Count Compliance
- Generate **exactly** the number of slides requested
- Distribute content **evenly** across slides
- **At least 20% of slides should include mermaid diagrams** when the topic involves processes or systems
- Create **balanced information flow**
"""


def get_user_prompt(prompt: str, n_slides: int, language: str, content: str):
    return f"""
        **Input:**
        - Prompt: {prompt}
        - Output Language: {language}
        - Number of Slides: {n_slides}
        - Additional Information: {content}
    """


def get_prompt_template(prompt: str, n_slides: int, language: str, content: str):
    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": get_user_prompt(prompt, n_slides, language, content),
        },
    ]


def get_response_format(response_model: BaseModel):
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "PresentationOutlineModel",
            "schema": response_model.model_json_schema(),
        },
    }


async def generate_ppt_outline(
    prompt: Optional[str],
    n_slides: int,
    language: Optional[str] = None,
    content: Optional[str] = None,
    web_search_enabled: bool = False,
    presentation_id: Optional[str] = None,
):
    model = get_large_model()
    response_model = get_presentation_outline_model_with_n_slides(n_slides)

    if not is_google_selected():
        client = get_llm_client()
        
        # Determine if we should use web search
        use_web_search = web_search_enabled and prompt and should_use_web_search(prompt)
        
        # DEBUG: Log web search decision process
        logger.info(f"OPENAI WEB SEARCH DECISION - web_search_enabled: {web_search_enabled} | prompt_exists: {bool(prompt)} | should_use_web_search: {should_use_web_search(prompt) if prompt else False} | final_decision: {use_web_search}")
        
        messages = get_prompt_template(prompt, n_slides, language, content)
        
        if use_web_search:
            # Set presentation context for citation tracking
            if presentation_id:
                tool_registry.set_presentation_context(presentation_id)
                logger.info(f"OPENAI WEB SEARCH ENABLED for presentation: {presentation_id}")
            
            # Add web search instruction to system prompt
            system_message = next((msg for msg in messages if msg["role"] == "system"), None)
            if system_message:
                system_message["content"] += "\n\nIMPORTANT: If you need current information, statistics, or recent data to create accurate content, search for relevant information to ensure accuracy."
            
            # Try using OpenAI's web search via Chat Completions with web_search_options
            try:
                logger.info("OPENAI: Attempting to use web search via Chat Completions API")
                
                # Use Chat Completions with web_search_options and search models
                search_model = "gpt-4o-search-preview" if "gpt-4" in model else "gpt-4o-mini-search-preview"
                
                response = await client.chat.completions.create(
                    model=search_model,
                    messages=messages,
                    web_search_options={},  # Enable web search
                    response_format=get_response_format(response_model)
                )
                
                if response.choices[0].message.content:
                    logger.info("OPENAI: Successfully used native web search with search model")
                    yield response.choices[0].message.content
                    return
                    
            except Exception as search_error:
                logger.warning(f"OPENAI: Search model failed, trying Responses API: {search_error}")
                
                # Try Responses API as second option
                try:
                    logger.info("OPENAI: Attempting Responses API with web_search_preview")
                    
                    # Note: This might need different client or API call
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=[{"type": "web_search_preview"}],
                        response_format=get_response_format(response_model)
                    )
                    
                    if response.choices[0].message.content:
                        logger.info("OPENAI: Successfully used Responses API web search")
                        yield response.choices[0].message.content
                        return
                        
                except Exception as responses_error:
                    logger.warning(f"OPENAI: Responses API also failed, falling back to custom: {responses_error}")
                    
                    # Final fallback to custom tool implementation
                    tools = tool_registry.get_tools_schema()
                    
                    async for response in await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True,
                        response_format=get_response_format(response_model),
                        tools=tools,
                        tool_choice="auto",
                    ):
                        delta: ChoiceDelta = response.choices[0].delta
                        
                        # Handle tool calls (simplified - ignoring for now)
                        if delta.tool_calls:
                            pass
                        elif delta.content:
                            yield delta.content
        else:
            # No web search needed, use standard streaming
            async for response in await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                response_format=get_response_format(response_model),
            ):
                delta: ChoiceDelta = response.choices[0].delta
                if delta.content:
                    yield delta.content

    else:
        client = get_google_llm_client()
        
        # Determine if we should use web search (same logic as OpenAI)
        use_web_search = web_search_enabled and prompt and should_use_web_search(prompt)
        
        # DEBUG: Log web search decision process for Google too
        logger.info(f"GEMINI WEB SEARCH DECISION - web_search_enabled: {web_search_enabled} | prompt_exists: {bool(prompt)} | should_use_web_search: {should_use_web_search(prompt) if prompt else False} | final_decision: {use_web_search}")
        
        # Set presentation context for citation tracking
        if use_web_search and presentation_id:
            tool_registry.set_presentation_context(presentation_id)
            logger.info(f"GEMINI GROUNDING SEARCH ENABLED for presentation: {presentation_id}")
        
        # Configure Gemini generation
        if use_web_search:
            # For web search, use google_search tool without structured output
            # Based on error: "controlled generation is not supported with google_search tool"
            system_message_with_search = system_prompt + "\n\nIMPORTANT: If you need current information, statistics, or recent data to create accurate content, search for relevant information using grounding with Google Search. Please format your response as valid JSON matching this exact structure: " + str(response_model.model_json_schema())
            
            config_kwargs = {
                "system_instruction": system_message_with_search,
                "tools": [{"google_search": {}}]  # google_search tool without controlled generation
            }
            logger.info("GEMINI: Using native grounding search with google_search tool (manual JSON formatting)")
        else:
            # No web search, use structured output with correct parameter name
            config_kwargs = {
                "system_instruction": system_prompt,
                "response_mime_type": "application/json",
                "response_schema": response_model,  # Use response_schema instead of response_json_schema
            }
            logger.info("GEMINI: Using structured output with response_schema (no web search)")
        
        generate_stream = iterator_to_async(client.models.generate_content_stream)
        try:
            config = GenerateContentConfig(**config_kwargs)
            print("use_web_search:", config)
            async for event in generate_stream(
                model=model,
                contents=[get_user_prompt(prompt, n_slides, language, content)],
                config=config,
            ):
                if event.text:
                    yield event.text
        except Exception as e:
            # If Google API fails, try OpenAI as fallback
            import json
            
            logger.exception("Google GenAI API failed, attempting OpenAI fallback")
            
            try:
                # Try OpenAI as fallback
                openai_client = get_llm_client()
                async for response in await openai_client.chat.completions.create(
                    model="gpt-4o-mini",  # Use a reliable model
                    messages=get_prompt_template(prompt, n_slides, language, content),
                    stream=True,
                    response_format=get_response_format(response_model),
                ):
                    delta: ChoiceDelta = response.choices[0].delta
                    if delta.content:
                        yield delta.content
                        
            except Exception as fallback_error:
                # If both fail, create a basic outline structure
                logger.exception("Both Google and OpenAI APIs failed, using fallback outline")
                
                fallback_outline = {
                    "title": f"Presentation: {prompt or 'Topic Overview'}",
                    "slides": []
                }
                
                # Generate basic slide titles
                for i in range(n_slides):
                    slide_title = f"Topic {i+1}"
                    if i == 0:
                        slide_title = "Introduction"
                    elif i == n_slides - 1:
                        slide_title = "Conclusion"
                    else:
                        slide_title = f"Key Point {i}"
                    
                    fallback_outline["slides"].append({
                        "title": slide_title,
                        "type": 123
                    })
                
                yield json.dumps(fallback_outline)
