from datetime import datetime
from typing import Optional

from models.llm_message import LLMSystemMessage, LLMUserMessage
from models.llm_tools import SearchWebTool
from services.llm_client import LLMClient
from utils.get_dynamic_models import get_presentation_outline_model_with_n_slides
from utils.llm_client_error_handler import handle_llm_client_exceptions
from utils.llm_provider import get_model


def get_system_prompt(
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
):
    return f"""
        You are an expert presentation creator. Generate structured presentations based on user requirements and format them according to the specified JSON schema with markdown content.

        Try to use available tools for better results.

        {"# User Instruction:" if instructions else ""}
        {instructions or ""}

        {"# Tone:" if tone else ""}
        {tone or ""}

        {"# Verbosity:" if verbosity else ""}
        {verbosity or ""}

        - Provide content for each slide in markdown format.
        - Make sure that flow of the presentation is logical and consistent.
        - Place greater emphasis on numerical data.
        - If Additional Information is provided, divide it into slides.
        - Make sure no images are provided in the content.
        - Make sure that content follows language guidelines.
    """


def get_user_prompt(
    content: str,
    n_slides: int,
    language: str,
    additional_context: Optional[str] = None,
):
    return f"""
        **Input:**
        - User provided content: {content}
        - Output Language: {language}
        - Number of Slides: {n_slides}
        - Current Date and Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        - Additional Information: {additional_context or ""}
    """


def get_messages(
    content: str,
    n_slides: int,
    language: str,
    additional_context: Optional[str] = None,
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
):
    return [
        LLMSystemMessage(
            content=get_system_prompt(tone, verbosity, instructions),
        ),
        LLMUserMessage(
            content=get_user_prompt(content, n_slides, language, additional_context),
        ),
    ]


async def generate_ppt_outline(
    content: str,
    n_slides: int,
    language: Optional[str] = None,
    additional_context: Optional[str] = None,
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    web_search: bool = False,
):
    model = get_model()
    response_model = get_presentation_outline_model_with_n_slides(n_slides)

    # if not is_google_selected():
    #     client = get_llm_client()
        
    #     # Determine if we should use web search
    #     use_web_search = web_search_enabled and prompt and should_use_web_search(prompt)
        
    #     # DEBUG: Log web search decision process
    #     logger.info(f"OPENAI WEB SEARCH DECISION - web_search_enabled: {web_search_enabled} | prompt_exists: {bool(prompt)} | should_use_web_search: {should_use_web_search(prompt) if prompt else False} | final_decision: {use_web_search}")
        
    #     messages = get_prompt_template(prompt, n_slides, language, content)
        
    #     if use_web_search:
    #         # Set presentation context for citation tracking
    #         if presentation_id:
    #             tool_registry.set_presentation_context(presentation_id)
    #             logger.info(f"OPENAI WEB SEARCH ENABLED for presentation: {presentation_id}")
            
    #         # Add web search instruction to system prompt
    #         system_message = next((msg for msg in messages if msg["role"] == "system"), None)
    #         if system_message:
    #             system_message["content"] += "\n\nIMPORTANT: If you need current information, statistics, or recent data to create accurate content, search for relevant information to ensure accuracy."
            
    #         # Try using OpenAI's web search via Chat Completions with web_search_options
    #         try:
    #             logger.info("OPENAI: Attempting to use web search via Chat Completions API")
                
    #             # Use Chat Completions with web_search_options and search models
    #             search_model = "gpt-4o-search-preview" if "gpt-4" in model else "gpt-4o-mini-search-preview"
                
    #             response = await client.chat.completions.create(
    #                 model=search_model,
    #                 messages=messages,
    #                 web_search_options={},  # Enable web search
    #                 response_format=get_response_format(response_model)
    #             )
                
    #             if response.choices[0].message.content:
    #                 logger.info("OPENAI: Successfully used native web search with search model")
    #                 yield response.choices[0].message.content
    #                 return
                    
    #         except Exception as search_error:
    #             logger.warning(f"OPENAI: Search model failed, trying Responses API: {search_error}")
                
    #             # Try Responses API as second option
    #             try:
    #                 logger.info("OPENAI: Attempting Responses API with web_search_preview")
                    
    #                 # Note: This might need different client or API call
    #                 response = await client.chat.completions.create(
    #                     model=model,
    #                     messages=messages,
    #                     tools=[{"type": "web_search_preview"}],
    #                     response_format=get_response_format(response_model)
    #                 )
                    
    #                 if response.choices[0].message.content:
    #                     logger.info("OPENAI: Successfully used Responses API web search")
    #                     yield response.choices[0].message.content
    #                     return
                        
    #             except Exception as responses_error:
    #                 logger.warning(f"OPENAI: Responses API also failed, falling back to custom: {responses_error}")
                    
    #                 # Final fallback to custom tool implementation
    #                 tools = tool_registry.get_tools_schema()
                    
    #                 async for response in await client.chat.completions.create(
    #                     model=model,
    #                     messages=messages,
    #                     stream=True,
    #                     response_format=get_response_format(response_model),
    #                     tools=tools,
    #                     tool_choice="auto",
    #                 ):
    #                     delta: ChoiceDelta = response.choices[0].delta
                        
    #                     # Handle tool calls (simplified - ignoring for now)
    #                     if delta.tool_calls:
    #                         pass
    #                     elif delta.content:
    #                         yield delta.content
    #     else:
    #         # No web search needed, use standard streaming
    #         async for response in await client.chat.completions.create(
    #             model=model,
    #             messages=messages,
    #             stream=True,
    #             response_format=get_response_format(response_model),
    #         ):
    #             delta: ChoiceDelta = response.choices[0].delta
    #             if delta.content:
    #                 yield delta.content

    # else:
    #     client = get_google_llm_client()
        
    #     # Determine if we should use web search (same logic as OpenAI)
    #     use_web_search = web_search_enabled and prompt and should_use_web_search(prompt)
        
    #     # DEBUG: Log web search decision process for Google too
    #     logger.info(f"GEMINI WEB SEARCH DECISION - web_search_enabled: {web_search_enabled} | prompt_exists: {bool(prompt)} | should_use_web_search: {should_use_web_search(prompt) if prompt else False} | final_decision: {use_web_search}")
        
    #     # Set presentation context for citation tracking
    #     if use_web_search and presentation_id:
    #         tool_registry.set_presentation_context(presentation_id)
    #         logger.info(f"GEMINI GROUNDING SEARCH ENABLED for presentation: {presentation_id}")
        
    #     # Configure Gemini generation
    #     if use_web_search:
    #         # For web search, use google_search tool without structured output
    #         # Based on error: "controlled generation is not supported with google_search tool"
    #         system_message_with_search = system_prompt + "\n\nIMPORTANT: If you need current information, statistics, or recent data to create accurate content, search for relevant information using grounding with Google Search. Please format your response as valid JSON matching this exact structure: " + str(response_model.model_json_schema())
            
    #         config_kwargs = {
    #             "system_instruction": system_message_with_search,
    #             "tools": [{"google_search": {}}]  # google_search tool without controlled generation
    #         }
    #         logger.info("GEMINI: Using native grounding search with google_search tool (manual JSON formatting)")
    #     else:
    #         # No web search, use structured output with correct parameter name
    #         config_kwargs = {
    #             "system_instruction": system_prompt,
    #             "response_mime_type": "application/json",
    #             "response_schema": response_model,  # Use response_schema instead of response_json_schema
    #         }
    #         logger.info("GEMINI: Using structured output with response_schema (no web search)")
        
    #     generate_stream = iterator_to_async(client.models.generate_content_stream)
    #     try:
    #         config = GenerateContentConfig(**config_kwargs)
    #         print("use_web_search:", config)
    #         async for event in generate_stream(
    #             model=model,
    #             contents=[get_user_prompt(prompt, n_slides, language, content)],
    #             config=config,
    #         ):
    #             if event.text:
    #                 yield event.text
    #     except Exception as e:
    #         # If Google API fails, try OpenAI as fallback
    #         import json
            
    #         logger.exception("Google GenAI API failed, attempting OpenAI fallback")
            
    #         try:
    #             # Try OpenAI as fallback
    #             openai_client = get_llm_client()
    #             async for response in await openai_client.chat.completions.create(
    #                 model="gpt-4o-mini",  # Use a reliable model
    #                 messages=get_prompt_template(prompt, n_slides, language, content),
    #                 stream=True,
    #                 response_format=get_response_format(response_model),
    #             ):
    #                 delta: ChoiceDelta = response.choices[0].delta
    #                 if delta.content:
    #                     yield delta.content
                        
    #         except Exception as fallback_error:
    #             # If both fail, create a basic outline structure
    #             logger.exception("Both Google and OpenAI APIs failed, using fallback outline")
                
    #             fallback_outline = {
    #                 "title": f"Presentation: {prompt or 'Topic Overview'}",
    #                 "slides": []
    #             }
                
    #             # Generate basic slide titles
    #             for i in range(n_slides):
    #                 slide_title = f"Topic {i+1}"
    #                 if i == 0:
    #                     slide_title = "Introduction"
    #                 elif i == n_slides - 1:
    #                     slide_title = "Conclusion"
    #                 else:
    #                     slide_title = f"Key Point {i}"
                    
    #                 fallback_outline["slides"].append({
    #                     "title": slide_title,
    #                     "type": 123
    #                 })
                
    #             yield json.dumps(fallback_outline)
    client = LLMClient()

    try:
        async for chunk in client.stream_structured(
            model,
            get_messages(
                content,
                n_slides,
                language,
                additional_context,
                tone,
                verbosity,
                instructions,
            ),
            response_model.model_json_schema(),
            strict=True,
            tools=(
                [SearchWebTool]
                if (client.enable_web_grounding() and web_search)
                else None
            ),
        ):
            yield chunk
    except Exception as e:
        yield handle_llm_client_exceptions(e)
