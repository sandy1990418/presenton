"""
StreamingMixin provides standardized streaming response functionality for handlers.
"""

import json
from typing import AsyncGenerator, Any, Dict
from fastapi.responses import StreamingResponse

from models.sse_response import SSEResponse, SSECompleteResponse, SSEStatusResponse
from .logging_mixin import LoggingMixin


class StreamingMixin(LoggingMixin):
    """Provides standardized streaming response utilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def create_sse_response(self, event: str, data: Any) -> SSEResponse:
        """
        Create a standardized SSE response.
        
        Args:
            event: Event type
            data: Data to send
            
        Returns:
            SSEResponse instance
        """
        return SSEResponse(event=event, data=json.dumps(data))
    
    def create_sse_status_response(self, status: str) -> SSEStatusResponse:
        """
        Create a status update SSE response.
        
        Args:
            status: Status message
            
        Returns:
            SSEStatusResponse instance
        """
        return SSEStatusResponse(status=status)
    
    def create_sse_complete_response(self, key: str, value: Any) -> SSECompleteResponse:
        """
        Create a completion SSE response.
        
        Args:
            key: Response key
            value: Response value
            
        Returns:
            SSECompleteResponse instance
        """
        return SSECompleteResponse(key=key, value=value)
    
    def create_streaming_response(self, generator: AsyncGenerator[str, None], media_type: str = "text/event-stream") -> StreamingResponse:
        """
        Create a FastAPI StreamingResponse with logging.
        
        Args:
            generator: Async generator that yields response chunks
            media_type: Response media type
            
        Returns:
            StreamingResponse instance
        """
        self.logger.info("Creating streaming response", media_type=media_type)
        return StreamingResponse(generator, media_type=media_type)
    
    async def yield_status_update(self, status: str) -> str:
        """
        Yield a status update for streaming.
        
        Args:
            status: Status message
            
        Returns:
            SSE formatted string
        """
        self.log_streaming_progress("status_update", status=status)
        response = self.create_sse_status_response(status)
        return response.to_string()
    
    async def yield_progress_update(self, step: str, current: int, total: int, **context) -> str:
        """
        Yield a progress update for streaming.
        
        Args:
            step: Current step description
            current: Current progress count
            total: Total expected count
            **context: Additional context data
            
        Returns:
            SSE formatted string
        """
        self.log_streaming_progress(step, current=current, total=total, **context)
        
        data = {
            "type": "progress",
            "step": step,
            "current": current,
            "total": total,
            "progress": round((current / total) * 100, 1),
            **context
        }
        
        response = self.create_sse_response("response", data)
        return response.to_string()
    
    async def yield_chunk_update(self, chunk: Any) -> str:
        """
        Yield a data chunk for streaming.
        
        Args:
            chunk: Data chunk to send
            
        Returns:
            SSE formatted string
        """
        self.logger.debug("Yielding data chunk", chunk_type=type(chunk).__name__)
        
        data = {
            "type": "chunk", 
            "chunk": chunk
        }
        
        response = self.create_sse_response("response", data)
        return response.to_string()
    
    async def yield_error(self, error_message: str, error_type: str = "error") -> str:
        """
        Yield an error for streaming.
        
        Args:
            error_message: Error message
            error_type: Type of error
            
        Returns:
            SSE formatted string
        """
        self.logger.error("Streaming error occurred", error_message=error_message, error_type=error_type)
        
        data = {
            "type": "error",
            "error": error_message,
            "error_type": error_type
        }
        
        response = self.create_sse_response("response", data)
        return response.to_string()
    
    async def yield_completion(self, key: str, value: Any) -> str:
        """
        Yield completion response for streaming.
        
        Args:
            key: Response key
            value: Final response value
            
        Returns:
            SSE formatted string
        """
        self.log_streaming_progress("completion", key=key)
        response = self.create_sse_complete_response(key, value)
        return response.to_string()
    
    def track_active_stream(self, stream_id: str, active_streams: set[str]) -> bool:
        """
        Track and prevent duplicate streaming requests.
        
        Args:
            stream_id: Unique stream identifier
            active_streams: Set of currently active stream IDs
            
        Returns:
            True if stream can proceed, False if already active
        """
        if stream_id in active_streams:
            self.logger.warning(
                "Duplicate stream request rejected",
                stream_id=stream_id,
                active_streams=len(active_streams)
            )
            return False
        
        active_streams.add(stream_id)
        self.logger.info(
            "Stream started",
            stream_id=stream_id,
            active_streams=len(active_streams)
        )
        return True
    
    def cleanup_active_stream(self, stream_id: str, active_streams: set[str]) -> None:
        """
        Clean up active stream tracking.
        
        Args:
            stream_id: Stream identifier to clean up
            active_streams: Set of currently active stream IDs
        """
        active_streams.discard(stream_id)
        self.logger.info(
            "Stream completed",
            stream_id=stream_id,
            remaining_active_streams=len(active_streams)
        )