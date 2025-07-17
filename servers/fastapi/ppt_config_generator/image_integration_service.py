"""
圖片整合服務 - 處理參考圖片的分析和整合到PPT中
"""
import base64
import os
from typing import List, Optional, Dict
from PIL import Image
import json

class ImageIntegrationService:
    """處理圖片整合到PPT生成過程中的服務"""
    
    def __init__(self):
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
    def analyze_images(self, image_paths: List[str]) -> List[Dict]:
        """分析圖片並提取相關信息"""
        analyzed_images = []
        
        for i, image_path in enumerate(image_paths):
            try:
                if not os.path.exists(image_path):
                    continue
                    
                # 獲取圖片基本信息
                with Image.open(image_path) as img:
                    width, height = img.size
                    format_type = img.format.lower() if img.format else 'unknown'
                    
                # 分析圖片類型和內容
                image_info = {
                    'id': f'image_{i+1}',
                    'path': image_path,
                    'filename': os.path.basename(image_path),
                    'dimensions': f'{width}x{height}',
                    'format': format_type,
                    'aspect_ratio': round(width/height, 2),
                    'size_category': self._categorize_image_size(width, height),
                    'content_type': self._analyze_image_content(image_path),
                    'suggested_placement': self._suggest_placement(width, height),
                    'description': self._generate_image_description(image_path, format_type)
                }
                
                analyzed_images.append(image_info)
                
            except Exception as e:
                print(f"Error analyzing image {image_path}: {e}")
                continue
        
        return analyzed_images
    
    def _categorize_image_size(self, width: int, height: int) -> str:
        """根據尺寸分類圖片"""
        total_pixels = width * height
        
        if total_pixels < 100000:  # < 100K pixels
            return 'small'
        elif total_pixels < 1000000:  # < 1M pixels
            return 'medium'
        else:
            return 'large'
    
    def _analyze_image_content(self, image_path: str) -> str:
        """分析圖片內容類型"""
        filename = os.path.basename(image_path).lower()
        
        # 基於檔名推測內容類型
        if any(keyword in filename for keyword in ['chart', 'graph', 'plot', 'data']):
            return 'chart_graph'
        elif any(keyword in filename for keyword in ['logo', 'brand', 'icon']):
            return 'logo_brand'
        elif any(keyword in filename for keyword in ['photo', 'picture', 'image']):
            return 'photograph'
        elif any(keyword in filename for keyword in ['diagram', 'flow', 'process']):
            return 'diagram'
        elif any(keyword in filename for keyword in ['screen', 'ui', 'interface']):
            return 'screenshot'
        else:
            return 'general'
    
    def _suggest_placement(self, width: int, height: int) -> str:
        """建議圖片放置位置"""
        aspect_ratio = width / height
        
        if aspect_ratio > 1.5:  # 寬圖
            return 'full_width'
        elif aspect_ratio < 0.75:  # 高圖
            return 'side_panel'
        else:  # 正方形或接近正方形
            return 'center_content'
    
    def _generate_image_description(self, image_path: str, format_type: str) -> str:
        """生成圖片描述"""
        filename = os.path.basename(image_path)
        content_type = self._analyze_image_content(image_path)
        
        descriptions = {
            'chart_graph': f'數據圖表 ({filename}) - 建議用於支持統計數據或趨勢說明',
            'logo_brand': f'品牌標誌 ({filename}) - 適合放置在標題頁或品牌介紹頁面',
            'photograph': f'照片圖像 ({filename}) - 可用於增強視覺效果或提供實例',
            'diagram': f'流程圖表 ({filename}) - 適合說明過程或系統架構',
            'screenshot': f'界面截圖 ({filename}) - 用於展示產品或系統功能',
            'general': f'參考圖片 ({filename}) - 可根據內容需要靈活使用'
        }
        
        return descriptions.get(content_type, f'圖片 ({filename}) - 可用於支持演示內容')
    
    def generate_image_integration_prompts(self, analyzed_images: List[Dict]) -> str:
        """生成圖片整合的提示文本"""
        if not analyzed_images:
            return ""
        
        prompt = f"\n\n**參考圖片分析與整合建議:**\n"
        prompt += f"共提供 {len(analyzed_images)} 張參考圖片，請根據以下分析結果將圖片有效整合到演示文稿中：\n\n"
        
        for img in analyzed_images:
            prompt += f"• **{img['id']}** ({img['filename']}):\n"
            prompt += f"  - 類型: {img['content_type']}\n"
            prompt += f"  - 尺寸: {img['dimensions']} ({img['size_category']})\n"
            prompt += f"  - 建議放置: {img['suggested_placement']}\n"
            prompt += f"  - 說明: {img['description']}\n"
            prompt += f"  - 整合建議: 請在相關投影片的 visual_suggestions 字段中明確指定此圖片的使用方式\n\n"
        
        prompt += "**圖片整合要求:**\n"
        prompt += "1. 在每張投影片的 visual_suggestions 字段中具體說明要使用哪些圖片\n"
        prompt += "2. 為每張圖片提供具體的放置位置和說明文字\n"
        prompt += "3. 確保圖片與投影片內容高度相關\n"
        prompt += "4. 在 speaker_notes 中包含圖片的講解要點\n\n"
        
        return prompt
    
    def create_image_references_for_slides(self, analyzed_images: List[Dict], slide_count: int) -> Dict[int, List[Dict]]:
        """為投影片創建圖片引用映射"""
        image_references = {}
        
        if not analyzed_images:
            return image_references
        
        # 均勻分配圖片到投影片
        images_per_slide = len(analyzed_images) // slide_count
        remaining_images = len(analyzed_images) % slide_count
        
        current_image_index = 0
        
        for slide_index in range(slide_count):
            slide_images = []
            
            # 計算這張投影片應該有多少圖片
            images_for_this_slide = images_per_slide
            if slide_index < remaining_images:
                images_for_this_slide += 1
            
            # 分配圖片
            for _ in range(images_for_this_slide):
                if current_image_index < len(analyzed_images):
                    slide_images.append(analyzed_images[current_image_index])
                    current_image_index += 1
            
            if slide_images:
                image_references[slide_index] = slide_images
        
        return image_references

# 全局服務實例
image_integration_service = ImageIntegrationService()