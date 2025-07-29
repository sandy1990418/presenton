"use client";
import React, { useState, useRef, useCallback, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { updateSlideFlowchart } from "@/store/slices/presentationGeneration";
import { FlowchartData, FlowchartNode, FlowchartConnection } from "./slide_layouts/Type10Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  Plus, 
  Square, 
  Circle, 
  Diamond, 
  RectangleHorizontal, 
  Trash2,
  Move,
  Edit3,
  Save,
  X
} from "lucide-react";
import { cn } from "@/lib/utils";

interface FlowchartEditorProps {
  slideIndex: number;
  flowchartData: FlowchartData;
}

type Tool = "select" | "rectangle" | "diamond" | "circle" | "rounded" | "connection";

const FlowchartEditor: React.FC<FlowchartEditorProps> = ({
  slideIndex,
  flowchartData,
}) => {
  const dispatch = useDispatch();
  const { currentColors } = useSelector((state: RootState) => state.theme);
  const [currentTool, setCurrentTool] = useState<Tool>("select");
  const [nodes, setNodes] = useState<FlowchartNode[]>(flowchartData.nodes);
  const [connections, setConnections] = useState<FlowchartConnection[]>(flowchartData.connections);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [editingNode, setEditingNode] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ nodeId: string; offset: { x: number; y: number } } | null>(null);
  const [connecting, setConnecting] = useState<{ from: string } | null>(null);
  const [editText, setEditText] = useState("");
  const canvasRef = useRef<HTMLDivElement>(null);

  // Save changes to Redux store
  useEffect(() => {
    const flowchartData = { nodes, connections };
    dispatch(updateSlideFlowchart({ index: slideIndex, flowchart: flowchartData }));
  }, [nodes, connections, slideIndex, dispatch]);

  // Handle canvas click for adding new nodes
  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    if (currentTool === "select") return;
    
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (currentTool !== "connection") {
      const newNode: FlowchartNode = {
        id: `node-${Date.now()}`,
        type: currentTool as FlowchartNode["type"],
        x: x - 60,
        y: y - 30,
        width: 120,
        height: 60,
        text: "New Node",
        backgroundColor: currentColors.iconBg,
        textColor: "#ffffff",
      };

      setNodes(prev => [...prev, newNode]);
      setCurrentTool("select");
    }
  }, [currentTool, currentColors.iconBg]);

  // Handle node click
  const handleNodeClick = useCallback((nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (currentTool === "connection") {
      if (connecting) {
        // Complete connection
        if (connecting.from !== nodeId) {
          const newConnection: FlowchartConnection = {
            id: `conn-${Date.now()}`,
            from: connecting.from,
            to: nodeId,
          };
          setConnections(prev => [...prev, newConnection]);
        }
        setConnecting(null);
        setCurrentTool("select");
      } else {
        // Start connection
        setConnecting({ from: nodeId });
      }
    } else {
      setSelectedNode(nodeId);
    }
  }, [currentTool, connecting]);

  // Handle node double-click for editing
  const handleNodeDoubleClick = useCallback((nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (node) {
      setEditingNode(nodeId);
      setEditText(node.text);
    }
  }, [nodes]);

  // Handle node text save
  const handleSaveNodeText = useCallback(() => {
    if (editingNode) {
      setNodes(prev => prev.map(node => 
        node.id === editingNode 
          ? { ...node, text: editText }
          : node
      ));
      setEditingNode(null);
      setEditText("");
    }
  }, [editingNode, editText]);

  // Handle mouse down for dragging
  const handleMouseDown = useCallback((nodeId: string, e: React.MouseEvent) => {
    if (currentTool !== "select") return;
    
    e.preventDefault();
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    setDragging({
      nodeId,
      offset: {
        x: e.clientX - rect.left - node.x,
        y: e.clientY - rect.top - node.y,
      },
    });
  }, [currentTool, nodes]);

  // Handle mouse move for dragging
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left - dragging.offset.x;
    const y = e.clientY - rect.top - dragging.offset.y;

    setNodes(prev => prev.map(node => 
      node.id === dragging.nodeId 
        ? { ...node, x, y }
        : node
    ));
  }, [dragging]);

  // Handle mouse up
  const handleMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  // Delete selected node
  const deleteSelectedNode = useCallback(() => {
    if (selectedNode) {
      setNodes(prev => prev.filter(node => node.id !== selectedNode));
      setConnections(prev => prev.filter(conn => 
        conn.from !== selectedNode && conn.to !== selectedNode
      ));
      setSelectedNode(null);
    }
  }, [selectedNode]);

  // Render node based on type
  const renderNode = useCallback((node: FlowchartNode) => {
    const isSelected = selectedNode === node.id;
    const isEditing = editingNode === node.id;
    
    const nodeStyle = {
      left: node.x,
      top: node.y,
      width: node.width,
      height: node.height,
      backgroundColor: node.backgroundColor,
      color: node.textColor,
    };

    const commonClasses = cn(
      "absolute cursor-pointer border-2 flex items-center justify-center text-sm font-medium transition-all duration-200",
      isSelected ? "border-blue-500 shadow-lg" : "border-transparent",
      dragging?.nodeId === node.id ? "opacity-50" : ""
    );

    const content = isEditing ? (
      <div className="flex flex-col gap-1 p-1">
        <Input
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          className="text-xs h-6"
          autoFocus
        />
        <div className="flex gap-1">
          <Button size="sm" variant="outline" onClick={handleSaveNodeText} className="h-5 w-5 p-0">
            <Save className="h-3 w-3" />
          </Button>
          <Button size="sm" variant="outline" onClick={() => setEditingNode(null)} className="h-5 w-5 p-0">
            <X className="h-3 w-3" />
          </Button>
        </div>
      </div>
    ) : (
      <span className="px-2 text-center break-words">{node.text}</span>
    );

    switch (node.type) {
      case "rectangle":
        return (
          <div
            key={node.id}
            className={cn(commonClasses, "rounded-sm")}
            style={nodeStyle}
            onClick={(e) => handleNodeClick(node.id, e)}
            onDoubleClick={() => handleNodeDoubleClick(node.id)}
            onMouseDown={(e) => handleMouseDown(node.id, e)}
            data-slide-element
            data-slide-index={slideIndex}
            data-element-type="flowchart-node"
            data-element-id={`slide-${slideIndex}-node-${node.id}`}
          >
            {content}
          </div>
        );
      
      case "diamond":
        return (
          <div
            key={node.id}
            className={cn(commonClasses, "transform rotate-45")}
            style={nodeStyle}
            onClick={(e) => handleNodeClick(node.id, e)}
            onDoubleClick={() => handleNodeDoubleClick(node.id)}
            onMouseDown={(e) => handleMouseDown(node.id, e)}
            data-slide-element
            data-slide-index={slideIndex}
            data-element-type="flowchart-node"
            data-element-id={`slide-${slideIndex}-node-${node.id}`}
          >
            <div className="transform -rotate-45 text-xs">
              {content}
            </div>
          </div>
        );
      
      case "circle":
        return (
          <div
            key={node.id}
            className={cn(commonClasses, "rounded-full")}
            style={nodeStyle}
            onClick={(e) => handleNodeClick(node.id, e)}
            onDoubleClick={() => handleNodeDoubleClick(node.id)}
            onMouseDown={(e) => handleMouseDown(node.id, e)}
            data-slide-element
            data-slide-index={slideIndex}
            data-element-type="flowchart-node"
            data-element-id={`slide-${slideIndex}-node-${node.id}`}
          >
            {content}
          </div>
        );
      
      case "rounded":
        return (
          <div
            key={node.id}
            className={cn(commonClasses, "rounded-full")}
            style={nodeStyle}
            onClick={(e) => handleNodeClick(node.id, e)}
            onDoubleClick={() => handleNodeDoubleClick(node.id)}
            onMouseDown={(e) => handleMouseDown(node.id, e)}
            data-slide-element
            data-slide-index={slideIndex}
            data-element-type="flowchart-node"
            data-element-id={`slide-${slideIndex}-node-${node.id}`}
          >
            {content}
          </div>
        );
      
      default:
        return null;
    }
  }, [
    selectedNode,
    editingNode,
    editText,
    dragging,
    slideIndex,
    handleNodeClick,
    handleNodeDoubleClick,
    handleMouseDown,
    handleSaveNodeText,
  ]);

  // Render connections
  const renderConnections = useCallback(() => {
    return connections.map((conn) => {
      const fromNode = nodes.find(n => n.id === conn.from);
      const toNode = nodes.find(n => n.id === conn.to);
      
      if (!fromNode || !toNode) return null;

      const fromCenter = {
        x: fromNode.x + fromNode.width / 2,
        y: fromNode.y + fromNode.height / 2,
      };
      
      const toCenter = {
        x: toNode.x + toNode.width / 2,
        y: toNode.y + toNode.height / 2,
      };

      return (
        <g key={conn.id}>
          <line
            x1={fromCenter.x}
            y1={fromCenter.y}
            x2={toCenter.x}
            y2={toCenter.y}
            stroke={currentColors.slideTitle}
            strokeWidth="2"
            markerEnd="url(#arrowhead)"
          />
          {conn.label && (
            <text
              x={(fromCenter.x + toCenter.x) / 2}
              y={(fromCenter.y + toCenter.y) / 2}
              fill={currentColors.slideTitle}
              fontSize="12"
              textAnchor="middle"
            >
              {conn.label}
            </text>
          )}
        </g>
      );
    });
  }, [connections, nodes, currentColors.slideTitle]);

  return (
    <div className="w-full h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-t-lg border-b">
        <Button
          variant={currentTool === "select" ? "default" : "outline"}
          size="sm"
          onClick={() => setCurrentTool("select")}
          className="h-8"
        >
          <Move className="h-4 w-4" />
        </Button>
        
        <div className="h-4 w-px bg-gray-300" />
        
        <Button
          variant={currentTool === "rectangle" ? "default" : "outline"}
          size="sm"
          onClick={() => setCurrentTool("rectangle")}
          className="h-8"
        >
          <Square className="h-4 w-4" />
        </Button>
        
        <Button
          variant={currentTool === "diamond" ? "default" : "outline"}
          size="sm"
          onClick={() => setCurrentTool("diamond")}
          className="h-8"
        >
          <Diamond className="h-4 w-4" />
        </Button>
        
        <Button
          variant={currentTool === "circle" ? "default" : "outline"}
          size="sm"
          onClick={() => setCurrentTool("circle")}
          className="h-8"
        >
          <Circle className="h-4 w-4" />
        </Button>
        
        <Button
          variant={currentTool === "rounded" ? "default" : "outline"}
          size="sm"
          onClick={() => setCurrentTool("rounded")}
          className="h-8"
        >
          <RectangleHorizontal className="h-4 w-4" />
        </Button>
        
        <div className="h-4 w-px bg-gray-300" />
        
        <Button
          variant={currentTool === "connection" ? "default" : "outline"}
          size="sm"
          onClick={() => setCurrentTool("connection")}
          className="h-8"
        >
          <Plus className="h-4 w-4" />
        </Button>
        
        <div className="h-4 w-px bg-gray-300" />
        
        <Button
          variant="outline"
          size="sm"
          onClick={deleteSelectedNode}
          disabled={!selectedNode}
          className="h-8"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Canvas */}
      <div
        ref={canvasRef}
        className="relative flex-1 bg-white border rounded-b-lg overflow-hidden"
        onClick={handleCanvasClick}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ minHeight: "400px" }}
      >
        {/* SVG for connections */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon
                points="0 0, 10 3.5, 0 7"
                fill={currentColors.slideTitle}
              />
            </marker>
          </defs>
          {renderConnections()}
        </svg>

        {/* Nodes */}
        {nodes.map(renderNode)}

        {/* Connection preview */}
        {connecting && (
          <div className="absolute top-2 left-2 bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">
            Click target node to create connection
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className="text-xs text-gray-600 p-2 border-t bg-gray-50">
        <p>
          <strong>Instructions:</strong> Select tools from toolbar, click canvas to add nodes, 
          double-click nodes to edit text, drag to move, use connection tool to link nodes.
        </p>
      </div>
    </div>
  );
};

export default FlowchartEditor;