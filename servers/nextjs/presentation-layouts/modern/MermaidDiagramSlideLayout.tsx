import React, { useEffect, useRef } from 'react'
import * as z from "zod";

export const layoutId = 'modern-mermaid-diagram-slide'
export const layoutName = 'Modern Mermaid Diagram'
export const layoutDescription = 'A modern, professional layout for displaying Mermaid diagrams with bold styling and contemporary design elements.'

const modernMermaidDiagramSlideSchema = z.object({
    title: z.string().min(3).max(50).default('Process Flow').meta({
        description: "Main title of the slide",
    }),
    description: z.string().min(10).max(200).optional().meta({
        description: "Optional description text to provide context for the diagram",
    }),
    mermaidCode: z.string().min(10).default(`graph LR
    A[Start] --> B{Is it working?}
    B -->|Yes| C[Great!]
    B -->|No| D[Fix it]
    D --> B
    C --> E[End]`).meta({
        description: "Mermaid diagram code. Supports all Mermaid syntax: graph LR/TD/TB, flowchart, sequenceDiagram, classDiagram, etc. Ensure proper syntax and node connections.",
    }),
    theme: z.enum(['default', 'dark', 'forest', 'neutral']).default('default').meta({
        description: "Mermaid theme to use",
    }),
    companyName: z.string().default("presenton").meta({
        description: "Company name displayed in header",
    }),
})

export const Schema = modernMermaidDiagramSlideSchema

export type ModernMermaidDiagramSlideData = z.infer<typeof modernMermaidDiagramSlideSchema>

interface ModernMermaidDiagramSlideLayoutProps {
    data: Partial<ModernMermaidDiagramSlideData>
}

const ModernMermaidDiagramSlideLayout: React.FC<ModernMermaidDiagramSlideLayoutProps> = ({ data: slideData }) => {
    const { title, description, mermaidCode, theme, companyName } = slideData;
    const mermaidRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const loadMermaid = async () => {
            try {
                // Dynamically import mermaid
                const mermaid = (await import('mermaid')).default;

                // Initialize mermaid with modern theme styling
                mermaid.initialize({
                    startOnLoad: true,
                    theme: theme || 'default',
                    themeVariables: {
                        primaryColor: '#1E4CD9',
                        primaryTextColor: '#ffffff',
                        primaryBorderColor: '#1E4CD9',
                        lineColor: '#1E4CD9',
                        secondaryColor: '#E3F2FD',
                        tertiaryColor: '#ffffff',
                        background: '#ffffff',
                        mainBkg: '#E3F2FD',
                        secondBkg: '#1E4CD9'
                    },
                    flowchart: {
                        useMaxWidth: true,
                        htmlLabels: true,
                        curve: 'basis'
                    }
                });

                if (mermaidRef.current && mermaidCode) {
                    // Clear previous content
                    mermaidRef.current.innerHTML = '';

                    // Create a unique ID for this diagram
                    const diagramId = `mermaid-modern-${Date.now()}`;

                    // Render the diagram
                    const { svg } = await mermaid.render(diagramId, mermaidCode);
                    mermaidRef.current.innerHTML = svg;
                }
            } catch (error) {
                console.error('Error loading or rendering mermaid:', error);
                if (mermaidRef.current) {
                    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
                    console.error('Mermaid code that failed:', mermaidCode);
                    
                    mermaidRef.current.innerHTML = `
                        <div class="flex items-center justify-center h-full text-red-500 bg-red-50 rounded-lg border border-red-200">
                            <div class="text-center p-6">
                                <div class="text-2xl mb-2">⚠️</div>
                                <p class="text-lg font-semibold mb-2">Mermaid Diagram Error</p>
                                <p class="text-sm text-gray-600 mb-3">Failed to render diagram: ${errorMessage}</p>
                                <details class="text-xs text-left">
                                    <summary class="cursor-pointer font-medium">Show Diagram Code</summary>
                                    <pre class="mt-2 p-2 bg-gray-100 rounded text-gray-800 overflow-auto">${mermaidCode || 'No code provided'}</pre>
                                </details>
                            </div>
                        </div>
                    `;
                }
            }
        };

        loadMermaid();
    }, [mermaidCode, theme]);

    return (
        <>
            {/* Montserrat Font */}
            <link
                href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap"
                rel="stylesheet"
            />
            
            <div
                className="w-full max-w-[1280px] bg-white aspect-video mx-auto relative overflow-hidden rounded-md"
                style={{
                    fontFamily: "Montserrat, sans-serif",
                    backgroundSize: "cover",
                    backgroundPosition: "center",
                }}
            >
                {/* Top Header */}
                <div className="absolute top-8 left-10 right-10 flex justify-between items-center text-[#1E4CD9] text-sm font-semibold">
                    <p>{companyName}</p>
                    <p>Diagram</p>
                </div>

                {/* Main Content */}
                <div className="absolute inset-0 pt-20 pb-10 px-10 flex flex-col">
                    {/* Title */}
                    {title && (
                        <div className="mb-6">
                            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-[#1E4CD9] leading-tight">
                                {title}
                            </h1>
                            {/* Blue underline */}
                            <span
                                className="block bg-[#1E4CD9] h-[4px] mt-2"
                                style={{
                                    width: "30%",
                                    transition: "width 0.3s",
                                }}
                            />
                        </div>
                    )}

                    {/* Description */}
                    {description && (
                        <p className="text-gray-700 text-lg lg:text-xl leading-relaxed mb-6 max-w-3xl">
                            {description}
                        </p>
                    )}

                    {/* Mermaid Diagram Container */}
                    <div className="flex-1 flex items-center justify-center">
                        <div
                            ref={mermaidRef}
                            className="w-full h-full flex items-center justify-center min-h-[300px] max-h-[400px] overflow-hidden bg-gray-50 rounded-lg border-2 border-[#1E4CD9]/20"
                            style={{
                                maxWidth: '100%',
                                maxHeight: '100%'
                            }}
                        />
                    </div>

                    {/* Fallback content if no mermaid code is provided */}
                    {!mermaidCode && (
                        <div className="flex-1 flex items-center justify-center">
                            <div className="text-center text-[#1E4CD9]">
                                <p className="text-xl font-semibold">No diagram to display</p>
                                <p className="text-sm mt-2">Please provide Mermaid diagram code</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    )
}

export default ModernMermaidDiagramSlideLayout