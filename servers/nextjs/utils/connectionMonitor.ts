// 連接狀態監控和健康檢查
export class ConnectionMonitor {
  private isOnline: boolean = true;
  private lastHealthCheck: number = Date.now();
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private readonly HEALTH_CHECK_INTERVAL = 30000; // 30秒
  private readonly MAX_OFFLINE_TIME = 300000; // 5分鐘

  constructor() {
    this.initializeMonitoring();
  }

  private initializeMonitoring(): void {
    // 監聽網絡狀態
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        this.isOnline = true;
        console.log('🌐 網絡連接已恢復');
      });

      window.addEventListener('offline', () => {
        this.isOnline = false;
        console.warn('🔴 網絡連接已斷開');
      });

      // 啟動健康檢查
      this.startHealthCheck();
    }
  }

  private startHealthCheck(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
    }

    this.healthCheckInterval = setInterval(async () => {
      const isHealthy = await this.performHealthCheck();
      
      if (!isHealthy) {
        console.warn('🚨 後端服務器健康檢查失敗');
        this.notifyConnectionIssue();
      }
    }, this.HEALTH_CHECK_INTERVAL);
  }

  private async performHealthCheck(): Promise<boolean> {
    try {
      const response = await fetch('/api/v1/ppt/health', {
        method: 'GET',
        timeout: 5000,
      } as any);

      if (response.ok) {
        this.lastHealthCheck = Date.now();
        return true;
      }
      return false;
    } catch (error) {
      console.error('健康檢查失敗:', error);
      return false;
    }
  }

  private notifyConnectionIssue(): void {
    const timeSinceLastCheck = Date.now() - this.lastHealthCheck;
    
    if (timeSinceLastCheck > this.MAX_OFFLINE_TIME) {
      // 觸發用戶通知
      if (typeof window !== 'undefined') {
        const event = new CustomEvent('connectionIssue', {
          detail: {
            message: '後端服務器可能無法訪問，請檢查服務器狀態',
            severity: 'error',
            duration: timeSinceLastCheck
          }
        });
        window.dispatchEvent(event);
      }
    }
  }

  public getConnectionStatus(): {
    isOnline: boolean;
    isHealthy: boolean;
    lastHealthCheck: number;
  } {
    return {
      isOnline: this.isOnline,
      isHealthy: Date.now() - this.lastHealthCheck < this.MAX_OFFLINE_TIME,
      lastHealthCheck: this.lastHealthCheck
    };
  }

  public stopMonitoring(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }
}

// 全局實例
export const connectionMonitor = new ConnectionMonitor();