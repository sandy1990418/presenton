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

  // If it's already a local path, return as is
  if (imageUrl.startsWith('/') || imageUrl.startsWith('./')) {
    return imageUrl;
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

  // Default fallback
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
  
  // In offline mode or if URL is external, use local path
  if (isOfflineMode() || imageUrl.startsWith('http')) {
    return getLocalImagePath(imageUrl);
  }

  return imageUrl;
}