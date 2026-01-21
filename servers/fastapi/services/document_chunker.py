"""
Document Chunker Service

Splits documents into semantic chunks for use in presentation generation.
Each chunk includes a summary and the original content, allowing slide
generation to reference only relevant chunks.
"""

import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from services.llm_client import LLMClient
from utils.llm_provider import get_model
from models.llm_message import LLMSystemMessage, LLMUserMessage


@dataclass
class DocumentChunk:
    """A chunk of document content with metadata."""
    id: int
    title: str  # Short title/topic for this chunk
    summary: str  # Brief summary of the chunk content
    content: str  # Original content
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DocumentChunker:
    """
    Splits documents into semantic chunks.
    
    Chunking strategies:
    1. By headers/sections if document has structure
    2. By paragraph groups if no clear structure
    3. By token count with overlap for long documents
    """
    
    def __init__(
        self,
        max_chunk_size: int = 1500,  # Max characters per chunk
        min_chunk_size: int = 200,   # Min characters per chunk
        overlap: int = 100,          # Character overlap between chunks
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap = overlap
    
    async def chunk_documents(
        self,
        documents: str,
        generate_summaries: bool = True,
    ) -> List[DocumentChunk]:
        """
        Split documents into chunks.
        
        Args:
            documents: Raw document content
            generate_summaries: Whether to generate LLM summaries for chunks
        
        Returns:
            List of DocumentChunk objects
        """
        if not documents or len(documents.strip()) < self.min_chunk_size:
            return []
        
        # Try structured chunking first (by headers)
        chunks = self._chunk_by_headers(documents)
        
        # Fall back to paragraph-based chunking
        if not chunks or len(chunks) == 1:
            chunks = self._chunk_by_paragraphs(documents)
        
        # Create DocumentChunk objects
        result = []
        for i, (title, content) in enumerate(chunks):
            chunk = DocumentChunk(
                id=i,
                title=title,
                summary="",  # Will be filled if generate_summaries=True
                content=content.strip(),
            )
            result.append(chunk)
        
        # Generate summaries if requested
        if generate_summaries and result:
            result = await self._generate_chunk_summaries(result)
        
        return result
    
    def _chunk_by_headers(self, text: str) -> List[tuple]:
        """
        Split by markdown headers or common section patterns.
        Returns list of (title, content) tuples.
        """
        # Match markdown headers (# ## ### etc.)
        header_pattern = r'^(#{1,6})\s+(.+?)$'
        
        # Also match common patterns like "Section 1:" or "1. Title"
        section_pattern = r'^(?:Section\s+\d+[:.]\s*|(?:\d+\.)+\s+)(.+?)$'
        
        lines = text.split('\n')
        chunks = []
        current_title = "Introduction"
        current_content = []
        
        for line in lines:
            # Check for markdown header
            header_match = re.match(header_pattern, line, re.MULTILINE)
            section_match = re.match(section_pattern, line, re.MULTILINE | re.IGNORECASE)
            
            if header_match or section_match:
                # Save previous chunk if it has content
                if current_content:
                    content = '\n'.join(current_content).strip()
                    if len(content) >= self.min_chunk_size:
                        chunks.append((current_title, content))
                    elif chunks:
                        # Merge small chunk with previous
                        prev_title, prev_content = chunks[-1]
                        chunks[-1] = (prev_title, prev_content + '\n\n' + content)
                
                # Start new chunk
                current_title = header_match.group(2) if header_match else section_match.group(1)
                current_content = []
            else:
                current_content.append(line)
        
        # Don't forget the last chunk
        if current_content:
            content = '\n'.join(current_content).strip()
            if len(content) >= self.min_chunk_size:
                chunks.append((current_title, content))
            elif chunks:
                prev_title, prev_content = chunks[-1]
                chunks[-1] = (prev_title, prev_content + '\n\n' + content)
        
        # If chunks are too large, split them further
        final_chunks = []
        for title, content in chunks:
            if len(content) > self.max_chunk_size * 2:
                # Split large chunks
                sub_chunks = self._split_large_chunk(title, content)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append((title, content))
        
        return final_chunks
    
    def _chunk_by_paragraphs(self, text: str) -> List[tuple]:
        """
        Split by paragraphs, grouping them to meet size requirements.
        """
        # Split by double newlines (paragraph breaks)
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        if not paragraphs:
            return []
        
        chunks = []
        current_content = []
        current_length = 0
        chunk_index = 1
        
        for para in paragraphs:
            para_length = len(para)
            
            # If adding this paragraph exceeds max, save current chunk
            if current_length + para_length > self.max_chunk_size and current_content:
                content = '\n\n'.join(current_content)
                chunks.append((f"Section {chunk_index}", content))
                chunk_index += 1
                
                # Start new chunk with overlap
                if self.overlap > 0 and current_content:
                    # Keep last paragraph as overlap
                    current_content = [current_content[-1]]
                    current_length = len(current_content[0])
                else:
                    current_content = []
                    current_length = 0
            
            current_content.append(para)
            current_length += para_length
        
        # Save final chunk
        if current_content:
            content = '\n\n'.join(current_content)
            if len(content) >= self.min_chunk_size:
                chunks.append((f"Section {chunk_index}", content))
            elif chunks:
                # Merge with previous
                prev_title, prev_content = chunks[-1]
                chunks[-1] = (prev_title, prev_content + '\n\n' + content)
        
        return chunks
    
    def _split_large_chunk(self, title: str, content: str) -> List[tuple]:
        """Split a large chunk into smaller pieces."""
        chunks = []
        
        # Try to split by paragraphs first
        paragraphs = re.split(r'\n\s*\n', content)
        
        current_content = []
        current_length = 0
        part = 1
        
        for para in paragraphs:
            if current_length + len(para) > self.max_chunk_size and current_content:
                chunks.append((f"{title} (Part {part})", '\n\n'.join(current_content)))
                part += 1
                current_content = []
                current_length = 0
            
            current_content.append(para)
            current_length += len(para)
        
        if current_content:
            chunk_title = f"{title} (Part {part})" if part > 1 else title
            chunks.append((chunk_title, '\n\n'.join(current_content)))
        
        return chunks
    
    async def _generate_chunk_summaries(
        self,
        chunks: List[DocumentChunk],
    ) -> List[DocumentChunk]:
        """Generate summaries for all chunks using LLM."""
        
        # Build a single prompt to summarize all chunks at once
        # This is more efficient than calling LLM for each chunk
        
        if len(chunks) <= 3:
            # For small number of chunks, summarize individually inline
            for chunk in chunks:
                chunk.summary = self._extract_first_sentence(chunk.content)
            return chunks
        
        # For larger documents, use LLM to generate summaries
        client = LLMClient()
        model = get_model()
        
        chunks_text = ""
        for chunk in chunks:
            chunks_text += f"\n[CHUNK {chunk.id}: {chunk.title}]\n{chunk.content[:500]}...\n"
        
        system_prompt = """You are a document analyzer. For each chunk provided, generate a brief 1-2 sentence summary capturing the key information, data points, and facts.

Output format - one line per chunk:
CHUNK 0: <summary>
CHUNK 1: <summary>
...

Be concise but capture the essential facts and data."""

        user_prompt = f"""Summarize each chunk:
{chunks_text}"""

        try:
            response = await client.generate(
                model=model,
                messages=[
                    LLMSystemMessage(content=system_prompt),
                    LLMUserMessage(content=user_prompt),
                ],
                max_tokens=1000,
            )
            
            # Parse response
            if response:
                for line in response.split('\n'):
                    match = re.match(r'CHUNK\s*(\d+)\s*:\s*(.+)', line, re.IGNORECASE)
                    if match:
                        chunk_id = int(match.group(1))
                        summary = match.group(2).strip()
                        if 0 <= chunk_id < len(chunks):
                            chunks[chunk_id].summary = summary
            
            # Fill in any missing summaries
            for chunk in chunks:
                if not chunk.summary:
                    chunk.summary = self._extract_first_sentence(chunk.content)
                    
        except Exception as e:
            print(f"Failed to generate chunk summaries: {e}")
            # Fall back to extractive summaries
            for chunk in chunks:
                chunk.summary = self._extract_first_sentence(chunk.content)
        
        return chunks
    
    def _extract_first_sentence(self, text: str) -> str:
        """Extract first sentence as a simple summary."""
        # Find first sentence ending
        match = re.match(r'^(.+?[.!?])\s', text)
        if match:
            return match.group(1)
        # If no sentence ending, take first 100 chars
        return text[:100].strip() + "..." if len(text) > 100 else text


def format_chunks_for_prompt(chunks: List[DocumentChunk]) -> str:
    """Format chunks for inclusion in a prompt."""
    result = "## Available Source Chunks\n\n"
    for chunk in chunks:
        result += f"[CHUNK {chunk.id}] {chunk.title}\n"
        result += f"Summary: {chunk.summary}\n\n"
    return result


def format_chunk_content_for_slide(
    chunks: List[dict],
    chunk_refs: List[int],
) -> str:
    """
    Format specific chunk contents for slide generation.
    
    Args:
        chunks: All available chunks (as dicts with 'id', 'title', 'content' keys)
        chunk_refs: List of chunk IDs to include
    
    Returns:
        Formatted string with referenced chunk contents
    """
    if not chunk_refs:
        return ""
    
    result = "## Source Reference Context\n\n"
    result += "Use the following source content as authoritative reference:\n\n"
    
    for ref_id in chunk_refs:
        if 0 <= ref_id < len(chunks):
            chunk = chunks[ref_id]
            # Support both dict and dataclass/model
            title = chunk.get("title", f"Chunk {ref_id}") if isinstance(chunk, dict) else chunk.title
            content = chunk.get("content", "") if isinstance(chunk, dict) else chunk.content
            result += f"### {title}\n"
            result += f"{content}\n\n"
    
    return result
