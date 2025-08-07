from models.llm_message import LLMMessage
from models.presentation_layout import SlideLayoutModel
from models.presentation_outline_model import SlideOutlineModel
from services.llm_client import LLMClient
from utils.llm_provider import get_model
from utils.schema_utils import remove_fields_from_schema

system_prompt = """
    Generate structured slide based on provided outline, follow mentioned steps and notes and provide structured output.

    # Steps
    1. Analyze the outline and title.
    2. Generate structured slide based on the outline and title.
    3. For Mermaid diagrams, ensure proper syntax and node connections.
    1. Analyze the outline.
    2. Generate structured slide based on the outline.

    # Notes
    - Slide body should not use words like "This slide", "This presentation".
    - Rephrase the slide body to make it flow naturally.
    - Provide prompt to generate image on "__image_prompt__" property.
    - Provide query to search icon on "__icon_query__" property.
    - Do not use markdown formatting in slide body.
    - **Strictly follow the max and min character limit for every property in the slide.**
    - **For Mermaid diagrams**: 
      - Use proper node syntax: A[Text], B{Decision}, C((Circle))
      - Ensure valid connections: -->, ---|, ==>, -.->
      - Keep node labels concise and escape special characters
      - Test syntax: graph LR/TD, flowchart, sequenceDiagram, etc.
    - **Avoid duplicate content**: Each slide should have unique information and perspective.
    - Only use markdown to highlight important points.
    - Make sure to follow language guidelines.
    **Strictly follow the max and min character limit for every property in the slide.**
"""


def get_user_prompt(outline: str, language: str):
    return f"""
        ## Icon Query And Image Prompt Language
        English

        ## Slide Content Language
        {language}

        ## Slide Outline
        {outline}
    """


def get_messages(outline: str, language: str):

    return [
        LLMMessage(
            role="system",
            content=system_prompt,
        ),
        LLMMessage(
            role="user",
            content=get_user_prompt(outline, language),
        ),
    ]


async def get_slide_content_from_type_and_outline(
    slide_layout: SlideLayoutModel, outline: SlideOutlineModel, language: str
):
    client = LLMClient()
    model = get_model()

    response_schema = remove_fields_from_schema(
        slide_layout.json_schema, ["__image_url__", "__icon_url__"]
    )

#     if not is_google_selected():
#         client = get_llm_client()
#         response = await client.beta.chat.completions.parse(
#             model=model,
#             messages=get_prompt_to_generate_slide_content(
#                 outline.title,
#                 outline.body,
#                 language,
#             ),
#             response_format={
#                 "type": "json_schema",
#                 "json_schema": {
#                     "name": "SlideContent",
#                     "schema": response_schema,
#                 },
#             },
#         )
#         return json.loads(response.choices[0].message.content)
#     else:
#         client = get_google_llm_client()
#         response = await asyncio.to_thread(
#             client.models.generate_content,
#             model=model,
#             contents=[get_user_prompt(outline.title, outline.body, language)],
#             config=GenerateContentConfig(
#                 system_instruction=system_prompt,
#                 response_mime_type="application/json",
#                 response_json_schema=response_schema,
#             ),
#         )
#         return json.loads(response.text)


# contextual_system_prompt = """
#     Generate structured slide based on provided title and outline, while maintaining continuity with previous slides in the presentation.

#     # Steps
#     1. Analyze the previous slides context to understand the presentation flow.
#     2. Analyze the current slide outline and title.
#     3. Generate structured slide content that builds upon previous information without repetition.
#     4. For Mermaid diagrams, ensure proper syntax and node connections.

#     # Notes
#     - **Reference previous content**: Build upon concepts introduced in earlier slides
#     - **Maintain logical flow**: Ensure content flows naturally from previous slides
#     - **Avoid repetition**: Don't repeat information already covered in previous slides
#     - **Progressive disclosure**: Introduce new concepts that build on established ones
#     - Slide body should not use words like "This slide", "This presentation".
#     - Rephrase the slide body to make it flow naturally.
#     - Provide prompt to generate image on "__image_prompt__" property.
#     - Provide query to search icon on "__icon_query__" property.
#     - Do not use markdown formatting in slide body.
#     - **Strictly follow the max and min character limit for every property in the slide.**
#     - **For Mermaid diagrams**: 
#       - Use proper node syntax: A[Text], B{Decision}, C((Circle))
#       - Ensure valid connections: -->, ---|, ==>, -.->
#       - Keep node labels concise and escape special characters
#       - Test syntax: graph LR/TD, flowchart, sequenceDiagram, etc.
# """


# def get_contextual_user_prompt(title: str, outline: str, previous_slides: List[Dict[str, Any]], language: str):
#     # Create a summary of previous slides for context
#     context_summary = ""
#     if previous_slides:
#         context_summary = "## Previous Slides Context\n"
#         for i, slide in enumerate(previous_slides, 1):
#             slide_title = slide.get('title', f'Slide {i}')
#             # Extract key content points for context
#             slide_content = ""
#             if isinstance(slide.get('content'), dict):
#                 # Extract relevant content fields (titles, main points, etc.)
#                 content = slide['content']
#                 for key, value in content.items():
#                     if key not in ['__image_prompt__', '__icon_query__', '__image_url__', '__icon_url__'] and value:
#                         if isinstance(value, str) and len(value.strip()) > 0:
#                             slide_content += f"- {value[:100]}...\n" if len(value) > 100 else f"- {value}\n"
            
#             context_summary += f"### Slide {i}: {slide_title}\n{slide_content}\n"
    
#     return f"""
#         ## Icon Query And Image Prompt Language
#         English

#         ## Slide Content Language
#         {language}

#         {context_summary}
#         ## Current Slide Title
#         {title}

#         ## Current Slide Outline
#         {outline}
#     """


# def get_contextual_prompt_to_generate_slide_content(
#     title: str, outline: str, previous_slides: List[Dict[str, Any]], language: str
# ):
#     return [
#         {
#             "role": "system",
#             "content": contextual_system_prompt,
#         },
#         {
#             "role": "user",
#             "content": get_contextual_user_prompt(title, outline, previous_slides, language),
#         },
#     ]


# async def get_contextual_slide_content(
#     slide_layout: SlideLayoutModel, 
#     outline: SlideOutlineModel,
#     all_previous_slides: List[Dict[str, Any]],
#     language: str
# ):
#     """
#     Generate slide content with context from previous slides for better continuity.
    
#     Args:
#         slide_layout: The layout model for the current slide
#         outline: The outline for the current slide
#         all_previous_slides: List of previously generated slide content for context
    
#     Returns:
#         Generated slide content as a dictionary
#     """
#     model = get_llm_provider()

#     response_schema = remove_fields_from_schema(
#         slide_layout.json_schema, ["__image_url__", "__icon_url__"]
#     )

#     if not is_google_selected():
#         client = get_llm_client()
#         response = await client.beta.chat.completions.parse(
#             model=model,
#             messages=get_contextual_prompt_to_generate_slide_content(
#                 outline.title,
#                 outline.body,
#                 all_previous_slides,
#                 language,
#             ),
#             response_format={
#                 "type": "json_schema",
#                 "json_schema": {
#                     "name": "SlideContent",
#                     "schema": response_schema,
#                 },
#             },
#         )
#         return json.loads(response.choices[0].message.content)
#     else:
#         client = get_google_llm_client()
#         response = await asyncio.to_thread(
#             client.models.generate_content,
#             model=model,
#             contents=[get_contextual_user_prompt(outline.title, outline.body, all_previous_slides, language)],
#             config=GenerateContentConfig(
#                 system_instruction=contextual_system_prompt,
#                 response_mime_type="application/json",
#                 response_json_schema=response_schema,
#             ),
#         )
#         return json.loads(response.text)
    response = await client.generate_structured(
        model=model,
        messages=get_messages(
            outline.content,
            language,
        ),
        response_format=response_schema,
        strict=False,
    )
    return response
