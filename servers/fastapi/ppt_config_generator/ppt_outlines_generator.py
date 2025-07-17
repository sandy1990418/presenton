from typing import Optional

from api.utils.model_utils import get_large_model, get_llm_client
from api.utils.variable_length_models import (
    get_presentation_markdown_model_with_n_slides,
)
from ppt_config_generator.models import PresentationMarkdownModel


def get_prompt_template(prompt: str, n_slides: int, language: str, content: str, images: list = None):
    images_info = ""
    if images:
        images_info = f"""
        - Reference Images: {len(images)} images provided
        - Image Integration: Each relevant image should be referenced in slide notes with specific placement suggestions
        """
    
    return [
        {
            "role": "system",
            "content": f"""
                You are a professional presentation designer and content strategist. Create a high-quality, engaging presentation that matches the depth and professionalism of human-crafted business presentations.
                
                # Professional Standards
                
                1. **Content Depth & Quality**:
                   - Provide substantial, actionable insights rather than superficial information
                   - Include specific data points, statistics, and concrete examples where relevant
                   - Structure content with clear narrative flow and logical progression
                   - Use professional business language with appropriate technical terminology
                   - Incorporate industry best practices and current trends
                
                2. **Slide Structure & Design**:
                   - Create compelling slide titles that capture attention and convey key messages
                   - Use hierarchical information architecture (main points → supporting details → examples)
                   - Balance text with visual elements (charts, diagrams, images)
                   - Include calls-to-action and key takeaways for each slide
                   - Ensure each slide has a clear purpose and contributes to overall narrative
                
                3. **Visual Integration**:
                   - Reference provided images strategically throughout the presentation
                   - Suggest specific placement for charts, graphs, and visual elements
                   - Include detailed descriptions for recommended visualizations
                   - Provide image captions and context explanations
                
                4. **Professional Presentation Techniques**:
                   - Start with a compelling hook or problem statement
                   - Use the "Tell them what you're going to tell them, tell them, then tell them what you told them" structure
                   - Include transition statements between slides
                   - Provide speaker notes with additional context and talking points
                   - End with clear next steps or recommendations
                
                # Content Guidelines
                
                - **Depth**: Each slide should contain 3-5 substantial points, not just bullet lists
                - **Evidence**: Include specific examples, case studies, or data to support key points
                - **Context**: Provide background information and explain why points matter
                - **Actionability**: Include practical applications and implementation steps
                - **Engagement**: Use storytelling techniques and real-world scenarios
                
                # Technical Requirements
                
                - Use markdown for rich formatting (tables, lists, emphasis)
                - Include suggested chart types and data visualization recommendations
                - Provide detailed notes for each slide including:
                  * Speaker talking points
                  * Visual element suggestions
                  * Transition cues
                  * Time estimates
                
                # Visual Element Integration
                
                - Analyze provided images and integrate them meaningfully into content
                - Suggest specific slide placements for each image
                - Provide context and explanation for visual elements
                - Recommend complementary charts or graphics
                
                Format the output in the specified JSON schema with professional-grade content.
                """,
        },
        {
            "role": "user",
            "content": f"""
                **Presentation Brief:**
                - Topic: {prompt}
                - Output Language: {language}
                - Number of Slides: {n_slides}
                - Additional Context: {content}
                {images_info}
                
                **Requirements:**
                - Create a presentation that matches professional business standards
                - Include specific, actionable insights rather than generic content
                - Integrate visual elements and data visualizations
                - Provide comprehensive speaker notes and presentation guidance
                - Ensure logical flow and narrative coherence
                
                **Target Audience:** Business professionals, stakeholders, and decision-makers
                **Presentation Style:** Professional, data-driven, actionable
            """,
        },
    ]


async def generate_ppt_content(
    prompt: Optional[str],
    n_slides: int,
    language: Optional[str] = None,
    content: Optional[str] = None,
    images: Optional[list] = None,
) -> PresentationMarkdownModel:
    from api.utils.model_utils import get_selected_llm_provider
    from api.models import SelectedLLMProvider
    import json
    
    client = get_llm_client()
    model = get_large_model()
    response_model = get_presentation_markdown_model_with_n_slides(n_slides)
    selected_llm = get_selected_llm_provider()

    try:
        # 對於 OpenAI，使用 structured output
        if selected_llm == SelectedLLMProvider.OPENAI:
            response = await client.beta.chat.completions.parse(
                model=model,
                temperature=0.2,
                messages=get_prompt_template(prompt, n_slides, language, content, images),
                response_format=response_model,
            )
            return response.choices[0].message.parsed
        
        # 對於其他提供商，使用 JSON mode
        else:
            # 添加 JSON 格式指令到 prompt
            messages = get_prompt_template(prompt, n_slides, language, content, images)
            
            # 修改系統消息以包含 JSON 格式要求
            messages[0]["content"] += f"""
            
            IMPORTANT: Return the response in valid JSON format matching this schema:
            {{
                "title": "string (Title of the presentation in about 3 to 8 words)",
                "notes": ["string array (Notes for the presentation)"],
                "slides": [
                    {{
                        "title": "string (Title of the slide in about 3 to 5 words)",
                        "body": "string (Content of the slide in markdown format)"
                    }}
                ]
            }}
            
            Make sure to generate exactly {n_slides} slides.
            """
            
            response = await client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            # 解析 JSON 響應
            json_response = json.loads(response.choices[0].message.content)
            
            # 驗證並創建 PresentationMarkdownModel
            return response_model(**json_response)
            
    except Exception as e:
        print(f"Error in generate_ppt_content: {e}")
        # 回退到基本的文本響應
        response = await client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=get_prompt_template(prompt, n_slides, language, content, images),
        )
        
        # 創建一個基本的響應結構
        from ppt_config_generator.models import SlideMarkdownModel
        
        return response_model(
            title=f"Presentation about {prompt[:50] if prompt else 'Topic'}...",
            notes=["Generated with fallback method"],
            slides=[
                SlideMarkdownModel(
                    title=f"Slide {i+1}",
                    body=f"Content for slide {i+1} based on: {prompt or 'No specific topic provided'}"
                )
                for i in range(n_slides)
            ]
        )
