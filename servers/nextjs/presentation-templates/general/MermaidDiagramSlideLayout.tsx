import React, { useEffect, useRef } from 'react'
import * as z from "zod";

export const layoutId = 'general-mermaid-diagram-slide'
export const layoutName = 'Mermaid Diagram'
export const layoutDescription = 'A clean, general-purpose layout for displaying Mermaid diagrams with title and optional description.'

const mermaidDiagramSlideSchema = z.object({
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
    })
})

export const Schema = mermaidDiagramSlideSchema

export type MermaidDiagramSlideData = z.infer<typeof mermaidDiagramSlideSchema>

interface MermaidDiagramSlideLayoutProps {
    data: Partial<MermaidDiagramSlideData>
}

const MermaidDiagramSlideLayout: React.FC<MermaidDiagramSlideLayoutProps> = ({ data: slideData }) => {
    const { title, description, mermaidCode, theme } = slideData;
    const mermaidRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const loadMermaid = async () => {
            try {
                // Dynamically import mermaid
                const mermaid = (await import('mermaid')).default;

                // Initialize mermaid with the selected theme and general styling
                mermaid.initialize({
                    startOnLoad: true,
                    theme: theme || 'default',
                    themeVariables: {
                        primaryColor: '#6366f1',
                        primaryTextColor: '#1f2937',
                        primaryBorderColor: '#e2e8f0',
                        lineColor: '#64748b',
                        secondaryColor: '#f1f5f9',
                        tertiaryColor: '#ffffff'
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
                    const diagramId = `mermaid-general-${Date.now()}`;

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
            {/* Import Google Fonts */}
            <link
                href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap"
                rel="stylesheet"
            />

            <div
                className="w-full rounded-sm max-w-[1280px] shadow-lg max-h-[720px] aspect-video bg-white relative z-20 mx-auto overflow-hidden"
                style={{
                    fontFamily: 'Poppins, sans-serif'
                }}
            >
                <div className="px-6 sm:px-12 lg:px-20 py-8 sm:py-12 lg:py-16 h-full flex flex-col">
                    {/* Title */}
                    {title && (
                        <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-gray-900 mb-4 lg:mb-6 text-center">
                            {title}
                        </h1>
                    )}

                    {/* Description */}
                    {description && (
                        <p className="text-gray-700 text-base sm:text-lg lg:text-xl leading-relaxed mb-6 lg:mb-8 text-center max-w-4xl mx-auto">
                            {description}
                        </p>
                    )}

                    {/* Mermaid Diagram Container */}
                    <div className="flex-1 flex items-center justify-center">
                        <div
                            ref={mermaidRef}
                            className="w-full h-full flex items-center justify-center min-h-[300px] max-h-[400px] overflow-hidden bg-gray-50 rounded-lg border border-gray-200"
                            style={{
                                maxWidth: '100%',
                                maxHeight: '100%'
                            }}
                        />
                    </div>

                    {/* Fallback content if no mermaid code is provided */}
                    {!mermaidCode && (
                        <div className="flex-1 flex items-center justify-center">
                            <div className="text-center text-gray-500">
                                <p className="text-lg font-semibold">No diagram to display</p>
                                <p className="text-sm mt-2">Please provide Mermaid diagram code</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    )
}

export default MermaidDiagramSlideLayout