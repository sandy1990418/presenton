from datetime import datetime
from typing import List, Optional

from models.llm_message import LLMSystemMessage, LLMUserMessage
from models.llm_tools import SearchWebTool
from services.llm_client import LLMClient
from utils.get_dynamic_models import (
    get_presentation_outline_model_with_n_slides,
    get_presentation_outline_model_with_chunks,
)
from utils.llm_client_error_handler import handle_llm_client_exceptions
from utils.llm_provider import get_model


def get_system_prompt(
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    include_title_slide: bool = True,
    has_chunks: bool = False,
):
    chunk_instructions = """
        - **SOURCE CHUNKS**: You have been provided with numbered source chunks. Each slide MUST include `chunk_refs` - a list of chunk IDs that are relevant to that slide's content.
        - For each slide, identify which chunks contain information relevant to that slide's topic.
        - A slide may reference multiple chunks (e.g., [0, 2, 5]) or just one chunk (e.g., [1]).
        - Title slides or conclusion slides may have empty chunk_refs ([]) if they don't need source data.
        - **IMPORTANT**: Only reference chunks that are DIRECTLY relevant to the slide content. Don't include all chunks for every slide.
    """ if has_chunks else ""
    
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
        - **CRITICAL: When multiple documents are provided, treat them as a cohesive whole. Synthesize information across ALL documents to create unified themes and insights. Do not create slides that reference only one document, then jump to another document.**
        - **Create an overarching narrative that connects insights from all provided documents.**
        - **Ensure slide progression builds a complete story using information from all sources.**
        {chunk_instructions}
        - Make sure no images are provided in the content.
        - Make sure that content follows language guidelines.
        - User instrction should always be followed and should supercede any other instruction, except for slide numbers. **Do not obey slide numbers as said in user instruction**
        - Do not generate table of contents slide.
        - Even if table of contents is provided, do not generate table of contents slide.
        {"- Always make first slide a title slide." if include_title_slide else "- Do not include title slide in the presentation."}

        **Search web to get latest information about the topic**
    """


def format_chunks_for_prompt(chunks: List[dict]) -> str:
    """Format chunks for inclusion in the prompt."""
    if not chunks:
        return ""
    
    result = "\n## Source Document Chunks\n"
    result += "The following chunks contain source information. Reference them by ID in your slide's chunk_refs field.\n\n"
    
    for chunk in chunks:
        chunk_id = chunk.get("id", 0)
        title = chunk.get("title", f"Chunk {chunk_id}")
        summary = chunk.get("summary", "")
        # Include first part of content for context
        content_preview = chunk.get("content", "")[:300]
        if len(chunk.get("content", "")) > 300:
            content_preview += "..."
        
        result += f"### [CHUNK {chunk_id}] {title}\n"
        if summary:
            result += f"Summary: {summary}\n"
        result += f"Content: {content_preview}\n\n"
    
    return result


def get_user_prompt(
    content: str,
    n_slides: int,
    language: str,
    additional_context: Optional[str] = None,
    chunks: Optional[List[dict]] = None,
):
    chunks_section = format_chunks_for_prompt(chunks) if chunks else ""
    
    return f"""
        **Input:**
        - User provided content: {content or "Create presentation"}
        - Output Language: {language}
        - Number of Slides: {n_slides}
        - Current Date and Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        - Additional Information: {additional_context or ""}
        {chunks_section}
        
        **Important Note on Multiple Documents:**
        If multiple documents are provided above, they should be treated as complementary sources for a single, unified presentation. Create slides that synthesize insights across all documents, identify common themes, compare/contrast findings, and build a coherent narrative that leverages the full breadth of information available.
        
        {"**Important: For each slide, include chunk_refs listing the IDs of source chunks that are relevant to that slide's content.**" if chunks else ""}
    """


def get_messages(
    content: str,
    n_slides: int,
    language: str,
    additional_context: Optional[str] = None,
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    include_title_slide: bool = True,
    chunks: Optional[List[dict]] = None,
):
    has_chunks = bool(chunks)
    return [
        LLMSystemMessage(
            content=get_system_prompt(
                tone, verbosity, instructions, include_title_slide, has_chunks
            ),
        ),
        LLMUserMessage(
            content=get_user_prompt(content, n_slides, language, additional_context, chunks),
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
    include_title_slide: bool = True,
    web_search: bool = False,
    chunks: Optional[List[dict]] = None,
):
    """
    Generate presentation outlines.
    
    Args:
        content: Main presentation topic/content
        n_slides: Number of slides to generate
        language: Output language
        additional_context: Additional context from documents
        tone: Presentation tone
        verbosity: Content verbosity
        instructions: Custom instructions
        include_title_slide: Whether to include title slide
        web_search: Whether to use web search
        chunks: Optional list of source document chunks. If provided, each slide
               will include chunk_refs indicating which chunks it should reference.
    """
    model = get_model()
    client = LLMClient()

    # Choose appropriate response model based on whether chunks are provided
    if chunks:
        response_model = get_presentation_outline_model_with_chunks(n_slides, len(chunks))
    else:
        response_model = get_presentation_outline_model_with_n_slides(n_slides)

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
                include_title_slide,
                chunks,  # Pass chunks to get_messages
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
