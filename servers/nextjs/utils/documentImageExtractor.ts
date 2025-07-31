/**
 * Client-side Document Image Extraction Utility
 * 
 * Extracts images from documents with position and context information
 * using the browser's native capabilities
 */

export interface ExtractedImageData {
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

export class DocumentImageExtractor {
  
  /**
   * Extract images from a PDF file using PDF.js
   */
  static async extractFromPDF(file: File): Promise<ExtractedImageData[]> {
    const images: ExtractedImageData[] = [];
    
    try {
      // Use PDF.js to parse the PDF (fallback if not available)
      let pdfjsLib;
      try {
        pdfjsLib = await import('pdfjs-dist');
        pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';
      } catch (error) {
        console.warn('PDF.js not available, skipping PDF extraction');
        return [];
      }
      
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      
      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        const page = await pdf.getPage(pageNum);
        
        // Get text content for context
        const textContent = await page.getTextContent();
        const pageText = textContent.items
          .map((item: any) => item.str)
          .join(' ');
        
        // Extract images from the page
        const operatorList = await page.getOperatorList();
        
        for (let i = 0; i < operatorList.fnArray.length; i++) {
          if (operatorList.fnArray[i] === pdfjsLib.OPS.paintImageXObject) {
            try {
              // Get image data
              const imgName = operatorList.argsArray[i][0];
              const resources = await page.objs.get(imgName);
              
              if (resources && resources.data) {
                // Create canvas and draw image
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                
                canvas.width = resources.width;
                canvas.height = resources.height;
                
                // Convert image data to canvas
                const imageData = new ImageData(
                  new Uint8ClampedArray(resources.data),
                  resources.width,
                  resources.height
                );
                ctx?.putImageData(imageData, 0, 0);
                
                // Convert to blob
                const blob = await new Promise<Blob>((resolve) => {
                  canvas.toBlob((blob) => resolve(blob!), 'image/png');
                });
                
                const imageSrc = URL.createObjectURL(blob);
                
                images.push({
                  imageBlob: blob,
                  imageSrc,
                  fileName: `${file.name}_page${pageNum}_img${i}.png`,
                  contextText: this.extractRelevantContext(pageText, 200),
                  position: {
                    page: pageNum,
                    width: resources.width,
                    height: resources.height
                  }
                });
              }
            } catch (error) {
              console.error('Error extracting image from PDF:', error);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error processing PDF:', error);
    }
    
    return images;
  }
  
  /**
   * Extract images from HTML/DOCX using file conversion
   */
  static async extractFromDocument(file: File): Promise<ExtractedImageData[]> {
    const images: ExtractedImageData[] = [];
    
    try {
      // Create a temporary container
      const container = document.createElement('div');
      container.style.visibility = 'hidden';
      container.style.position = 'absolute';
      container.style.top = '-9999px';
      document.body.appendChild(container);
      
      if (file.type.includes('html') || file.name.endsWith('.html')) {
        // Handle HTML files
        const text = await file.text();
        container.innerHTML = text;
        
        const imgElements = container.querySelectorAll('img');
        
        for (let i = 0; i < imgElements.length; i++) {
          const img = imgElements[i];
          const extractedImage = await this.processImageElement(img, file.name, i);
          if (extractedImage) {
            images.push(extractedImage);
          }
        }
      } else if (file.type.includes('word') || file.name.endsWith('.docx')) {
        // For DOCX, we'll need to use a library like mammoth.js
        try {
          let mammoth;
          try {
            mammoth = await import('mammoth');
          } catch (error) {
            console.warn('Mammoth.js not available, skipping DOCX extraction');
            return [];
          }
          const result = await mammoth.convertToHtml({ arrayBuffer: await file.arrayBuffer() });
          
          container.innerHTML = result.value;
          
          const imgElements = container.querySelectorAll('img');
          
          for (let i = 0; i < imgElements.length; i++) {
            const img = imgElements[i];
            const extractedImage = await this.processImageElement(img, file.name, i);
            if (extractedImage) {
              images.push(extractedImage);
            }
          }
        } catch (error) {
          console.error('Error processing DOCX:', error);
        }
      }
      
      // Clean up
      document.body.removeChild(container);
      
    } catch (error) {
      console.error('Error extracting images from document:', error);
    }
    
    return images;
  }
  
  /**
   * Process an individual image element
   */
  private static async processImageElement(
    img: HTMLImageElement, 
    documentName: string, 
    index: number
  ): Promise<ExtractedImageData | null> {
    try {
      // Wait for image to load
      await new Promise((resolve, reject) => {
        if (img.complete) {
          resolve(void 0);
        } else {
          img.onload = resolve;
          img.onerror = reject;
        }
      });
      
      // Create canvas to convert image to blob
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      canvas.width = img.naturalWidth || img.width;
      canvas.height = img.naturalHeight || img.height;
      
      ctx?.drawImage(img, 0, 0);
      
      // Convert to blob
      const blob = await new Promise<Blob>((resolve) => {
        canvas.toBlob((blob) => resolve(blob!), 'image/png');
      });
      
      const imageSrc = URL.createObjectURL(blob);
      
      // Extract context text (surrounding elements)
      const contextText = this.extractImageContext(img);
      
      return {
        imageBlob: blob,
        imageSrc,
        fileName: `${documentName}_img${index}.png`,
        contextText,
        position: {
          width: canvas.width,
          height: canvas.height,
          x: img.offsetLeft,
          y: img.offsetTop
        },
        altText: img.alt,
        caption: img.title || img.getAttribute('data-caption') || ''
      };
      
    } catch (error) {
      console.error('Error processing image element:', error);
      return null;
    }
  }
  
  /**
   * Extract context text around an image element
   */
  private static extractImageContext(img: HTMLImageElement): string {
    const contextParts: string[] = [];
    
    // Get text from parent elements
    let parent = img.parentElement;
    while (parent && contextParts.join(' ').length < 300) {
      const textNodes = this.getTextContent(parent);
      if (textNodes.length > 0) {
        contextParts.unshift(...textNodes);
      }
      parent = parent.parentElement;
    }
    
    // Get text from sibling elements
    const siblings = img.parentElement?.children;
    if (siblings) {
      for (const sibling of Array.from(siblings)) {
        if (sibling !== img) {
          const siblingText = this.getTextContent(sibling as HTMLElement);
          contextParts.push(...siblingText);
        }
      }
    }
    
    return this.extractRelevantContext(contextParts.join(' '), 300);
  }
  
  /**
   * Get text content from an element, excluding script and style tags
   */
  private static getTextContent(element: HTMLElement): string[] {
    const textParts: string[] = [];
    
    for (const node of Array.from(element.childNodes)) {
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent?.trim();
        if (text && text.length > 0) {
          textParts.push(text);
        }
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        const el = node as HTMLElement;
        if (!['SCRIPT', 'STYLE', 'IMG'].includes(el.tagName)) {
          textParts.push(...this.getTextContent(el));
        }
      }
    }
    
    return textParts;
  }
  
  /**
   * Extract relevant context from text, focusing on meaningful content
   */
  private static extractRelevantContext(text: string, maxLength: number): string {
    // Clean up text
    const cleaned = text
      .replace(/\s+/g, ' ')
      .replace(/[^\w\s.,!?;:-]/g, '')
      .trim();
    
    if (cleaned.length <= maxLength) {
      return cleaned;
    }
    
    // Try to break at sentence boundaries
    const sentences = cleaned.split(/[.!?]+/);
    let result = '';
    
    for (const sentence of sentences) {
      if ((result + sentence).length <= maxLength) {
        result += sentence + '. ';
      } else {
        break;
      }
    }
    
    return result.trim() || cleaned.substring(0, maxLength) + '...';
  }
  
  /**
   * Extract all images from multiple documents
   */
  static async extractFromFiles(files: File[]): Promise<ExtractedImageData[]> {
    const allImages: ExtractedImageData[] = [];
    
    for (const file of files) {
      try {
        if (file.type === 'application/pdf') {
          const pdfImages = await this.extractFromPDF(file);
          allImages.push(...pdfImages);
        } else {
          const docImages = await this.extractFromDocument(file);
          allImages.push(...docImages);
        }
      } catch (error) {
        console.error(`Error processing file ${file.name}:`, error);
      }
    }
    
    return allImages;
  }
}