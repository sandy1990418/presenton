import os
import uvicorn
import argparse


if __name__ == "__main__":
    os.makedirs("debug", exist_ok=True)

    parser = argparse.ArgumentParser(description="Run the FastAPI server")
    parser.add_argument(
        "--port", type=int, required=True, help="Port number to run the server on"
    )
    args = parser.parse_args()

    uvicorn.run(
        "api.main:app", 
        host="0.0.0.0", 
        port=args.port, 
        log_level="info",
        timeout_keep_alive=300,  # 5分鐘 keep-alive 超時
        timeout_graceful_shutdown=30,  # 30秒優雅關閉
        limit_concurrency=1000,  # 並發限制
        limit_max_requests=1000,  # 最大請求數
        access_log=True,
        reload=False,
        workers=1
    )
