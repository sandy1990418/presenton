export type TextType =
  | "title"
  | "heading 1"
  | "heading 2"
  | "heading 3"
  | "heading 4"
  | "normal text";
export interface TextSize {
  fontSize: number;
  lineHeight: number;
  fontWeight: string;
}

interface SlideContent {
  title: string;
  body: string | Array<{ heading: string; description: string }>;
  description?: string;
  graph?: any;
  diagram?: any;
  infographics?: any;
  image_prompts?: string[];
  icon_queries?: Array<{ queries: string[] }>;
  flowchart?: {
    nodes: Array<{
      id: string;
      type: "rectangle" | "diamond" | "circle" | "rounded";
      x: number;
      y: number;
      width: number;
      height: number;
      text: string;
      backgroundColor?: string;
      textColor?: string;
    }>;
    connections: Array<{
      id: string;
      from_node: string;
      to_node: string;
      label?: string;
      style?: "solid" | "dashed" | "dotted";
    }>;
  };
}

export interface Slide {
  id: string | null;
  index: number;
  type: number;
  design_index: number | null;
  images: string[] | null;
  properties: null | any;
  icons: string[] | null;
  graph_id: string | null;
  presentation?: string;
  content: SlideContent;
}
