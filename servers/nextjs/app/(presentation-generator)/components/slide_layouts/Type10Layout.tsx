import React from "react";
import TiptapText from "../TiptapText";

export interface FlowchartNode {
  id: string;
  type: "rectangle" | "diamond" | "circle" | "rounded";
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  backgroundColor?: string;
  textColor?: string;
}

export interface FlowchartConnection {
  id: string;
  from: string;
  to: string;
  label?: string;
  style?: "solid" | "dashed" | "dotted";
}

export interface FlowchartData {
  nodes: FlowchartNode[];
  connections: FlowchartConnection[];
}

interface Type10LayoutProps {
  title: string;
  slideId: string | null;
  slideIndex: number;
  flowchartData?: FlowchartData;
  body?: string;
}

const Type10Layout = ({
  title,
  slideId,
  slideIndex,
  flowchartData,
  body,
}: Type10LayoutProps) => {
  // Default colors for flowchart elements
  const currentColors = {
    iconBg: "#3b82f6",
    slideTitle: "#374151",
    slideDescription: "#6b7280"
  };

  // Default flowchart data if none provided
  const defaultFlowchartData: FlowchartData = {
    nodes: [
      {
        id: "start",
        type: "circle",
        x: 200,
        y: 50,
        width: 100,
        height: 60,
        text: "Start",
        backgroundColor: currentColors.iconBg,
        textColor: "#ffffff",
      },
      {
        id: "process1",
        type: "rectangle",
        x: 200,
        y: 150,
        width: 140,
        height: 60,
        text: "Process Step",
        backgroundColor: currentColors.slideDescription,
        textColor: "#ffffff",
      },
      {
        id: "decision",
        type: "diamond",
        x: 200,
        y: 250,
        width: 120,
        height: 80,
        text: "Decision?",
        backgroundColor: currentColors.slideTitle,
        textColor: "#ffffff",
      },
      {
        id: "end",
        type: "circle",
        x: 200,
        y: 370,
        width: 100,
        height: 60,
        text: "End",
        backgroundColor: currentColors.iconBg,
        textColor: "#ffffff",
      },
    ],
    connections: [
      { id: "conn1", from: "start", to: "process1" },
      { id: "conn2", from: "process1", to: "decision" },
      { id: "conn3", from: "decision", to: "end", label: "Yes" },
    ],
  };

  const currentFlowchartData = flowchartData || defaultFlowchartData;

  // Function to get SVG path for connections
  const getConnectionPath = (
    fromNode: FlowchartNode,
    toNode: FlowchartNode
  ): string => {
    const fromX = fromNode.x + fromNode.width / 2;
    const fromY = fromNode.y + fromNode.height;
    const toX = toNode.x + toNode.width / 2;
    const toY = toNode.y;

    return `M ${fromX} ${fromY} L ${toX} ${toY}`;
  };

  // Function to render different node shapes
  const renderNode = (node: FlowchartNode) => {
    const { x, y, width, height, type, text, backgroundColor, textColor } = node;

    switch (type) {
      case "diamond":
        return (
          <g key={node.id}>
            <polygon
              points={`${x + width / 2},${y} ${x + width},${y + height / 2} ${
                x + width / 2
              },${y + height} ${x},${y + height / 2}`}
              fill={backgroundColor}
              stroke="#333"
              strokeWidth="2"
            />
            <text
              x={x + width / 2}
              y={y + height / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fill={textColor}
              fontSize="12"
              fontWeight="500"
            >
              {text}
            </text>
          </g>
        );
      case "circle":
        return (
          <g key={node.id}>
            <ellipse
              cx={x + width / 2}
              cy={y + height / 2}
              rx={width / 2}
              ry={height / 2}
              fill={backgroundColor}
              stroke="#333"
              strokeWidth="2"
            />
            <text
              x={x + width / 2}
              y={y + height / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fill={textColor}
              fontSize="12"
              fontWeight="500"
            >
              {text}
            </text>
          </g>
        );
      case "rounded":
        return (
          <g key={node.id}>
            <rect
              x={x}
              y={y}
              width={width}
              height={height}
              rx="15"
              ry="15"
              fill={backgroundColor}
              stroke="#333"
              strokeWidth="2"
            />
            <text
              x={x + width / 2}
              y={y + height / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fill={textColor}
              fontSize="12"
              fontWeight="500"
            >
              {text}
            </text>
          </g>
        );
      default: // rectangle
        return (
          <g key={node.id}>
            <rect
              x={x}
              y={y}
              width={width}
              height={height}
              fill={backgroundColor}
              stroke="#333"
              strokeWidth="2"
            />
            <text
              x={x + width / 2}
              y={y + height / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fill={textColor}
              fontSize="12"
              fontWeight="500"
            >
              {text}
            </text>
          </g>
        );
    }
  };

  return (
    <div
      className="slide-container rounded-sm w-full max-w-[1280px] shadow-lg px-3 sm:px-12 lg:px-20 py-[10px] sm:py-[40px] lg:py-[86px] flex flex-col items-center justify-center max-h-[720px] aspect-video bg-white relative z-20 mx-auto"
      data-slide-element
      data-slide-index={slideIndex}
      data-slide-id={slideId}
      data-slide-type="10"
      data-element-type="slide-container"
      data-element-id={`slide-${slideIndex}-container`}
      style={{
        fontFamily: "Inter, sans-serif",
      }}
    >
      {/* Title */}
      <div className="w-full text-center mb-6">
        <TiptapText
          content={title}
          className="text-2xl font-bold text-center"
          placeholder="Enter slide title..."
        />
      </div>

      {/* Body Text (if provided) */}
      {body && (
        <div className="w-full text-center mb-4">
          <TiptapText
            content={body}
            className="text-base text-center"
            placeholder="Enter body text..."
          />
        </div>
      )}

      {/* Flowchart SVG */}
      <div className="flex-1 w-full flex items-center justify-center">
        <svg
          width="100%"
          height="400"
          viewBox="0 0 600 450"
          className="border border-gray-200 rounded-lg bg-gray-50"
        >
          {/* Render connections first (so they appear behind nodes) */}
          {currentFlowchartData.connections.map((connection) => {
            const fromNode = currentFlowchartData.nodes.find(
              (node) => node.id === connection.from
            );
            const toNode = currentFlowchartData.nodes.find(
              (node) => node.id === connection.to
            );

            if (!fromNode || !toNode) return null;

            const path = getConnectionPath(fromNode, toNode);
            const midX = (fromNode.x + fromNode.width / 2 + toNode.x + toNode.width / 2) / 2;
            const midY = (fromNode.y + fromNode.height + toNode.y) / 2;

            return (
              <g key={connection.id}>
                <path
                  d={path}
                  stroke="#333"
                  strokeWidth="2"
                  fill="none"
                  markerEnd="url(#arrowhead)"
                  strokeDasharray={connection.style === "dashed" ? "5,5" : "0"}
                />
                {connection.label && (
                  <text
                    x={midX}
                    y={midY}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="#333"
                    fontSize="10"
                    fontWeight="500"
                    className="bg-white"
                  >
                    {connection.label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Arrow marker definition */}
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#333" />
            </marker>
          </defs>

          {/* Render nodes */}
          {currentFlowchartData.nodes.map(renderNode)}
        </svg>
      </div>

    </div>
  );
};

export default Type10Layout;