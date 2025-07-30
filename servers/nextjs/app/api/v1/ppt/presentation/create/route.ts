import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 300000); // 5 minutes timeout

    const response = await fetch('http://localhost:8000/api/v1/ppt/presentation/create', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: `FastAPI error: ${errorText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Presentation creation proxy error:', error);
    
    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        return NextResponse.json(
          { error: 'Request timeout - presentation creation took too long' },
          { status: 504 }
        );
      }
      
      if (error.message.includes('ECONNRESET') || error.message.includes('socket hang up')) {
        return NextResponse.json(
          { error: 'Connection lost to backend server' },
          { status: 502 }
        );
      }
    }

    return NextResponse.json(
      { error: 'Internal server error during presentation creation' },
      { status: 500 }
    );
  }
}