from enum import Enum
from typing import List, Mapping, Union, Optional
from pydantic import BaseModel

from graph_processor.models import GraphModel, LLMGraphModel
from ppt_generator.models.other_models import (
    TYPE1,
    TYPE2,
    TYPE3,
    TYPE4,
    TYPE5,
    TYPE6,
    TYPE7,
    TYPE8,
    TYPE9,
)


class TableType(Enum):
    TABLE = "table"
    BAR = "bar"
    LINE = "line"
    PIE = "pie"


class TableDataModel(BaseModel):
    x_labels: List[str]
    y_labels: List[str]
    data: List[List[float]]


class TableModel(BaseModel):
    name: str
    type: TableType
    data: TableDataModel


class HeadingModel(BaseModel):
    heading: str
    description: str

    def to_llm_content(self, image_prompt: str = None, icon_query: str = None):
        from ppt_generator.models.llm_models import (
            LLMHeadingModel,
            LLMHeadingModelWithImagePrompt,
            LLMHeadingModelWithIconQuery,
        )

        if image_prompt:
            return LLMHeadingModelWithImagePrompt(
                heading=self.heading,
                description=self.description,
                image_prompt=image_prompt,
            )
        elif icon_query:
            return LLMHeadingModelWithIconQuery(
                heading=self.heading,
                description=self.description,
                icon_query=icon_query,
            )
        return LLMHeadingModel(
            heading=self.heading,
            description=self.description,
        )


class SlideContentModel(BaseModel):
    title: str


class Type1Content(SlideContentModel):
    body: str
    image_prompts: List[str]

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType1Content

        return LLMType1Content(
            title=self.title,
            body=self.body,
            image_prompt=self.image_prompts[0] if self.image_prompts else "",
        )


class Type2Content(SlideContentModel):
    body: List[HeadingModel]

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType2Content

        return LLMType2Content(
            title=self.title,
            body=[item.to_llm_content() for item in self.body],
        )


class Type3Content(SlideContentModel):
    body: List[HeadingModel]
    image_prompts: List[str]

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType3Content

        return LLMType3Content(
            title=self.title,
            body=[item.to_llm_content() for item in self.body],
            image_prompt=self.image_prompts[0] if self.image_prompts else "",
        )


class Type4Content(SlideContentModel):
    body: List[HeadingModel]
    image_prompts: List[str]

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType4Content

        llm_body = []
        for i, item in enumerate(self.body):
            image_prompt = self.image_prompts[i] if i < len(self.image_prompts) else ""
            llm_body.append(item.to_llm_content(image_prompt=image_prompt))
        return LLMType4Content(
            title=self.title,
            body=llm_body,
        )


class Type5Content(SlideContentModel):
    body: str
    # table: TableModel
    graph: GraphModel

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType5Content

        return LLMType5Content(
            title=self.title,
            body=self.body,
            # table=self.table,
            graph=self.graph,
        )


class Type6Content(SlideContentModel):
    description: str
    body: List[HeadingModel]

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType6Content

        return LLMType6Content(
            title=self.title,
            description=self.description,
            body=[item.to_llm_content() for item in self.body],
        )


class Type7Content(SlideContentModel):
    body: List[HeadingModel]
    icon_queries: Optional[List[str]] = None

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType7Content

        llm_body = []
        icon_queries = self.icon_queries or []
        for i, item in enumerate(self.body):
            # 確保總是有 icon_query，即使是空字符串也要傳遞，這樣會返回 LLMHeadingModelWithIconQuery
            icon_query = icon_queries[i] if i < len(icon_queries) else "default"
            # 強制使用 icon_query 路徑以確保類型一致性
            if not icon_query.strip():
                icon_query = "default"
            llm_body.append(item.to_llm_content(icon_query=icon_query))
        return LLMType7Content(
            title=self.title,
            body=llm_body,
        )


class Type8Content(SlideContentModel):
    description: str
    body: List[HeadingModel]
    icon_queries: Optional[List[str]] = None

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType8Content

        llm_body = []
        icon_queries = self.icon_queries or []
        for i, item in enumerate(self.body):
            # Type8 使用 image_prompt 而不是 icon_query，所以使用 image_prompt 參數
            icon_query = icon_queries[i] if i < len(icon_queries) else "default"
            # 強制使用 image_prompt 路徑以確保類型一致性
            if not icon_query.strip():
                icon_query = "default"
            llm_body.append(item.to_llm_content(image_prompt=icon_query))
        return LLMType8Content(
            title=self.title,
            description=self.description,
            body=llm_body,
        )


class Type9Content(SlideContentModel):
    body: List[HeadingModel]
    # table: TableModel
    graph: GraphModel

    def to_llm_content(self):
        from ppt_generator.models.llm_models import LLMType9Content

        return LLMType9Content(
            title=self.title,
            body=[item.to_llm_content() for item in self.body],
            # table=self.table,
            graph=self.graph,
        )


ContentUnion = Union[
    Type1Content,
    Type2Content,
    Type3Content,
    Type4Content,
    Type5Content,
    Type6Content,
    Type7Content,
    Type8Content,
    Type9Content,
]

CONTENT_TYPE_MAPPING: Mapping[int, ContentUnion] = {
    TYPE1: Type1Content,
    TYPE2: Type2Content,
    TYPE3: Type3Content,
    TYPE4: Type4Content,
    TYPE5: Type5Content,
    TYPE6: Type6Content,
    TYPE7: Type7Content,
    TYPE8: Type8Content,
    TYPE9: Type9Content,
}
