"use client";
import React, { useState } from "react";
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
} from "@dnd-kit/core";
import {
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { OutlineItem } from "./OutlineItem";
import { Button } from "@/components/ui/button";
import { FileText, Edit3, Eye } from "lucide-react";

interface OutlineContentProps {
    outlines: { content: string }[] | null;
    isLoading: boolean;
    isStreaming: boolean;
    onDragEnd: (event: any) => void;
    onAddSlide: () => void;
}

const OutlineContent: React.FC<OutlineContentProps> = ({
    outlines,
    isLoading,
    isStreaming,
    onDragEnd,
    onAddSlide
}) => {
    const [viewMode, setViewMode] = useState<'edit' | 'markdown'>('edit');
    
    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const generateMarkdownPreview = (outlines: { content: string }[]) => {
        if (!outlines || outlines.length === 0) return "";
        
        let markdown = "# Presentation Architecture\n\n";
        markdown += `📊 **Total Slides:** ${outlines.length}\n\n`;
        markdown += "## Slide Structure\n\n";
        
        outlines.forEach((outline, index) => {
            const slideNumber = index + 1;
            const title = `Slide ${slideNumber}`;
            const body = outline.content || "No content";
            
            // Detect if it's a mermaid slide
            const isMermaidSlide = body.toLowerCase().includes("mermaid") || 
                                   body.toLowerCase().includes("diagram") ||
                                   body.toLowerCase().includes("flowchart") ||
                                   body.toLowerCase().includes("graph");
            
            markdown += `### ${slideNumber}. ${title}\n`;
            if (isMermaidSlide) {
                markdown += "🔄 **Type:** Mermaid Diagram\n";
            } else {
                markdown += "📝 **Type:** Content Slide\n";
            }
            
            // Truncate long content for preview
            const truncatedBody = body.length > 100 ? body.substring(0, 100) + "..." : body;
            markdown += `**Content:** ${truncatedBody}\n\n`;
        });
        
        return markdown;
    };

    return (
        <div className="space-y-6 font-instrument_sans">
            {/* Header with view toggle */}
            <div className="flex items-center justify-between">
                <h5 className="text-lg font-medium">
                    Presentation Outline
                </h5>
                <div className="flex items-center gap-2">
                    {isStreaming && (
                        <div className="flex items-center text-sm text-blue-600">
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
                            Generating outlines...
                        </div>
                    )}
                    {outlines && outlines.length > 0 && !isLoading && (
                        <div className="flex bg-gray-100 rounded-lg p-1">
                            <button
                                onClick={() => setViewMode('edit')}
                                className={`flex items-center gap-1 px-3 py-1 rounded-md text-sm transition-colors ${
                                    viewMode === 'edit' 
                                        ? 'bg-white text-blue-600 shadow-sm' 
                                        : 'text-gray-600 hover:text-gray-800'
                                }`}
                            >
                                <Edit3 className="w-4 h-4" />
                                Edit
                            </button>
                            <button
                                onClick={() => setViewMode('markdown')}
                                className={`flex items-center gap-1 px-3 py-1 rounded-md text-sm transition-colors ${
                                    viewMode === 'markdown' 
                                        ? 'bg-white text-blue-600 shadow-sm' 
                                        : 'text-gray-600 hover:text-gray-800'
                                }`}
                            >
                                <Eye className="w-4 h-4" />
                                Preview
                            </button>
                        </div>
                    )}
                </div>
            </div>
            {/* Skeleton loading state */}
            {isLoading && (
                <div className="space-y-4">
                    {[...Array(6)].map((_, index) => (
                        <div key={index} className="animate-pulse">
                            <div className="flex items-start space-x-3 p-4 border rounded-lg bg-white">
                                <div className="w-6 h-6 bg-gray-200 rounded-full flex-shrink-0"></div>
                                <div className="flex-1 space-y-2">
                                    <div className="h-5 bg-gray-200 rounded w-3/4"></div>
                                    <div className="space-y-1">
                                        <div className="h-4 bg-gray-100 rounded w-full"></div>
                                        <div className="h-4 bg-gray-100 rounded w-5/6"></div>
                                        <div className="h-4 bg-gray-100 rounded w-4/6"></div>
                                    </div>
                                </div>
                                <div className="w-5 h-5 bg-gray-200 rounded flex-shrink-0"></div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Outlines content */}
            {outlines && outlines.length > 0 && (
                <div>
                    <DndContext
                        sensors={sensors}
                        collisionDetection={closestCenter}
                        onDragEnd={onDragEnd}
                    >
                        {isStreaming ? (

                           outlines.map((item, index) => (
                            <OutlineItem
                                key={`slide-${index}`}
                                index={index + 1}
                                slideOutline={item}
                                isStreaming={isStreaming}
                            />
                        ))
                        ) :
                            <SortableContext
                            items={outlines?.map((item, index) => ({ id: `slide-${index}` })) || []}
                            strategy={verticalListSortingStrategy}
                        >
                            {outlines?.map((item, index) => (
                                <OutlineItem
                                    key={`slide-${index}`}
                                    index={index + 1}
                                    slideOutline={item}
                                    isStreaming={isStreaming}
                                />
                            ))}
                        </SortableContext>}
                    </DndContext>

                    {viewMode === 'edit' ? (
                        <>
                            <Button
                                variant="outline"
                                onClick={onAddSlide}
                                disabled={isLoading || isStreaming}
                                className="w-full my-4 text-blue-600 border-blue-200"
                            >
                                + Add Slide
                            </Button>
                        </>
                    ) : (
                        /* Markdown Preview Mode */
                        <div className="bg-white rounded-lg border p-6">
                            <div className="prose prose-sm max-w-none">
                                <div 
                                    className="markdown-content"
                                    dangerouslySetInnerHTML={{ 
                                        __html: generateMarkdownPreview(outlines || [])
                                            .replace(/\n/g, '<br/>')
                                            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                            .replace(/^### (.*?)$/gm, '<h3 class="text-lg font-semibold text-gray-800 mt-4 mb-2">$1</h3>')
                                            .replace(/^## (.*?)$/gm, '<h2 class="text-xl font-bold text-gray-900 mt-6 mb-3">$1</h2>')
                                            .replace(/^# (.*?)$/gm, '<h1 class="text-2xl font-bold text-blue-600 mb-4">$1</h1>')
                                    }}
                                />
                            </div>
                            <div className="mt-6 pt-4 border-t">
                                <Button
                                    variant="outline"
                                    onClick={() => setViewMode('edit')}
                                    className="text-blue-600 border-blue-200"
                                >
                                    <Edit3 className="w-4 h-4 mr-2" />
                                    Switch to Edit Mode
                                </Button>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Empty state */}
            {!isStreaming && !isLoading && outlines && outlines.length === 0 && (
                <div className="text-center py-12 bg-white rounded-lg border-2 border-dashed border-gray-200">
                    <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600 mb-4">No outlines available</p>
                    <Button
                        variant="outline"
                        onClick={onAddSlide}
                        className="text-blue-600 border-blue-200"
                    >
                        + Add First Slide
                    </Button>
                </div>
            )}
        </div>
    );
};

export default OutlineContent; 