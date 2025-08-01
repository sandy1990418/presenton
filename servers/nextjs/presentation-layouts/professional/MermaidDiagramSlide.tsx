import React, { useEffect, useRef } from 'react'
import * as z from "zod";
import { ImageSchema } from "../defaultSchemes";

export const layoutId = 'professional-mermaid-diagram-slide'
export const layoutName = 'Professional Mermaid Diagram'
export const layoutDescription = 'A professional, business-focused layout for displaying Mermaid diagrams with sophisticated styling and branding elements.'

const professionalMermaidDiagramSlideSchema = z.object({
    organizationName: z.string()
        .min(2)
        .max(25)
        .default("Your Organization")
        .meta({
            description: "Name of the organization, company, or entity presenting",
        }),
    
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
    
    brandLogo: ImageSchema.default({
        __image_url__: "https://via.placeholder.com/40x40/14B8A6/FFFFFF?text=L",
        __image_prompt__: "Professional organization logo - clean and modern design"
    }).meta({
        description: "Logo or brand mark representing the presenting organization",
    }),
    
    showDecorations: z.boolean()
        .default(true)
        .meta({
            description: "Whether to display decorative visual elements like background shapes",
        }),
})

export const Schema = professionalMermaidDiagramSlideSchema

export type ProfessionalMermaidDiagramSlideData = z.infer<typeof professionalMermaidDiagramSlideSchema>

interface ProfessionalMermaidDiagramSlideLayoutProps {
    data: Partial<ProfessionalMermaidDiagramSlideData>
}

const ProfessionalMermaidDiagramSlideLayout: React.FC<ProfessionalMermaidDiagramSlideLayoutProps> = ({ data: slideData }) => {
    const { organizationName, title, description, mermaidCode, theme, brandLogo, showDecorations } = slideData;
    const mermaidRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const loadMermaid = async () => {
            try {
                // Dynamically import mermaid
                const mermaid = (await import('mermaid')).default;

                // Initialize mermaid with professional theme styling
                mermaid.initialize({
                    startOnLoad: true,
                    theme: theme || 'default',
                    themeVariables: {
                        primaryColor: '#14B8A6',
                        primaryTextColor: '#1f2937',
                        primaryBorderColor: '#14B8A6',
                        lineColor: '#14B8A6',
                        secondaryColor: '#F0FDFA',
                        tertiaryColor: '#ffffff',
                        background: '#ffffff',
                        mainBkg: '#F0FDFA',
                        secondBkg: '#14B8A6'
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
                    const diagramId = `mermaid-professional-${Date.now()}`;

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
        <div className="aspect-video max-w-[1280px] w-full bg-white relative overflow-hidden">
            {/* Header with Logo and Organization Name */}
            <div className="absolute top-0 left-0 right-0 px-16 py-8 flex justify-between items-center z-20">
                {/* Company Logo and Name */}
                <div className="flex items-center space-x-3">
                    {brandLogo?.__image_url__ && (
                        <div className="w-10 h-10">
                            <img
                                src={brandLogo.__image_url__}
                                alt={brandLogo.__image_prompt__}
                                className="w-full h-full object-contain"
                            />
                        </div>
                    )}
                    {organizationName && (
                        <span className="text-2xl font-bold text-gray-900">
                            {organizationName}
                        </span>
                    )}
                </div>

                {/* Diagram indicator */}
                <div className="w-12 h-12 bg-teal-600 rounded-full flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                </div>
            </div>

            {/* Decorative Circles */}
            {showDecorations && (
                <>
                    <div className="absolute top-20 right-16 w-80 h-80 bg-teal-100 rounded-full opacity-40 z-10"></div>
                    <div className="absolute bottom-16 left-16 w-64 h-64 bg-yellow-100 rounded-full opacity-30 z-10"></div>
                </>
            )}

            {/* Main Content */}
            <div className="relative h-full flex flex-col justify-center px-16 pt-24 pb-12">
                {/* Title */}
                {title && (
                    <div className="mb-6 z-20 relative">
                        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 leading-tight">
                            {title}
                        </h1>
                        {/* Teal underline */}
                        <div className="w-24 h-1 bg-teal-600 mt-3"></div>
                    </div>
                )}

                {/* Description */}
                {description && (
                    <p className="text-gray-700 text-lg lg:text-xl leading-relaxed mb-8 max-w-3xl z-20 relative">
                        {description}
                    </p>
                )}

                {/* Mermaid Diagram Container */}
                <div className="flex-1 flex items-center justify-center z-20 relative">
                    <div
                        ref={mermaidRef}
                        className="w-full h-full flex items-center justify-center min-h-[300px] max-h-[400px] overflow-hidden bg-white rounded-lg border-2 border-teal-200 shadow-lg"
                        style={{
                            maxWidth: '100%',
                            maxHeight: '100%'
                        }}
                    />
                </div>

                {/* Fallback content if no mermaid code is provided */}
                {!mermaidCode && (
                    <div className="flex-1 flex items-center justify-center z-20 relative">
                        <div className="text-center text-teal-600">
                            <p className="text-xl font-semibold">No diagram to display</p>
                            <p className="text-sm mt-2">Please provide Mermaid diagram code</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

export default ProfessionalMermaidDiagramSlideLayout