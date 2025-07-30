/**
 * Convert absolute export file path to relative URL for serving
 * @param absolutePath - The absolute path returned by FastAPI
 * @returns Relative URL that can be served by Next.js
 */
export function convertExportPathToUrl(absolutePath: string): string {
  console.log('Converting export path:', absolutePath);
  
  if (!absolutePath) {
    throw new Error('Export path is required');
  }

  // If it's already a relative URL (starts with /app_data or /api), return as is
  if (absolutePath.startsWith('/app_data') || absolutePath.startsWith('/api') || absolutePath.startsWith('http')) {
    console.log('Path already relative/URL, returning as is:', absolutePath);
    return absolutePath;
  }

  // Extract filename from absolute path
  const filename = absolutePath.split('/').pop();
  if (!filename) {
    throw new Error('Invalid export path - no filename found');
  }

  // Return URL that will be served by our Next.js API route
  const convertedUrl = `/app_data/exports/${filename}`;
  console.log('Converted path to URL:', convertedUrl);
  return convertedUrl;
}

/**
 * Download file with proper error handling
 * @param path - File path (will be converted if absolute)
 * @param filename - Optional custom filename for download
 */
export function downloadFile(path: string, filename?: string) {
  try {
    console.log('downloadFile called with path:', path);
    const downloadUrl = convertExportPathToUrl(path);
    const downloadFilename = filename || downloadUrl.split('/').pop() || 'download';

    console.log('Final download URL:', downloadUrl);
    console.log('Download filename:', downloadFilename);

    // Force download using fetch and blob approach for better control
    fetch(downloadUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.blob();
      })
      .then(blob => {
        // Create blob URL and download
        const blobUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = downloadFilename;
        link.style.display = 'none';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Clean up blob URL
        window.URL.revokeObjectURL(blobUrl);
        console.log(`Download completed for: ${downloadUrl}`);
      })
      .catch(error => {
        console.error('Fetch download failed, trying direct link method:', error);
        
        // Fallback to direct link method
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = downloadFilename;
        link.style.display = 'none';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      });
    
    console.log(`Download initiated for: ${downloadUrl}`);
  } catch (error) {
    console.error('Download failed:', error);
    throw error;
  }
}