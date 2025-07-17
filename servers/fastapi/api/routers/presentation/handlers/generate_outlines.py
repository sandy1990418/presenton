import uuid

from api.models import LogMetadata
from api.routers.presentation.models import GenerateOutlinesRequest
from api.services.instances import TEMP_FILE_SERVICE
from api.services.logging import LoggingService
from api.sql_models import PresentationSqlModel
from ppt_config_generator.ppt_outlines_generator import generate_ppt_content
from api.services.database import get_sql_session
from ppt_config_generator.image_integration_service import image_integration_service


class PresentationOutlinesGenerateHandler:
    def __init__(self, data: GenerateOutlinesRequest):
        self.data = data

        self.session = str(uuid.uuid4())
        self.temp_dir = TEMP_FILE_SERVICE.create_temp_dir(self.session)

    def __del__(self):
        TEMP_FILE_SERVICE.cleanup_temp_dir(self.temp_dir)

    async def post(self, logging_service: LoggingService, log_metadata: LogMetadata):

        logging_service.logger.info(
            logging_service.message(self.data.model_dump(mode="json")),
            extra=log_metadata.model_dump(),
        )

        with get_sql_session() as sql_session:
            presentation = sql_session.get(
                PresentationSqlModel, self.data.presentation_id
            )

            # 智能圖片處理和整合（錯誤處理增強）
            image_processing_result = None
            if hasattr(presentation, 'images') and presentation.images:
                try:
                    # 獲取文檔路徑（如果有的話）
                    documents = getattr(presentation, 'documents', []) or []
                    
                    # 提取投影片標題（從prompt中推斷或使用占位符）
                    slide_titles = [f"投影片 {i+1}" for i in range(presentation.n_slides)]
                    
                    # 使用智能圖片處理器
                    image_processing_result = await image_integration_service.analyze_images_intelligent(
                        image_paths=presentation.images,
                        documents=documents,
                        presentation_prompt=presentation.prompt,
                        slide_titles=slide_titles
                    )
                    
                    logging_service.logger.info(
                        f"Intelligent image processing completed: {image_processing_result.get('total_images_analyzed', 0)} images analyzed",
                        extra=log_metadata.model_dump(),
                    )
                    
                except Exception as e:
                    logging_service.logger.error(
                        f"Error in intelligent image processing: {e}. Falling back to basic image analysis.",
                        extra=log_metadata.model_dump(),
                    )
                    # 回退到基本圖片分析
                    try:
                        analyzed_images = image_integration_service.analyze_images(presentation.images)
                        image_processing_result = {
                            'total_images_analyzed': len(analyzed_images),
                            'image_analyses': analyzed_images,
                            'slide_image_mapping': {},
                            'high_relevance_images': analyzed_images
                        }
                        logging_service.logger.info(
                            f"Fallback image analysis completed: {len(analyzed_images)} images",
                            extra=log_metadata.model_dump(),
                        )
                    except Exception as fallback_error:
                        logging_service.logger.error(
                            f"Fallback image analysis also failed: {fallback_error}. Continuing without images.",
                            extra=log_metadata.model_dump(),
                        )
                        image_processing_result = None

            presentation_content = await generate_ppt_content(
                presentation.prompt,
                presentation.n_slides,
                presentation.language,
                presentation.summary,
                image_processing_result,
            )
            presentation_content.slides = presentation_content.slides[
                : presentation.n_slides
            ]

            presentation.title = presentation_content.title
            presentation.outlines = [
                each.model_dump() for each in presentation_content.slides
            ]
            presentation.notes = presentation_content.notes

            sql_session.commit()
            sql_session.refresh(presentation)

        logging_service.logger.info(
            logging_service.message(presentation.model_dump(mode="json")),
            extra=log_metadata.model_dump(),
        )

        return presentation
