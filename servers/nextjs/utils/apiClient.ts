// API 客戶端工具，包含重試邏輯和錯誤處理
interface ApiClientOptions {
  timeout?: number;
  retries?: number;
  retryDelay?: number;
}

interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  status?: number;
}

class ApiClient {
  private baseURL: string;
  private defaultOptions: ApiClientOptions;

  constructor(baseURL: string = '', options: ApiClientOptions = {}) {
    this.baseURL = baseURL;
    this.defaultOptions = {
      timeout: 300000, // 5分鐘默認超時
      retries: 3,
      retryDelay: 1000,
      ...options
    };
  }

  private async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private async makeRequest<T>(
    url: string,
    options: RequestInit = {},
    apiOptions: ApiClientOptions = {}
  ): Promise<ApiResponse<T>> {
    const mergedOptions = { ...this.defaultOptions, ...apiOptions };
    const controller = new AbortController();
    
    // 設置超時
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, mergedOptions.timeout);

    const requestOptions: RequestInit = {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'Connection': 'keep-alive',
        ...options.headers,
      },
    };

    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= mergedOptions.retries!; attempt++) {
      try {
        const response = await fetch(`${this.baseURL}${url}`, requestOptions);
        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data,
          status: response.status
        };

      } catch (error) {
        lastError = error as Error;
        
        // 如果是最後一次嘗試，直接拋出錯誤
        if (attempt === mergedOptions.retries) {
          break;
        }

        // 檢查是否是可重試的錯誤
        if (this.isRetryableError(error as Error)) {
          console.warn(`API請求失敗 (嘗試 ${attempt + 1}/${mergedOptions.retries! + 1}):`, error);
          await this.delay(mergedOptions.retryDelay! * Math.pow(2, attempt)); // 指數退避
        } else {
          break; // 不可重試的錯誤，直接退出
        }
      }
    }

    clearTimeout(timeoutId);
    return {
      success: false,
      error: lastError?.message || 'Unknown error',
      status: lastError?.name === 'AbortError' ? 408 : 500
    };
  }

  private isRetryableError(error: Error): boolean {
    const retryableErrors = [
      'socket hang up',
      'ECONNRESET',
      'ETIMEDOUT',
      'ENOTFOUND',
      'ECONNREFUSED',
      'AbortError'
    ];
    
    return retryableErrors.some(retryableError => 
      error.message.includes(retryableError) || error.name === retryableError
    );
  }

  // GET 請求
  async get<T>(url: string, options?: ApiClientOptions): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(url, { method: 'GET' }, options);
  }

  // POST 請求
  async post<T>(url: string, data?: any, options?: ApiClientOptions): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(url, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }, options);
  }

  // PUT 請求
  async put<T>(url: string, data?: any, options?: ApiClientOptions): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(url, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    }, options);
  }

  // DELETE 請求
  async delete<T>(url: string, options?: ApiClientOptions): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(url, { method: 'DELETE' }, options);
  }

  // 表單數據請求
  async postForm<T>(url: string, formData: FormData, options?: ApiClientOptions): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(url, {
      method: 'POST',
      body: formData,
      headers: {
        // 不設置 Content-Type，讓瀏覽器自動設置
      },
    }, options);
  }
}

// 創建默認實例
export const apiClient = new ApiClient('/api/v1/ppt', {
  timeout: 300000, // 5分鐘
  retries: 3,
  retryDelay: 2000 // 2秒起始延遲
});

// 創建長時間運行請求的實例
export const longRunningApiClient = new ApiClient('/api/v1/ppt', {
  timeout: 600000, // 10分鐘
  retries: 5,
  retryDelay: 3000 // 3秒起始延遲
});

export default ApiClient;