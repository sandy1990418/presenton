'use client';

import React, { useState, useCallback } from 'react';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, CheckCircle, Image as ImageIcon, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
// Simplified interface for now - will integrate full extraction later
interface ExtractedImageData {
  imageBlob: Blob;
  imageSrc: string;
  fileName: string;
  contextText: string;
  position: {
    page?: number;
    x?: number;
    y?: number;
    width: number;
    height: number;
  };
  altText?: string;
  caption?: string;
}

interface ImageMatch {
  slideIndex: number;
  slideTitle: string;
  imageData: {
    fileName: string;
    imageSrc: string;
    contextText: string;
    position: any;
    altText?: string;
    caption?: string;
  };
  similarityScore: number;
  placementSuggestion: string;
  confidence: number;
}

interface ImageExtractionProcessorProps {
  files: File[];
  presentationId: string | null;
  onImagesExtracted: (matches: ImageMatch[]) => void;
  onExtractionComplete: () => void;
}

export const ImageExtractionProcessor: React.FC<ImageExtractionProcessorProps> = ({
  files,
  presentationId,
  onImagesExtracted,
  onExtractionComplete
}) => {
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionProgress, setExtractionProgress] = useState(0);
  const [extractionStatus, setExtractionStatus] = useState<string>('');
  const [extractedImages, setExtractedImages] = useState<ExtractedImageData[]>([]);
  const [imageMatches, setImageMatches] = useState<ImageMatch[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [aiProvider, setAiProvider] = useState<string>('Unknown');
  const [matchingMethod, setMatchingMethod] = useState<string>('Unknown');

  const extractImagesFromDocuments = useCallback(async () => {
    if (!files.length || !presentationId) {
      toast.error('No files or presentation ID provided');
      return;
    }

    setIsExtracting(true);
    setExtractionProgress(0);
    setExtractionStatus('Starting image extraction...');

    try {
      // Step 1: Extract images from documents (demo data for now)
      setExtractionStatus('Extracting images from documents...');
      setExtractionProgress(20);

      const extractedImages: ExtractedImageData[] = [
        {
          imageBlob: new Blob(),
          imageSrc: '/static/images/placeholder.jpg',
          fileName: 'chart_analysis.png',
          contextText: 'Financial analysis chart showing revenue growth over quarterly periods with detailed breakdown of market segments',
          position: { width: 800, height: 600 },
          altText: 'Revenue growth chart',
          caption: 'Quarterly Revenue Analysis'
        },
        {
          imageBlob: new Blob(),
          imageSrc: '/static/images/placeholder.jpg', 
          fileName: 'process_diagram.png',
          contextText: 'Process workflow diagram illustrating the steps in our manufacturing pipeline with quality control checkpoints',
          position: { width: 600, height: 400 },
          altText: 'Manufacturing process',
          caption: 'Production Workflow'
        }
      ];

      setExtractedImages(extractedImages);

      // Step 2: Process images and match using server-side AI
      setExtractionStatus('Processing images with AI matching...');
      setExtractionProgress(60);

      const imageDataForProcessing = extractedImages.map(img => ({
        fileName: img.fileName,
        imageSrc: img.imageSrc,
        contextText: img.contextText,
        position: img.position,
        altText: img.altText,
        caption: img.caption
      }));

      const matchingFormData = new FormData();
      matchingFormData.append('presentation_id', presentationId);
      matchingFormData.append('images_data', JSON.stringify(imageDataForProcessing));

      const matchingResponse = await fetch('/api/v1/ppt/image-matching/process-extracted-images', {
        method: 'POST',
        body: matchingFormData,
      });

      if (!matchingResponse.ok) {
        throw new Error('Failed to process image matching');
      }

      const matchingResult = await matchingResponse.json();

      if (matchingResult.success) {
        setImageMatches(matchingResult.matches || []);
        setExtractionStatus(`Successfully matched ${matchingResult.matches?.length || 0} images`);
        setExtractionProgress(100);
        setShowResults(true);

        // Notify parent component
        onImagesExtracted(matchingResult.matches || []);
        
        toast.success(`Successfully matched ${matchingResult.matches?.length || 0} images with AI!`);
      } else {
        throw new Error(matchingResult.message || 'Image matching failed');
      }

    } catch (error) {
      console.error('Image extraction error:', error);
      setExtractionStatus(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      toast.error('Failed to extract and match images');
    } finally {
      setIsExtracting(false);
      onExtractionComplete();
    }
  }, [files, presentationId, onImagesExtracted, onExtractionComplete]);

  const renderExtractionProgress = () => (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {isExtracting ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <ImageIcon className="w-5 h-5" />
          )}
          Image Extraction
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span>{extractionStatus}</span>
            <span>{extractionProgress}%</span>
          </div>
          <Progress value={extractionProgress} className="w-full" />
          
          {!isExtracting && extractionProgress < 100 && (
            <Button 
              onClick={extractImagesFromDocuments}
              className="w-full"
              disabled={!presentationId}
            >
              <ImageIcon className="w-4 h-4 mr-2" />
              Extract Images from Documents
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );

  const renderImageMatches = () => {
    if (!showResults || imageMatches.length === 0) return null;

    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            Image Matches Found
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="text-sm text-gray-600">
              Found {imageMatches.length} images that match your presentation content:
            </div>
            
            {imageMatches.map((match, index) => (
              <div key={index} className="border rounded-lg p-3 space-y-2">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="font-medium text-sm">
                      Slide {match.slideIndex + 1}: {match.slideTitle}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {match.imageData.fileName}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Badge 
                      variant={match.confidence > 0.7 ? "default" : "secondary"}
                      className="text-xs"
                    >
                      {Math.round(match.confidence * 100)}% match
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {match.placementSuggestion}
                    </Badge>
                  </div>
                </div>
                
                {match.imageData.contextText && (
                  <div className="text-xs text-gray-600 bg-gray-50 p-2 rounded">
                    Context: {match.imageData.contextText.substring(0, 100)}...
                  </div>
                )}
                
                {match.imageData.imageSrc && (
                  <div className="mt-2">
                    <img 
                      src={match.imageData.imageSrc} 
                      alt={match.imageData.altText || 'Extracted image'}
                      className="max-w-32 max-h-24 object-contain border rounded"
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderExtractedImages = () => {
    if (!extractedImages.length || showResults) return null;

    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImageIcon className="w-5 h-5" />
            Extracted Images ({extractedImages.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {extractedImages.slice(0, 6).map((img, index) => (
              <div key={index} className="border rounded p-2">
                <img 
                  src={img.imageSrc} 
                  alt={img.altText || `Extracted image ${index + 1}`}
                  className="w-full h-20 object-contain mb-2"
                />
                <div className="text-xs text-gray-600 truncate">
                  {img.fileName}
                </div>
                {img.contextText && (
                  <div className="text-xs text-gray-400 truncate mt-1">
                    {img.contextText.substring(0, 50)}...
                  </div>
                )}
              </div>
            ))}
          </div>
          {extractedImages.length > 6 && (
            <div className="text-sm text-gray-500 mt-3 text-center">
              ... and {extractedImages.length - 6} more images
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-4">
      {renderExtractionProgress()}
      {renderExtractedImages()}
      {renderImageMatches()}
    </div>
  );
};

export default ImageExtractionProcessor;