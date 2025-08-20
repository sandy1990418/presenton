import path from 'path';
import fs from 'fs';
import puppeteer from 'puppeteer';

import { sanitizeFilename } from '@/app/(presentation-generator)/utils/others';
import { NextResponse, NextRequest } from 'next/server';


export async function POST(req: NextRequest) {
  try {
    const { id, title } = await req.json();
    console.log('PDF Export request:', { id, title });
    
    if (!id) {
      return NextResponse.json({ error: "Missing Presentation ID" }, { status: 400 });
    }
  const browser = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-web-security',
    ]
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });
  page.setDefaultNavigationTimeout(300000);
  page.setDefaultTimeout(300000);

  await page.goto(`http://localhost:3000/pdf-maker?id=${id}`, { waitUntil: 'networkidle0', timeout: 180000 });

  await page.waitForFunction('() => document.readyState === "complete"')

  try {
    await page.waitForFunction(
      `
      () => {
        const allElements = document.querySelectorAll('*');
        let loadedElements = 0;
        let totalElements = allElements.length;
        
        for (let el of allElements) {
            const style = window.getComputedStyle(el);
            const isVisible = style.display !== 'none' && 
                            style.visibility !== 'hidden' && 
                            style.opacity !== '0';
            
            if (isVisible && el.offsetWidth > 0 && el.offsetHeight > 0) {
                loadedElements++;
            }
        }
        
        return (loadedElements / totalElements) >= 0.99;
      }
      `,
      { timeout: 300000 }
    );

    await new Promise(resolve => setTimeout(resolve, 1000));

  } catch (error) {
    console.log("Warning: Some content may not have loaded completely:", error);
  }


  const pdfBuffer = await page.pdf({
    width: "1280px",
    height: "720px",
    printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  });

    await browser.close();

    const sanitizedTitle = sanitizeFilename(title ?? 'presentation').replace(/\s+/g, '_');
    const fileName = `${sanitizedTitle}.pdf`;
    const destinationPath = path.join(process.env.APP_DATA_DIRECTORY!, 'exports', fileName);
    
    await fs.promises.mkdir(path.dirname(destinationPath), { recursive: true });
    await fs.promises.writeFile(destinationPath, pdfBuffer);

    console.log(`PDF generated successfully: ${fileName}, size: ${pdfBuffer.length} bytes`);

    // Return the download URL in JSON format for compatibility
    const downloadUrl = `/api/download/${fileName}`;
    return NextResponse.json({
      success: true,
      path: downloadUrl,
      filename: fileName
    });
  } catch (error) {
    console.error('PDF Export error:', error);
    return NextResponse.json({ 
      error: 'Failed to generate PDF',
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 });
  }
}
