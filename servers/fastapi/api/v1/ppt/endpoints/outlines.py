import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.presentation_outline_model import PresentationOutlineModel
from models.sql.presentation import PresentationModel
from models.sse_response import SSECompleteResponse, SSEResponse, SSEStatusResponse
from services.database import get_async_session
from utils.llm_calls.generate_presentation_outlines import generate_ppt_outline

OUTLINES_ROUTER = APIRouter(prefix="/outlines", tags=["Outlines"])


@OUTLINES_ROUTER.get("/stream")
async def stream_outlines(
    presentation_id: str, sql_session: AsyncSession = Depends(get_async_session)
):
    presentation = await sql_session.get(PresentationModel, presentation_id)

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    async def inner():
        yield SSEStatusResponse(
            status="Generating presentation outlines..."
        ).to_string()

        presentation_content_text = ""
        async for chunk in generate_ppt_outline(
            presentation.prompt,
            presentation.n_slides,
            presentation.language,
            presentation.summary,
            presentation.web_search_enabled,
            presentation.id,
        ):
            # Give control to the event loop
            await asyncio.sleep(0)

            yield SSEResponse(
                event="response",
                data=json.dumps({"type": "chunk", "chunk": chunk}),
            ).to_string()
            presentation_content_text += chunk

        try:
            # Clean and validate the accumulated JSON
            cleaned_content = presentation_content_text.strip()
            if not cleaned_content:
                raise ValueError("Empty content received")
                
            presentation_content_json = json.loads(cleaned_content)
            # (f"PARSED JSON: {presentation_content_json}")
            
            # Validate required fields
            if "slides" not in presentation_content_json:
                raise ValueError("Missing 'slides' field in response")
                
            presentation_content = PresentationOutlineModel(**presentation_content_json)
            
            # Ensure we don't exceed requested slide count and remove duplicates
            unique_slides = []
            seen_titles = set()
            for slide in presentation_content.slides[:presentation.n_slides]:
                if slide.title not in seen_titles:
                    unique_slides.append(slide)
                    seen_titles.add(slide.title)
                else:
                    print(f"⚠️ Duplicate slide title detected and removed: {slide.title}")

            presentation.title = presentation_content.title or f"Presentation - {presentation.prompt[:50]}"
            presentation.outlines = [slide.model_dump() for slide in unique_slides]
            presentation.notes = getattr(presentation_content, 'notes', None)
            
            # Success! Outlines were parsed and set
            print(f"✅ Successfully set {len(presentation.outlines)} unique outlines (removed {len(presentation_content.slides) - len(unique_slides)} duplicates)")
            
        except (json.JSONDecodeError, ValueError) as e:
            # If parsing fails, log the error but don't crash the endpoint
            print(f"⚠️ PARSING FAILED: {e}")
            print(f"CONTENT LENGTH: {len(presentation_content_text)}")
            print(f"CONTENT PREVIEW: {presentation_content_text[:500]}...")
            
            # Try to extract partial information
            if presentation_content_text:
                try:
                    # Try to repair incomplete JSON
                    from json_repair import repair_json

                    repaired_json = repair_json(presentation_content_text)
                    partial_json = json.loads(repaired_json)
                    
                    if "title" in partial_json:
                        presentation.title = partial_json["title"]
                        print(f"✅ EXTRACTED TITLE: {presentation.title}")
                    
                    if "slides" in partial_json and isinstance(partial_json["slides"], list):
                        # Create fallback slides from partial data
                        presentation.outlines = []
                        for slide_data in partial_json["slides"][:presentation.n_slides]:
                            if isinstance(slide_data, dict) and "title" in slide_data:
                                presentation.outlines.append(slide_data)
                        print(f"✅ EXTRACTED {len(presentation.outlines)} PARTIAL SLIDES")
                except Exception as repair_error:
                    print(f"⚠️ JSON repair also failed: {repair_error}")
                    
            # Set fallback values if nothing was extracted
            if not presentation.title:
                presentation.title = f"Presentation - {presentation.prompt[:50]}"
            if not presentation.outlines:
                presentation.outlines = []

        sql_session.add(presentation)
        await sql_session.commit()

        yield SSECompleteResponse(
            key="presentation", value=presentation.model_dump(mode="json")
        ).to_string()

    return StreamingResponse(inner(), media_type="text/event-stream")
