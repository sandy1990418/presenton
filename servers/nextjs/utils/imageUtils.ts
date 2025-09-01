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

