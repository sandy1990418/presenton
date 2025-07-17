"""
文件圖片提取服務 - 從PDF、Word等文件中自動提取圖片
"""
import os
import tempfile
import shutil
from typing import List, Dict, Optional
try:
    import pypdfium2 as pdfium2
    PYPDFIUM2_AVAILABLE = True
except ImportError:
    PYPDFIUM2_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
from PIL import Image
import io
import base64
from pathlib import Path
import logging

try:
    from docx import Document
    from docx.document import Document as DocumentType
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

class DocumentImageExtractor:
    """從各種文件格式中提取圖片的服務"""
    
    def __init__(self):
        self.supported_formats = {'.pdf', '.docx', '.doc'}
        self.image_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        self.logger = logging.getLogger(__name__)
        
        # Check available libraries
        if not (PYPDFIUM2_AVAILABLE or PDFPLUMBER_AVAILABLE):
            self.logger.warning("PDF processing libraries not available. PDF extraction will be disabled.")
            self.supported_formats.discard('.pdf')
        
        if not DOCX_AVAILABLE:
            self.logger.warning("python-docx not available. DOCX extraction will be disabled.")
            self.supported_formats.discard('.docx')
            self.supported_formats.discard('.doc')
    
    def extract_images_from_document(self, document_path: str, output_dir: Optional[str] = None) -> List[Dict]:
        """
        從文件中提取所有圖片
        
        Args:
            document_path: 文件路徑
            output_dir: 輸出目錄，如果不提供則使用臨時目錄
            
        Returns:
            提取的圖片信息列表
        """
        if not os.path.exists(document_path):
            self.logger.error(f"Document not found: {document_path}")
            return []
        
        file_extension = Path(document_path).suffix.lower()
        
        if file_extension not in self.supported_formats:
            self.logger.warning(f"Unsupported document format: {file_extension}")
            return []
        
        # 創建輸出目錄
        if output_dir is None:
            output_dir = tempfile.mkdtemp()
        
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            if file_extension == '.pdf' and (PYPDFIUM2_AVAILABLE or PDFPLUMBER_AVAILABLE):
                return self._extract_from_pdf(document_path, output_dir)
            elif file_extension in ['.docx', '.doc'] and DOCX_AVAILABLE:
                return self._extract_from_docx(document_path, output_dir)
            else:
                self.logger.warning(f"No handler available for format: {file_extension}")
                return []
        except Exception as e:
            self.logger.error(f"Error extracting images from {document_path}: {e}")
            return []
    
    def _extract_from_pdf(self, pdf_path: str, output_dir: str) -> List[Dict]:
        """從PDF文件中提取圖片"""
        extracted_images = []
        
        try:
            # 打開PDF文件
            pdf_document = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # 獲取圖片數據
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_document, xref)
                        
                        # 確保圖片不是CMYK格式
                        if pix.n - pix.alpha < 4:
                            # 生成文件名
                            image_filename = f"pdf_page{page_num + 1}_img{img_index + 1}.png"
                            image_path = os.path.join(output_dir, image_filename)
                            
                            # 保存圖片
                            pix.save(image_path)
                            
                            # 獲取圖片信息
                            image_info = self._get_image_info(image_path, page_num + 1, img_index + 1, 'pdf')
                            extracted_images.append(image_info)
                            
                            self.logger.info(f"Extracted image: {image_filename}")
                        
                        pix = None  # 釋放內存
                        
                    except Exception as e:
                        self.logger.error(f"Error extracting image {img_index} from page {page_num}: {e}")
                        continue
            
            pdf_document.close()
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {e}")
        
        return extracted_images
    
    def _extract_from_docx(self, docx_path: str, output_dir: str) -> List[Dict]:
        """從DOCX文件中提取圖片"""
        if not DOCX_AVAILABLE:
            self.logger.error("python-docx not available. Install with: pip install python-docx")
            return []
        
        extracted_images = []
        
        try:
            # 打開Word文檔
            doc = Document(docx_path)
            
            # 從文檔關係中提取圖片
            image_count = 0
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    try:
                        # 獲取圖片數據
                        image_data = rel.target_part.blob
                        
                        # 確定圖片格式
                        image_format = self._detect_image_format(image_data)
                        if not image_format:
                            continue
                        
                        # 生成文件名
                        image_filename = f"docx_img{image_count + 1}.{image_format}"
                        image_path = os.path.join(output_dir, image_filename)
                        
                        # 保存圖片
                        with open(image_path, 'wb') as f:
                            f.write(image_data)
                        
                        # 獲取圖片信息
                        image_info = self._get_image_info(image_path, None, image_count + 1, 'docx')
                        extracted_images.append(image_info)
                        
                        image_count += 1
                        self.logger.info(f"Extracted image: {image_filename}")
                        
                    except Exception as e:
                        self.logger.error(f"Error extracting image {image_count}: {e}")
                        continue
        
        except Exception as e:
            self.logger.error(f"Error processing DOCX {docx_path}: {e}")
        
        return extracted_images
    
    def _detect_image_format(self, image_data: bytes) -> Optional[str]:
        """檢測圖片格式"""
        try:
            image = Image.open(io.BytesIO(image_data))
            format_name = image.format.lower() if image.format else None
            image.close()
            return format_name
        except Exception:
            return None
    
    def _get_image_info(self, image_path: str, page_num: Optional[int], img_index: int, source_type: str) -> Dict:
        """獲取圖片的詳細信息"""
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                format_type = img.format.lower() if img.format else 'unknown'
                
            file_size = os.path.getsize(image_path)
            
            # 生成圖片描述
            description = self._generate_extraction_description(
                os.path.basename(image_path), 
                source_type, 
                page_num, 
                img_index,
                width, 
                height
            )
            
            return {
                'id': f'extracted_{source_type}_{img_index}',
                'path': image_path,
                'filename': os.path.basename(image_path),
                'dimensions': f'{width}x{height}',
                'format': format_type,
                'file_size': file_size,
                'aspect_ratio': round(width/height, 2),
                'source_type': source_type,
                'page_number': page_num,
                'image_index': img_index,
                'content_type': self._analyze_extracted_image_content(image_path),
                'suggested_placement': self._suggest_placement_for_extracted(width, height),
                'description': description,
                'extraction_source': f'{source_type}_document'
            }
            
        except Exception as e:
            self.logger.error(f"Error getting image info for {image_path}: {e}")
            return {
                'id': f'extracted_{source_type}_{img_index}',
                'path': image_path,
                'filename': os.path.basename(image_path),
                'error': str(e),
                'source_type': source_type,
                'page_number': page_num,
                'image_index': img_index
            }
    
    def _analyze_extracted_image_content(self, image_path: str) -> str:
        """分析提取圖片的內容類型"""
        filename = os.path.basename(image_path).lower()
        
        # 基於檔名和特徵推測內容類型
        if 'chart' in filename or 'graph' in filename:
            return 'chart_graph'
        elif 'diagram' in filename or 'flow' in filename:
            return 'diagram'
        elif 'logo' in filename or 'brand' in filename:
            return 'logo_brand'
        elif 'screenshot' in filename or 'screen' in filename:
            return 'screenshot'
        else:
            return 'document_image'
    
    def _suggest_placement_for_extracted(self, width: int, height: int) -> str:
        """為提取的圖片建議放置位置"""
        aspect_ratio = width / height
        
        if aspect_ratio > 1.8:  # 很寬的圖
            return 'full_width_header'
        elif aspect_ratio > 1.3:  # 寬圖
            return 'full_width_content'
        elif aspect_ratio < 0.6:  # 高圖
            return 'side_panel_right'
        else:  # 正方形或接近正方形
            return 'center_content'
    
    def _generate_extraction_description(self, filename: str, source_type: str, page_num: Optional[int], img_index: int, width: int, height: int) -> str:
        """生成提取圖片的描述"""
        source_info = f"從 {source_type.upper()} 文件中提取"
        if page_num:
            source_info += f"（第 {page_num} 頁）"
        
        size_info = f"尺寸 {width}x{height}"
        
        # 根據尺寸和比例推測用途
        aspect_ratio = width / height
        if aspect_ratio > 1.5:
            usage_suggestion = "適合作為頁眉圖片或寬版內容展示"
        elif aspect_ratio < 0.75:
            usage_suggestion = "適合作為側邊欄圖片或垂直流程圖"
        else:
            usage_suggestion = "適合作為主要內容圖片或圖表"
        
        return f"{source_info} - {size_info} - {usage_suggestion}"
    
    def extract_and_analyze_batch(self, document_paths: List[str], output_base_dir: Optional[str] = None) -> Dict[str, List[Dict]]:
        """
        批量處理多個文件並提取圖片
        
        Args:
            document_paths: 文件路徑列表
            output_base_dir: 輸出基礎目錄
            
        Returns:
            按文件分組的圖片信息字典
        """
        if output_base_dir is None:
            output_base_dir = tempfile.mkdtemp()
        
        results = {}
        
        for doc_path in document_paths:
            if not os.path.exists(doc_path):
                self.logger.warning(f"Document not found: {doc_path}")
                continue
            
            # 為每個文件創建子目錄
            doc_name = Path(doc_path).stem
            doc_output_dir = os.path.join(output_base_dir, doc_name)
            
            try:
                extracted_images = self.extract_images_from_document(doc_path, doc_output_dir)
                results[doc_path] = extracted_images
                
                self.logger.info(f"Extracted {len(extracted_images)} images from {doc_path}")
                
            except Exception as e:
                self.logger.error(f"Error processing document {doc_path}: {e}")
                results[doc_path] = []
        
        return results
    
    def cleanup_extracted_images(self, output_dir: str):
        """清理提取的圖片文件"""
        try:
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
                self.logger.info(f"Cleaned up extracted images directory: {output_dir}")
        except Exception as e:
            self.logger.error(f"Error cleaning up directory {output_dir}: {e}")

# 全局服務實例
document_image_extractor = DocumentImageExtractor()