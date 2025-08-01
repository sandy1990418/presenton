/**
 * Utility functions for handling images in offline environments
 */

/**
 * Convert image URL to local path if available, fallback to placeholder
 * @param imageUrl - The original image URL (could be external or local)
 * @returns Local image path or placeholder
 */
export function getLocalImagePath(imageUrl: string | undefined): string {
  if (!imageUrl) {
    return '/static/images/placeholder.jpg';
  }

  // If it's already a web accessible path, return as is
  if (imageUrl.startsWith('/app_data/') || imageUrl.startsWith('/static/')) {
    return imageUrl;
  }

  // If it's a relative local path starting with ./ return as is
  if (imageUrl.startsWith('./')) {
    return imageUrl;
  }

  // Handle absolute local paths - extract relative portion for web serving
  if (imageUrl.includes('/images/')) {
    const parts = imageUrl.split('/images/');
    if (parts.length > 1) {
      const imagePath = parts[parts.length - 1];
      return `/app_data/images/${imagePath}`;
    }
  }

  // Handle paths that contain app_data directory
  if (imageUrl.includes('/app_data/')) {
    const parts = imageUrl.split('/app_data/');
    if (parts.length > 1) {
      const relativePath = parts[parts.length - 1];
      return `/app_data/${relativePath}`;
    }
  }

  // Handle database directory paths 
  if (imageUrl.includes('/database/')) {
    const parts = imageUrl.split('/database/');
    if (parts.length > 1) {
      const relativePath = parts[parts.length - 1];
      return `/app_data/${relativePath}`;
    }
  }

  // If it's an external URL, check if we have a local version
  if (imageUrl.startsWith('http')) {
    // Extract filename from URL if possible
    try {
      const url = new URL(imageUrl);
      const pathname = url.pathname;
      const filename = pathname.split('/').pop();
      
      if (filename && (filename.includes('.jpg') || filename.includes('.png') || filename.includes('.jpeg') || filename.includes('.webp'))) {
        // Try to serve from local database images directory
        return `/app_data/images/${filename}`;
      }
    } catch (e) {
      console.warn('Failed to parse image URL:', imageUrl);
    }
    
    // Fallback to placeholder for external URLs in offline mode
    return '/static/images/placeholder.jpg';
  }

  // For any other local paths, assume they need to be served from app_data
  if (imageUrl.startsWith('/')) {
    return imageUrl;
  }

  // Default fallback
  console.warn(`Unable to convert image path for offline use: ${imageUrl}`);
  return '/static/images/placeholder.jpg';
}

/**
 * Check if running in offline mode (no internet connection)
 * This is a simple heuristic - in production you might want more sophisticated detection
 */
export function isOfflineMode(): boolean {
  if (typeof window !== 'undefined') {
    return !navigator.onLine;
  }
  return false;
}

/**
 * Get image source with offline support
 * @param imageData - Image data object with __image_url__ property
 * @returns Appropriate image source for current environment
 */
export function getImageSrc(imageData: any): string {
  if (!imageData || !imageData.__image_url__) {
    return '/static/images/placeholder.jpg';
  }

  const imageUrl = imageData.__image_url__;
  
  // Always use local path conversion for better offline support
  return getLocalImagePath(imageUrl);
}

/**
 * Convert a backend file path to a frontend-accessible URL for offline environments
 * This is a convenience function that wraps getLocalImagePath for direct string usage
 * @param imagePath - The image path from the backend
 * @returns A frontend-accessible URL or fallback placeholder
 */
export function convertImagePathForOffline(imagePath: string): string {
  return getLocalImagePath(imagePath);
}