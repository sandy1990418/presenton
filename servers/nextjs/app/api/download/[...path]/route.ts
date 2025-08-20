import { NextRequest, NextResponse } from 'next/server';
import path from 'path';
import fs from 'fs';

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  try {
    const filePath = params.path.join('/');
    const decodedPath = decodeURIComponent(filePath);
    
    // Security: Only allow downloads from the exports directory
    const exportsDir = path.join(process.env.APP_DATA_DIRECTORY!, 'exports');
    const fullPath = path.join(exportsDir, decodedPath);
    
    // Ensure the requested file is within the exports directory
    if (!fullPath.startsWith(exportsDir)) {
      return NextResponse.json({ error: 'Invalid file path' }, { status: 403 });
    }
    
    // Check if file exists
    if (!fs.existsSync(fullPath)) {
      return NextResponse.json({ error: 'File not found' }, { status: 404 });
    }
    
    // Read the file
    const fileBuffer = fs.readFileSync(fullPath);
    const fileName = path.basename(fullPath);
    const fileExtension = path.extname(fileName).toLowerCase();
    
    // Determine content type
    let contentType = 'application/octet-stream';
    if (fileExtension === '.pdf') {
      contentType = 'application/pdf';
    } else if (fileExtension === '.pptx') {
      contentType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
    }
    
    // Return file as download
    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': `attachment; filename="${encodeURIComponent(fileName)}"`,
        'Content-Length': fileBuffer.length.toString(),
      },
    });
    
  } catch (error) {
    console.error('Download error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}