"""
智能圖片處理器 - 使用LLM分析和處理圖片嵌入
"""
import os
import base64
import tempfile
from typing import List, Dict, Optional, Any
from PIL import Image
import io
import logging
from api.utils.model_utils import get_llm_client, get_large_model

class IntelligentImageProcessor:
    """使用LLM智能處理圖片分析和嵌入的服務"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.model = None
        
    def _get_llm_client(self):
        """獲取LLM客戶端"""
        if self.client is None:
            self.client = get_llm_client()
            self.model = get_large_model()
        return self.client, self.model
    
    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """將圖片編碼為base64"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Error encoding image {image_path}: {e}")
            return None
    
    async def analyze_image_with_llm(self, image_path: str, presentation_context: str) -> Dict:
        """使用LLM分析圖片內容和相關性"""
        try:
            client, model = self._get_llm_client()
            
            # 將圖片編碼為base64
            base64_image = self.encode_image_to_base64(image_path)
            if not base64_image:
                return {"error": "Failed to encode image"}
            
            messages = [
                {
                    "role": "system",
                    "content": """你是一個專業的圖片分析師和演示專家。請分析提供的圖片，並評估它與演示主題的相關性。

請提供以下分析：
1. 圖片內容描述（詳細但簡潔）
2. 圖片類型（圖表、流程圖、照片、架構圖、數據可視化等）
3. 與演示主題的相關性評分（1-10）
4. 建議使用的投影片位置（開場、概念說明、案例研究、數據展示、總結等）
5. 圖片標題建議
6. 使用這張圖片的理由和價值

請以JSON格式回覆。"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""演示主題和內容：
{presentation_context}

請分析這張圖片並評估它與上述演示內容的相關性。"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            import json
            analysis = json.loads(response.choices[0].message.content)
            
            # 添加圖片路徑信息
            analysis['image_path'] = image_path
            analysis['image_filename'] = os.path.basename(image_path)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing image with LLM: {e}")
            return {
                "error": str(e),
                "image_path": image_path,
                "image_filename": os.path.basename(image_path) if image_path else "unknown"
            }
    
    async def batch_analyze_images(self, image_paths: List[str], presentation_context: str) -> List[Dict]:
        """批量分析多張圖片"""
        analyses = []
        
        for image_path in image_paths:
            if os.path.exists(image_path):
                analysis = await self.analyze_image_with_llm(image_path, presentation_context)
                analyses.append(analysis)
                self.logger.info(f"Analyzed image: {os.path.basename(image_path)}")
            else:
                self.logger.warning(f"Image not found: {image_path}")
        
        # 按相關性評分排序
        analyses.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return analyses
    
    async def generate_slide_image_mapping(self, image_analyses: List[Dict], slide_titles: List[str]) -> Dict[int, List[Dict]]:
        """使用LLM生成投影片與圖片的智能映射"""
        try:
            client, model = self._get_llm_client()
            
            # 準備圖片摘要
            image_summaries = []
            for i, analysis in enumerate(image_analyses):
                if 'error' not in analysis:
                    summary = f"圖片{i+1}: {analysis.get('description', 'No description')} (相關性: {analysis.get('relevance_score', 0)}/10)"
                    image_summaries.append(summary)
            
            # 準備投影片摘要
            slide_summaries = []
            for i, title in enumerate(slide_titles):
                slide_summaries.append(f"投影片{i+1}: {title}")
            
            messages = [
                {
                    "role": "system",
                    "content": """你是一個專業的演示設計師。請根據提供的圖片分析和投影片標題，為每張投影片智能分配最相關的圖片。

規則：
1. 每張投影片最多分配2張圖片
2. 優先選擇相關性評分高的圖片
3. 確保圖片與投影片內容高度相關
4. 避免重複使用同一張圖片
5. 如果沒有相關圖片，可以不分配

請以JSON格式回覆，格式如下：
{
    "mappings": [
        {
            "slide_index": 0,
            "slide_title": "投影片標題",
            "assigned_images": [
                {
                    "image_index": 0,
                    "image_filename": "圖片檔名",
                    "placement_suggestion": "圖片放置建議",
                    "usage_reason": "使用這張圖片的原因"
                }
            ]
        }
    ]
}"""
                },
                {
                    "role": "user",
                    "content": f"""可用圖片：
{chr(10).join(image_summaries)}

投影片：
{chr(10).join(slide_summaries)}

請為每張投影片智能分配最合適的圖片。"""
                }
            ]
            
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            import json
            mapping_result = json.loads(response.choices[0].message.content)
            
            # 轉換為投影片索引為鍵的字典
            slide_image_mapping = {}
            for mapping in mapping_result.get('mappings', []):
                slide_idx = mapping.get('slide_index')
                if slide_idx is not None:
                    slide_image_mapping[slide_idx] = []
                    for img_assignment in mapping.get('assigned_images', []):
                        img_idx = img_assignment.get('image_index')
                        if img_idx is not None and img_idx < len(image_analyses):
                            # 結合原始分析數據和分配建議
                            combined_info = {
                                **image_analyses[img_idx],
                                'placement_suggestion': img_assignment.get('placement_suggestion', ''),
                                'usage_reason': img_assignment.get('usage_reason', '')
                            }
                            slide_image_mapping[slide_idx].append(combined_info)
            
            return slide_image_mapping
            
        except Exception as e:
            self.logger.error(f"Error generating slide image mapping: {e}")
            return {}
    
    async def extract_pdf_images_with_analysis(self, pdf_path: str, presentation_context: str) -> List[Dict]:
        """從PDF提取圖片並進行智能分析（使用簡化方法）"""
        extracted_images = []
        
        try:
            # 檢查是否有pypdfium2或pdfplumber
            pdf_processor = None
            
            try:
                import pypdfium2 as pdfium2
                pdf_processor = 'pypdfium2'
            except ImportError:
                try:
                    import pdfplumber
                    pdf_processor = 'pdfplumber'
                except ImportError:
                    self.logger.warning("No PDF processing library available")
                    return []
            
            # 使用pypdfium2渲染PDF頁面為圖片
            if pdf_processor == 'pypdfium2':
                temp_dir = tempfile.mkdtemp()
                pdf = pdfium2.PdfDocument(pdf_path)
                
                for page_index in range(min(len(pdf), 10)):  # 限制最多10頁
                    try:
                        page = pdf.get_page(page_index)
                        pil_image = page.render(scale=2.0).to_pil()
                        
                        # 保存為臨時圖片
                        image_filename = f"pdf_page_{page_index + 1}.png"
                        image_path = os.path.join(temp_dir, image_filename)
                        pil_image.save(image_path)
                        
                        # 使用LLM分析圖片
                        analysis = await self.analyze_image_with_llm(image_path, presentation_context)
                        analysis['source'] = 'pdf_page'
                        analysis['page_number'] = page_index + 1
                        
                        extracted_images.append(analysis)
                        
                    except Exception as e:
                        self.logger.error(f"Error processing PDF page {page_index}: {e}")
                        continue
                
                pdf.close()
            
            # 如果使用pdfplumber，嘗試提取圖片（功能有限）
            elif pdf_processor == 'pdfplumber':
                self.logger.info("Using pdfplumber - limited image extraction capability")
                # pdfplumber主要用於文本，圖片提取功能有限
                # 這裡可以記錄文檔存在，但不提取圖片
                
        except Exception as e:
            self.logger.error(f"Error extracting PDF images: {e}")
        
        return extracted_images
    
    async def process_presentation_images(self, 
                                        direct_images: List[str], 
                                        document_paths: List[str],
                                        presentation_prompt: str,
                                        slide_titles: List[str]) -> Dict:
        """完整的智能圖片處理流程"""
        
        all_image_analyses = []
        
        # 分析直接上傳的圖片
        if direct_images:
            self.logger.info(f"Analyzing {len(direct_images)} directly uploaded images")
            direct_analyses = await self.batch_analyze_images(direct_images, presentation_prompt)
            for analysis in direct_analyses:
                analysis['source_type'] = 'direct_upload'
            all_image_analyses.extend(direct_analyses)
        
        # 從文檔中提取並分析圖片
        for doc_path in document_paths:
            if doc_path.lower().endswith('.pdf'):
                self.logger.info(f"Extracting and analyzing images from PDF: {os.path.basename(doc_path)}")
                pdf_analyses = await self.extract_pdf_images_with_analysis(doc_path, presentation_prompt)
                all_image_analyses.extend(pdf_analyses)
        
        # 使用LLM生成智能的投影片-圖片映射
        slide_image_mapping = {}
        if all_image_analyses and slide_titles:
            self.logger.info("Generating intelligent slide-image mapping")
            slide_image_mapping = await self.generate_slide_image_mapping(all_image_analyses, slide_titles)
        
        return {
            'total_images_analyzed': len(all_image_analyses),
            'image_analyses': all_image_analyses,
            'slide_image_mapping': slide_image_mapping,
            'high_relevance_images': [img for img in all_image_analyses if img.get('relevance_score', 0) >= 7]
        }
    
    def generate_enhanced_prompt_with_images(self, 
                                           original_prompt: str, 
                                           image_processing_result: Dict) -> str:
        """生成包含圖片信息的增強提示"""
        
        if not image_processing_result.get('image_analyses'):
            return original_prompt
        
        enhanced_prompt = original_prompt + "\n\n"
        enhanced_prompt += "**智能圖片分析結果:**\n"
        enhanced_prompt += f"已分析 {image_processing_result['total_images_analyzed']} 張圖片，以下是高相關性圖片（評分≥7）：\n\n"
        
        high_relevance_images = image_processing_result.get('high_relevance_images', [])
        
        for i, img_analysis in enumerate(high_relevance_images[:5]):  # 最多顯示5張高相關圖片
            enhanced_prompt += f"**圖片 {i+1}**: {img_analysis.get('image_filename', 'Unknown')}\n"
            enhanced_prompt += f"- 內容: {img_analysis.get('description', 'No description')}\n"
            enhanced_prompt += f"- 類型: {img_analysis.get('image_type', 'Unknown')}\n"
            enhanced_prompt += f"- 相關性: {img_analysis.get('relevance_score', 0)}/10\n"
            enhanced_prompt += f"- 建議用途: {img_analysis.get('suggested_usage', 'General use')}\n\n"
        
        # 添加投影片映射信息
        if image_processing_result.get('slide_image_mapping'):
            enhanced_prompt += "**投影片圖片分配:**\n"
            for slide_idx, images in image_processing_result['slide_image_mapping'].items():
                enhanced_prompt += f"- 投影片 {slide_idx + 1}: "
                image_names = [img.get('image_filename', 'Unknown') for img in images]
                enhanced_prompt += ", ".join(image_names) + "\n"
        
        enhanced_prompt += "\n**請在生成演示內容時：**\n"
        enhanced_prompt += "1. 在相應的投影片中明確引用這些圖片\n"
        enhanced_prompt += "2. 在 visual_suggestions 字段中詳細說明每張圖片的使用方式\n"
        enhanced_prompt += "3. 在 speaker_notes 中包含圖片的講解要點\n"
        enhanced_prompt += "4. 確保內容與圖片所展示的信息高度一致\n\n"
        
        return enhanced_prompt

# 全局服務實例
intelligent_image_processor = IntelligentImageProcessor()