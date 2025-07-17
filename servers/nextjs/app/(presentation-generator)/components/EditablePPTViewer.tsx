"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PlusCircle, Save, Eye, Code, Edit3, Trash2, BarChart3, PieChart } from "lucide-react";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

interface EditablePPTViewerProps {
  initialContent?: {
    title: string;
    slides: SlideContent[];
  };
  onSave?: (content: any) => void;
  className?: string;
}

interface SlideContent {
  id: string;
  type: "title" | "content" | "chart" | "text";
  title: string;
  content: string;
  htmlContent?: string;
  chartData?: any;
}

const EditablePPTViewer: React.FC<EditablePPTViewerProps> = ({
  initialContent,
  onSave,
  className = "",
}) => {
  const [activeTab, setActiveTab] = useState("preview");
  const [presentation, setPresentation] = useState({
    title: initialContent?.title || "評估 - 語音對話",
    slides: initialContent?.slides || [
      {
        id: "1",
        type: "content" as const,
        title: "語音對話主觀評估",
        content: `Kimi-Audio 在語音對話任務上進行了全面的主觀評估，評估維度包括語速控制、口音控制、情感控制、同理心和風格控制。`,
        chartData: {
          radarData: [
            { subject: '語速控制', 'Kimi-Audio': 4.30, 'GPT-4o': 3.80, 'GLM-4-Voice': 3.65 },
            { subject: '口音控制', 'Kimi-Audio': 3.45, 'GPT-4o': 3.20, 'GLM-4-Voice': 3.10 },
            { subject: '情感控制', 'Kimi-Audio': 4.27, 'GPT-4o': 3.90, 'GLM-4-Voice': 3.75 },
            { subject: '同理心', 'Kimi-Audio': 3.39, 'GPT-4o': 3.60, 'GLM-4-Voice': 3.25 },
            { subject: '風格控制', 'Kimi-Audio': 4.09, 'GPT-4o': 3.85, 'GLM-4-Voice': 3.70 },
          ],
          barData: [
            { name: '語速控制', value: 4.30 },
            { name: '口音控制', value: 3.45 },
            { name: '情感控制', value: 4.27 },
            { name: '同理心', value: 3.39 },
            { name: '風格控制', value: 4.09 },
          ]
        },
        htmlContent: `
          <div class="slide-content">
            <h2>🧠 語音對話主觀評估</h2>
            <p>Kimi-Audio 在語音對話任務上進行了全面的主觀評估，評估維度包括語速控制、口音控制、情感控制、同理心和風格控制。</p>
            
            <div class="chart-section">
              <h3>📊 評估結果</h3>
              <p>除了 GPT-4o 外，Kimi-Audio 在情感控制、同理心和語速控制方面取得了<span class="highlight">最高分數</span>，總體平均分 3.90，優於 Step-Audio-chat (3.33)、GPT-4o-mini (3.45) 和 GLM-4-Voice (3.65)。</p>
              
              <div class="metrics">
                <div class="metric-item">
                  <span class="metric-label">語速控制</span>
                  <div class="metric-bar">
                    <div class="metric-fill" style="width: 86%"></div>
                  </div>
                  <span class="metric-value">4.30</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">口音控制</span>
                  <div class="metric-bar">
                    <div class="metric-fill" style="width: 69%"></div>
                  </div>
                  <span class="metric-value">3.45</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">情感控制</span>
                  <div class="metric-bar">
                    <div class="metric-fill" style="width: 85%"></div>
                  </div>
                  <span class="metric-value">4.27</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">同理心</span>
                  <div class="metric-bar">
                    <div class="metric-fill" style="width: 68%"></div>
                  </div>
                  <span class="metric-value">3.39</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">風格控制</span>
                  <div class="metric-bar">
                    <div class="metric-fill" style="width: 82%"></div>
                  </div>
                  <span class="metric-value">4.09</span>
                </div>
              </div>
              
              <div class="radar-chart">
                <svg width="400" height="300" viewBox="0 0 400 300">
                  <polygon points="200,50 320,120 290,220 110,220 80,120" fill="rgba(255,165,0,0.2)" stroke="rgba(255,165,0,0.8)" stroke-width="2"/>
                  <polygon points="200,80 290,130 270,190 130,190 110,130" fill="rgba(128,128,128,0.2)" stroke="rgba(128,128,128,0.8)" stroke-width="2"/>
                  <polygon points="200,90 280,140 260,180 140,180 120,140" fill="rgba(0,128,0,0.2)" stroke="rgba(0,128,0,0.8)" stroke-width="2"/>
                  
                  <text x="200" y="40" text-anchor="middle" class="chart-label">語速控制</text>
                  <text x="330" y="125" text-anchor="middle" class="chart-label">口音控制</text>
                  <text x="300" y="235" text-anchor="middle" class="chart-label">情感控制</text>
                  <text x="100" y="235" text-anchor="middle" class="chart-label">同理心</text>
                  <text x="70" y="125" text-anchor="middle" class="chart-label">風格控制</text>
                </svg>
                
                <div class="chart-legend">
                  <div class="legend-item">
                    <div class="legend-color" style="background-color: rgba(255,165,0,0.8)"></div>
                    <span>Kimi-Audio</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color" style="background-color: rgba(128,128,128,0.8)"></div>
                    <span>GPT-4o</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color" style="background-color: rgba(0,128,0,0.8)"></div>
                    <span>GLM-4-Voice</span>
                  </div>
                </div>
              </div>
              
              <p class="note">* 評分標準：1-5分，分數越高越好</p>
            </div>
          </div>
        `,
      },
    ],
  });

  const [editingSlide, setEditingSlide] = useState<string | null>(null);
  const [chartType, setChartType] = useState<'radar' | 'bar'>('radar');

  const renderChart = (slide: SlideContent) => {
    if (!slide.chartData) return null;

    if (chartType === 'radar' && slide.chartData.radarData) {
      return (
        <div className="w-full h-80">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={slide.chartData.radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="subject" />
              <PolarRadiusAxis angle={90} domain={[0, 5]} />
              <Radar name="Kimi-Audio" dataKey="Kimi-Audio" stroke="#ff6b35" fill="#ff6b35" fillOpacity={0.3} />
              <Radar name="GPT-4o" dataKey="GPT-4o" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} />
              <Radar name="GLM-4-Voice" dataKey="GLM-4-Voice" stroke="#82ca9d" fill="#82ca9d" fillOpacity={0.3} />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      );
    } else if (chartType === 'bar' && slide.chartData.barData) {
      return (
        <div className="w-full h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={slide.chartData.barData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#ff6b35" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }
    return null;
  };

  const handleSave = () => {
    if (onSave) {
      onSave(presentation);
    }
  };

  const addNewSlide = () => {
    const newSlide: SlideContent = {
      id: Date.now().toString(),
      type: "content",
      title: "新投影片",
      content: "在此輸入內容...",
      htmlContent: "<div class='slide-content'><h2>新投影片</h2><p>在此輸入內容...</p></div>",
    };
    setPresentation((prev) => ({
      ...prev,
      slides: [...prev.slides, newSlide],
    }));
  };

  const deleteSlide = (slideId: string) => {
    setPresentation((prev) => ({
      ...prev,
      slides: prev.slides.filter((slide) => slide.id !== slideId),
    }));
  };

  const updateSlide = (slideId: string, updates: Partial<SlideContent>) => {
    setPresentation((prev) => ({
      ...prev,
      slides: prev.slides.map((slide) =>
        slide.id === slideId ? { ...slide, ...updates } : slide
      ),
    }));
  };

  const generateHTMLFromContent = (slide: SlideContent) => {
    return `
      <div class="slide-content">
        <h2>${slide.title}</h2>
        <div class="content">
          ${slide.content.split('\n').map(line => `<p>${line}</p>`).join('')}
        </div>
      </div>
    `;
  };

  return (
    <div className={`w-full max-w-6xl mx-auto ${className}`}>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-2xl">
            <Input
              value={presentation.title}
              onChange={(e) =>
                setPresentation((prev) => ({ ...prev, title: e.target.value }))
              }
              className="text-2xl font-bold border-none p-0 focus:ring-0"
            />
          </CardTitle>
          <div className="flex gap-2">
            <Button onClick={addNewSlide} size="sm" variant="outline">
              <PlusCircle className="w-4 h-4 mr-2" />
              新增投影片
            </Button>
            <Button onClick={handleSave} size="sm">
              <Save className="w-4 h-4 mr-2" />
              儲存
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="preview" className="flex items-center gap-2">
                <Eye className="w-4 h-4" />
                預覽
              </TabsTrigger>
              <TabsTrigger value="code" className="flex items-center gap-2">
                <Code className="w-4 h-4" />
                程式碼
              </TabsTrigger>
            </TabsList>

            <TabsContent value="preview" className="mt-6">
              <div className="space-y-6">
                {presentation.slides.map((slide, index) => (
                  <Card key={slide.id} className="relative">
                    <div className="absolute top-2 right-2 flex gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setEditingSlide(slide.id)}
                      >
                        <Edit3 className="w-4 h-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => deleteSlide(slide.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-500">
                          投影片 {index + 1} / {presentation.slides.length}
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {editingSlide === slide.id ? (
                        <div className="space-y-4">
                          <div>
                            <Label htmlFor={`title-${slide.id}`}>標題</Label>
                            <Input
                              id={`title-${slide.id}`}
                              value={slide.title}
                              onChange={(e) =>
                                updateSlide(slide.id, { title: e.target.value })
                              }
                            />
                          </div>
                          <div>
                            <Label htmlFor={`content-${slide.id}`}>內容</Label>
                            <Textarea
                              id={`content-${slide.id}`}
                              value={slide.content}
                              onChange={(e) =>
                                updateSlide(slide.id, { content: e.target.value })
                              }
                              rows={8}
                            />
                          </div>
                          <div className="flex gap-2">
                            <Button
                              onClick={() => {
                                updateSlide(slide.id, {
                                  htmlContent: generateHTMLFromContent(slide),
                                });
                                setEditingSlide(null);
                              }}
                              size="sm"
                            >
                              確定
                            </Button>
                            <Button
                              onClick={() => setEditingSlide(null)}
                              variant="outline"
                              size="sm"
                            >
                              取消
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="slide-preview">
                          <div className="slide-content-wrapper">
                            <h2 className="text-2xl font-bold mb-4">{slide.title}</h2>
                            <p className="text-gray-700 mb-6">{slide.content}</p>
                            
                            {slide.chartData && (
                              <div className="chart-section">
                                <div className="flex items-center justify-between mb-4">
                                  <h3 className="text-lg font-semibold">📊 評估結果</h3>
                                  <div className="flex gap-2">
                                    <Button
                                      size="sm"
                                      variant={chartType === 'radar' ? 'default' : 'outline'}
                                      onClick={() => setChartType('radar')}
                                    >
                                      <PieChart className="w-4 h-4 mr-2" />
                                      雷達圖
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant={chartType === 'bar' ? 'default' : 'outline'}
                                      onClick={() => setChartType('bar')}
                                    >
                                      <BarChart3 className="w-4 h-4 mr-2" />
                                      長條圖
                                    </Button>
                                  </div>
                                </div>
                                {renderChart(slide)}
                                <p className="text-sm text-gray-500 mt-4">* 評分標準：1-5分，分數越高越好</p>
                              </div>
                            )}
                            
                            {!slide.chartData && (
                              <div
                                dangerouslySetInnerHTML={{
                                  __html: slide.htmlContent || generateHTMLFromContent(slide),
                                }}
                              />
                            )}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="code" className="mt-6">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="html-code">HTML 程式碼</Label>
                  <Textarea
                    id="html-code"
                    value={`<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${presentation.title}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .slide-content { background: white; padding: 30px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .slide-content h2 { color: #333; margin-bottom: 20px; }
        .highlight { background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px; }
        .metrics { margin: 20px 0; }
        .metric-item { display: flex; align-items: center; margin: 10px 0; }
        .metric-label { width: 120px; font-weight: bold; }
        .metric-bar { flex: 1; height: 20px; background-color: #e0e0e0; border-radius: 10px; margin: 0 10px; position: relative; }
        .metric-fill { height: 100%; background-color: #ff9800; border-radius: 10px; }
        .metric-value { font-weight: bold; color: #333; }
        .radar-chart { text-align: center; margin: 20px 0; }
        .chart-label { font-size: 12px; fill: #333; }
        .chart-legend { display: flex; justify-content: center; gap: 20px; margin-top: 10px; }
        .legend-item { display: flex; align-items: center; gap: 5px; }
        .legend-color { width: 20px; height: 20px; border-radius: 3px; }
        .note { font-size: 12px; color: #666; margin-top: 20px; }
    </style>
</head>
<body>
${presentation.slides.map(slide => slide.htmlContent || generateHTMLFromContent(slide)).join('\n')}
</body>
</html>`}
                    rows={20}
                    readOnly
                    className="font-mono text-sm"
                  />
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <style jsx>{`
        .slide-content-wrapper {
          min-height: 400px;
          padding: 20px;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          background: white;
        }
        
        .slide-content h2 {
          color: #333;
          margin-bottom: 20px;
          font-size: 1.5rem;
        }
        
        .highlight {
          background-color: #ffeb3b;
          padding: 2px 4px;
          border-radius: 3px;
        }
        
        .metrics {
          margin: 20px 0;
        }
        
        .metric-item {
          display: flex;
          align-items: center;
          margin: 10px 0;
        }
        
        .metric-label {
          width: 120px;
          font-weight: bold;
        }
        
        .metric-bar {
          flex: 1;
          height: 20px;
          background-color: #e0e0e0;
          border-radius: 10px;
          margin: 0 10px;
          position: relative;
        }
        
        .metric-fill {
          height: 100%;
          background-color: #ff9800;
          border-radius: 10px;
        }
        
        .metric-value {
          font-weight: bold;
          color: #333;
        }
        
        .radar-chart {
          text-align: center;
          margin: 20px 0;
        }
        
        .chart-label {
          font-size: 12px;
          fill: #333;
        }
        
        .chart-legend {
          display: flex;
          justify-content: center;
          gap: 20px;
          margin-top: 10px;
        }
        
        .legend-item {
          display: flex;
          align-items: center;
          gap: 5px;
        }
        
        .legend-color {
          width: 20px;
          height: 20px;
          border-radius: 3px;
        }
        
        .note {
          font-size: 12px;
          color: #666;
          margin-top: 20px;
        }
      `}</style>
    </div>
  );
};

export default EditablePPTViewer;