"""
Refactored document parsing services with clean architecture.
"""

import os
import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from docling.document_converter import DocumentConverter as DoclingDocumentConverter, PdfFormatOption, PowerpointFormatOption, WordFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from mixins.logging_mixin import LoggingMixin
from services import TEMP_FILE_SERVICE


@dataclass
class ParseResult:
    """Document parsing result."""
    markdown_content: str
    output_directory: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ConversionConfig:
    """Document conversion configuration."""
    supported_extensions: List[str]
    timeout_seconds: int = 60
    cleanup_temp_files: bool = True


class DocumentConverter(ABC):
    """Abstract base class for document converters."""
    
    @abstractmethod
    def convert_to_pdf(self, file_path: str, output_dir: str) -> str:
        """Convert document to PDF format."""
        pass
    
    @abstractmethod
    def is_supported(self, file_extension: str) -> bool:
        """Check if file extension is supported."""
        pass


class LibreOfficeConverter(DocumentConverter, LoggingMixin):
    """LibreOffice-based document converter."""
    
    def __init__(self, config: ConversionConfig):
        super().__init__()
        self.config = config
        self._command = self._get_platform_command()
    
    def _get_platform_command(self) -> str:
        """Get platform-specific LibreOffice command."""
        import platform
        
        if platform.system().lower() == 'darwin':
            return '/Applications/LibreOffice.app/Contents/MacOS/soffice'
        return 'libreoffice'
    
    def convert_to_pdf(self, file_path: str, output_dir: str) -> str:
        """Convert document to PDF using LibreOffice."""
        if not self.is_supported(Path(file_path).suffix):
            raise ValueError(f"Unsupported file type: {file_path}")
        
        output_path = self._build_output_path(file_path, output_dir)
        command = self._build_conversion_command(file_path, output_dir)
        
        self._execute_conversion(command, output_path)
        return output_path
    
    def _build_output_path(self, file_path: str, output_dir: str) -> str:
        """Build expected PDF output path."""
        stem = Path(file_path).stem
        return os.path.join(output_dir, f"{stem}.pdf")
    
    def _build_conversion_command(self, file_path: str, output_dir: str) -> List[str]:
        """Build LibreOffice conversion command."""
        return [
            self._command,
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            file_path
        ]
    
    def _execute_conversion(self, command: List[str], expected_output: str) -> None:
        """Execute conversion command and validate result."""
        self.log_external_service_call("LibreOffice", "pdf_conversion")
        
        try:
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                timeout=self.config.timeout_seconds
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Conversion failed: {result.stderr}")
            
            if not os.path.exists(expected_output):
                raise RuntimeError(f"Output file not created: {expected_output}")
                
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Conversion timeout after {self.config.timeout_seconds}s")
    
    def is_supported(self, file_extension: str) -> bool:
        """Check if file extension is supported."""
        return file_extension.lower() in self.config.supported_extensions


class MinerUConfigManager:
    """Manages MinerU configuration loading and validation."""
    
    DEFAULT_CONFIG_PATHS = [
        "./mineru.json",
        "~/mineru.json",
        "/etc/mineru/config.json"
    ]
    
    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load MinerU configuration from file."""
        paths_to_try = [config_path] if config_path else cls.DEFAULT_CONFIG_PATHS
        
        for path in paths_to_try:
            if path and cls._try_load_config_file(path):
                return cls._try_load_config_file(path)
        
        return {}
    
    @staticmethod
    def _try_load_config_file(path: str) -> Optional[Dict[str, Any]]:
        """Try to load config from a specific path."""
        try:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                with open(expanded_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return None


class MinerUCLI(LoggingMixin):
    """MinerU command-line interface wrapper."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self._setup_environment()
        self._validate_cli_availability()
    
    def _setup_environment(self) -> None:
        """Setup environment variables from config."""
        env_mappings = {
            'model-dir': 'MINERU_MODELS_DIR',
            'device-mode': 'MINERU_DEVICE_MODE',
            'model-source': 'MINERU_MODEL_SOURCE'
        }
        
        for config_key, env_key in env_mappings.items():
            if config_key in self.config:
                os.environ[env_key] = str(self.config[config_key])
    
    def _validate_cli_availability(self) -> None:
        """Validate that MinerU CLI is available."""
        try:
            result = subprocess.run(['mineru', '--version'], capture_output=True, timeout=10)
            if result.returncode != 0:
                raise RuntimeError("MinerU CLI not responding correctly")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            raise RuntimeError("MinerU CLI not available in PATH")
    
    def parse_document(self, pdf_path: str, output_dir: str) -> subprocess.CompletedProcess:
        """Parse document using MinerU CLI."""
        command = ['mineru', pdf_path, '--output', output_dir]
        
        self.log_external_service_call("MinerU", "document_parsing", file_path=pdf_path)
        
        return subprocess.run(command, capture_output=True, text=True, timeout=300)


class MarkdownExtractor(LoggingMixin):
    """Extracts and processes markdown from MinerU output."""
    
    MARKDOWN_PATTERNS = [
        "{file_stem}.md",
        "{file_stem}/{file_stem}.md", 
        "auto/{file_stem}.md",
        "output.md",
        "content.md"
    ]
    
    def extract_markdown(self, output_dir: str, original_file: str) -> str:
        """Extract markdown content from MinerU output directory."""
        file_stem = Path(original_file).stem
        
        for pattern in self.MARKDOWN_PATTERNS:
            md_path = os.path.join(output_dir, pattern.format(file_stem=file_stem))
            if os.path.exists(md_path):
                return self._read_and_process_markdown(md_path)
        
        raise FileNotFoundError(f"No markdown output found in {output_dir}")
    
    def _read_and_process_markdown(self, file_path: str) -> str:
        """Read and post-process markdown content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._post_process_markdown(content)
            
        except Exception as e:
            self.logger.warning(f"Failed to read markdown file {file_path}: {e}")
            return f"# Error reading markdown\n\nFailed to read file: {e}"
    
    def _post_process_markdown(self, content: str) -> str:
        """Post-process markdown for better formatting."""
        import re
        
        # Remove excessive blank lines
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()


class DoclingService:
    """Document parsing service using Docling library."""
    
    def __init__(self):
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = False
        
        self.converter = DoclingDocumentConverter(
            allowed_formats=[InputFormat.PPTX, InputFormat.PDF, InputFormat.DOCX],
            format_options={
                InputFormat.DOCX: WordFormatOption(pipeline_options=self.pipeline_options),
                InputFormat.PPTX: PowerpointFormatOption(pipeline_options=self.pipeline_options),
                InputFormat.PDF: PdfFormatOption(pipeline_options=self.pipeline_options),
            },
        )

    def parse_to_markdown(self, file_path: str) -> str:
        """Parse document to markdown format."""
        result = self.converter.convert(file_path)
        return result.document.export_to_markdown()


class MinerUService(LoggingMixin):
    """Clean, modular MinerU document parsing service."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize MinerU service with clean architecture."""
        super().__init__()
        
        # Load configuration
        self.config = MinerUConfigManager.load_config(config_path)
        
        # Initialize components
        conversion_config = ConversionConfig(
            supported_extensions=['.docx', '.pptx', '.doc', '.ppt'],
            timeout_seconds=60,
            cleanup_temp_files=True
        )
        
        self.converter = LibreOfficeConverter(conversion_config)
        self.mineru_cli = MinerUCLI(self.config)
        self.markdown_extractor = MarkdownExtractor()
        
        self.log_request_start("MinerU service initialization")
    
    def parse_to_markdown(self, file_path: str) -> ParseResult:
        """
        Parse document to markdown with clean separation of concerns.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            ParseResult containing markdown content and metadata
        """
        try:
            self.log_request_start("document_parsing", file_path=file_path)
            
            # Setup
            output_dir = TEMP_FILE_SERVICE.create_temp_dir("mineru_output")
            pdf_path = self._ensure_pdf_format(file_path, output_dir)
            
            # Parse
            result = self.mineru_cli.parse_document(pdf_path, output_dir)
            self._validate_parsing_result(result)
            
            # Extract
            markdown_content = self.markdown_extractor.extract_markdown(output_dir, file_path)
            
            # Cleanup
            self._cleanup_if_needed(pdf_path, file_path)
            
            # Result
            parse_result = ParseResult(
                markdown_content=markdown_content,
                output_directory=output_dir,
                metadata={"original_file": file_path, "pdf_path": pdf_path}
            )
            
            self.log_request_success("document_parsing", file_path=file_path)
            return parse_result
            
        except Exception as e:
            self.log_request_error("document_parsing", e, file_path=file_path)
            raise
    
    def _ensure_pdf_format(self, file_path: str, output_dir: str) -> str:
        """Ensure document is in PDF format, convert if necessary."""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.pdf':
            return file_path
        
        if not self.converter.is_supported(file_extension):
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        return self.converter.convert_to_pdf(file_path, output_dir)
    
    def _validate_parsing_result(self, result: subprocess.CompletedProcess) -> None:
        """Validate MinerU parsing result."""
        if result.returncode != 0:
            raise RuntimeError(f"MinerU parsing failed: {result.stderr}")
    
    def _cleanup_if_needed(self, pdf_path: str, original_path: str) -> None:
        """Clean up temporary files if needed."""
        if pdf_path != original_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                self.logger.info("Cleaned up temporary PDF", file=pdf_path)
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {pdf_path}: {e}")
    
    def is_supported(self, file_path: str) -> bool:
        """Check if file type is supported."""
        extension = Path(file_path).suffix.lower()
        return extension == '.pdf' or self.converter.is_supported(extension)
    
    # Backward compatibility method
    def parse_to_markdown_legacy(self, file_path: str) -> Tuple[str, str]:
        """
        Legacy method for backward compatibility.
        Returns tuple of (markdown_content, output_directory) instead of ParseResult.
        """
        result = self.parse_to_markdown(file_path)
        return result.markdown_content, result.output_directory
