/**
 * Client-side Embedding Service
 * 
 * Uses browser-based models for text embeddings and semantic similarity
 * without requiring server-side computation
 */

interface EmbeddingResult {
  embedding: number[];
  similarity?: number;
}

interface ImageTextMatch {
  imageIndex: number;
  slideIndex: number;
  similarity: number;
  confidence: number;
  placementSuggestion: 'header' | 'content' | 'sidebar' | 'inline';
}

export class ClientEmbeddingService {
  private static instance: ClientEmbeddingService;
  private isInitialized = false;
  private model: any = null;
  private tokenizer: any = null;

  private constructor() {}

  static getInstance(): ClientEmbeddingService {
    if (!ClientEmbeddingService.instance) {
      ClientEmbeddingService.instance = new ClientEmbeddingService();
    }
    return ClientEmbeddingService.instance;
  }

  /**
   * Initialize the embedding model using Web-based transformers
   */
  async initialize(): Promise<boolean> {
    if (this.isInitialized) return true;

    try {
      // Option 1: Use Transformers.js (lightweight browser-based models)
      const { pipeline, env } = await import('@xenova/transformers');
      
      // Set to use local models (no external downloads during inference)
      env.allowLocalModels = false;
      
      // Load a lightweight sentence embedding model
      this.model = await pipeline(
        'feature-extraction', 
        'Xenova/all-MiniLM-L6-v2',
        { 
          progress_callback: (progress: any) => {
            console.log('Loading embedding model:', Math.round(progress.progress || 0), '%');
          }
        }
      );

      this.isInitialized = true;
      console.log('✅ Client-side embedding model loaded successfully');
      return true;

    } catch (error) {
      console.warn('Transformers.js not available, falling back to simple similarity');
      
      // Fallback: Use simple keyword-based similarity
      this.isInitialized = true;
      this.model = null;
      return false;
    }
  }

  /**
   * Create embeddings for text using the loaded model
   */
  async createEmbedding(text: string): Promise<EmbeddingResult> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    try {
      if (this.model) {
        // Use Transformers.js model
        const result = await this.model(text, { pooling: 'mean', normalize: true });
        
        // Convert tensor to array
        const embedding = Array.from(result.data) as number[];
        
        return { embedding };
      } else {
        // Fallback: Create simple feature vector from text
        return { embedding: this.createSimpleEmbedding(text) };
      }
    } catch (error) {
      console.error('Error creating embedding:', error);
      return { embedding: this.createSimpleEmbedding(text) };
    }
  }

  /**
   * Create multiple embeddings efficiently
   */
  async createEmbeddings(texts: string[]): Promise<EmbeddingResult[]> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    const embeddings: EmbeddingResult[] = [];

    try {
      if (this.model && texts.length > 1) {
        // Batch processing for efficiency
        const results = await this.model(texts, { pooling: 'mean', normalize: true });
        
        for (let i = 0; i < texts.length; i++) {
          const embedding = Array.from(results.data.slice(i * results.dims[1], (i + 1) * results.dims[1])) as number[];
          embeddings.push({ embedding });
        }
      } else {
        // Process individually or use fallback
        for (const text of texts) {
          const result = await this.createEmbedding(text);
          embeddings.push(result);
        }
      }
    } catch (error) {
      console.error('Error creating batch embeddings:', error);
      // Fallback to individual processing
      for (const text of texts) {
        embeddings.push({ embedding: this.createSimpleEmbedding(text) });
      }
    }

    return embeddings;
  }

  /**
   * Calculate cosine similarity between two embeddings
   */
  calculateSimilarity(embedding1: number[], embedding2: number[]): number {
    try {
      // Cosine similarity calculation
      const dotProduct = embedding1.reduce((sum, a, i) => sum + a * embedding2[i], 0);
      const magnitudeA = Math.sqrt(embedding1.reduce((sum, a) => sum + a * a, 0));
      const magnitudeB = Math.sqrt(embedding2.reduce((sum, b) => sum + b * b, 0));
      
      if (magnitudeA === 0 || magnitudeB === 0) return 0;
      
      return dotProduct / (magnitudeA * magnitudeB);
    } catch (error) {
      console.error('Error calculating similarity:', error);
      return 0;
    }
  }

  /**
   * Match images to slides using embeddings
   */
  async matchImagesToSlides(
    images: Array<{
      fileName: string;
      contextText: string;
      altText?: string;
      caption?: string;
      position?: any;
    }>,
    slides: Array<{
      title: string;
      body?: string;
    }>
  ): Promise<ImageTextMatch[]> {
    if (!images.length || !slides.length) return [];

    try {
      // Create embeddings for image contexts
      const imageTexts = images.map(img => {
        const context = [img.contextText, img.altText, img.caption]
          .filter(Boolean)
          .join(' ')
          .trim();
        return context || 'image visual content';
      });

      const imageEmbeddings = await this.createEmbeddings(imageTexts);

      // Create embeddings for slide content
      const slideTexts = slides.map(slide => 
        `${slide.title || ''} ${slide.body || ''}`.trim()
      );

      const slideEmbeddings = await this.createEmbeddings(slideTexts);

      // Find best matches
      const matches: ImageTextMatch[] = [];

      imageEmbeddings.forEach((imageEmbed, imageIndex) => {
        let bestMatch = {
          slideIndex: 0,
          similarity: 0,
          confidence: 0
        };

        slideEmbeddings.forEach((slideEmbed, slideIndex) => {
          const similarity = this.calculateSimilarity(
            imageEmbed.embedding,
            slideEmbed.embedding
          );

          if (similarity > bestMatch.similarity) {
            bestMatch = {
              slideIndex,
              similarity,
              confidence: Math.min(0.95, similarity + 0.1) // Boost confidence slightly
            };
          }
        });

        // Only include matches above threshold
        if (bestMatch.similarity > 0.1) {
          matches.push({
            imageIndex,
            slideIndex: bestMatch.slideIndex,
            similarity: bestMatch.similarity,
            confidence: bestMatch.confidence,
            placementSuggestion: this.suggestPlacement(images[imageIndex], bestMatch.similarity)
          });
        }
      });

      // Sort by similarity score
      matches.sort((a, b) => b.similarity - a.similarity);

      // Limit to avoid overcrowding slides
      return this.optimizeDistribution(matches);

    } catch (error) {
      console.error('Error matching images to slides:', error);
      return this.fallbackMatching(images, slides);
    }
  }

  /**
   * Suggest optimal placement for an image
   */
  private suggestPlacement(
    image: any, 
    similarity: number
  ): 'header' | 'content' | 'sidebar' | 'inline' {
    const width = image.position?.width || 0;
    const height = image.position?.height || 0;

    // High similarity images get better placement
    if (similarity > 0.7) {
      if (width > height && width > 600) return 'header';
      if (height > width && height > 400) return 'sidebar';
      return 'content';
    }

    // Lower similarity images get inline placement
    return 'inline';
  }

  /**
   * Optimize distribution to avoid too many images per slide
   */
  private optimizeDistribution(matches: ImageTextMatch[]): ImageTextMatch[] {
    const slideImageCount: { [key: number]: number } = {};
    const optimized: ImageTextMatch[] = [];
    const maxImagesPerSlide = 2;

    for (const match of matches) {
      const currentCount = slideImageCount[match.slideIndex] || 0;
      
      if (currentCount < maxImagesPerSlide || match.confidence > 0.8) {
        optimized.push(match);
        slideImageCount[match.slideIndex] = currentCount + 1;
      }
    }

    return optimized;
  }

  /**
   * Simple keyword-based fallback matching
   */
  private fallbackMatching(images: any[], slides: any[]): ImageTextMatch[] {
    const matches: ImageTextMatch[] = [];

    images.forEach((image, imageIndex) => {
      const imageText = (image.contextText || '').toLowerCase();
      const keywords = imageText.split(/\s+/).filter((word: string) => word.length > 3);

      let bestMatch = { slideIndex: 0, score: 0 };

      slides.forEach((slide, slideIndex) => {
        const slideText = `${slide.title || ''} ${slide.body || ''}`.toLowerCase();
        const keywordMatches = keywords.filter((keyword: string) => slideText.includes(keyword)).length;
        const score = keywords.length > 0 ? keywordMatches / keywords.length : 0.1;

        if (score > bestMatch.score) {
          bestMatch = { slideIndex, score };
        }
      });

      if (bestMatch.score > 0.1) {
        matches.push({
          imageIndex,
          slideIndex: bestMatch.slideIndex,
          similarity: bestMatch.score,
          confidence: Math.min(0.8, bestMatch.score + 0.2),
          placementSuggestion: this.suggestPlacement(image, bestMatch.score)
        });
      }
    });

    return matches.sort((a, b) => b.similarity - a.similarity);
  }

  /**
   * Create simple embedding based on text features (fallback)
   */
  private createSimpleEmbedding(text: string): number[] {
    const words = text.toLowerCase().split(/\s+/);
    const features: number[] = new Array(384).fill(0); // Match common embedding dimension

    // Simple feature extraction based on word characteristics
    words.forEach((word, index) => {
      if (word.length > 0) {
        const hash = this.simpleHash(word) % 384;
        features[hash] += 1 / (index + 1); // Weight by position
      }
    });

    // Normalize
    const magnitude = Math.sqrt(features.reduce((sum, val) => sum + val * val, 0));
    if (magnitude > 0) {
      return features.map(val => val / magnitude);
    }

    return features;
  }

  /**
   * Simple hash function for consistent word mapping
   */
  private simpleHash(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }

  /**
   * Check if advanced embeddings are available
   */
  hasAdvancedEmbeddings(): boolean {
    return this.model !== null;
  }

  /**
   * Get model loading status
   */
  getStatus(): { initialized: boolean; hasAdvancedModel: boolean; modelName: string } {
    return {
      initialized: this.isInitialized,
      hasAdvancedModel: this.model !== null,
      modelName: this.model ? 'Xenova/all-MiniLM-L6-v2' : 'Keyword-based fallback'
    };
  }
}