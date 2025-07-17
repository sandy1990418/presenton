import os
import uuid
import tempfile
from typing import Optional, Union


class TempFileService:
    def __init__(self):
        # 使用環境變數或默認臨時目錄
        self.base_dir = os.getenv("TEMP_DIRECTORY") or tempfile.gettempdir()
        
        # 確保base_dir不是None
        if self.base_dir is None:
            self.base_dir = tempfile.mkdtemp()
        
        # 創建presenton特定的臨時目錄
        self.base_dir = os.path.join(self.base_dir, "presenton_temp")
        
        self.cleanup_base_dir()
        os.makedirs(self.base_dir, exist_ok=True)

    def create_dir_in_dir(self, base_dir: str, dir_name: Optional[str] = None) -> str:
        temp_dir = os.path.join(base_dir, dir_name if dir_name else str(uuid.uuid4()))
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    def create_temp_dir(self, dir_name: Optional[str] = None) -> str:
        return self.create_dir_in_dir(self.base_dir, dir_name)

    def create_temp_file_path(
        self, file_path: str, dir_path: Optional[str] = None
    ) -> str:
        if dir_path is None:
            dir_path = self.base_dir

        full_path = os.path.join(dir_path, file_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        return full_path

    def create_temp_file(
        self, file_path: str, content: Union[bytes, str], dir_path: Optional[str] = None
    ) -> str:
        file_path = self.create_temp_file_path(file_path, dir_path)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(file_path, mode) as f:
            f.write(content)

        return file_path

    def read_temp_file(self, file_path: str, binary: bool = True) -> Union[bytes, str]:
        mode = "rb" if binary else "r"
        with open(file_path, mode) as f:
            return f.read()

    def cleanup_temp_file(self, file_path: str):
        if os.path.exists(file_path):
            os.remove(file_path)

    def delete_dir_files(self, dir_path: str):
        if os.path.exists(dir_path):
            for root, dirs, files in os.walk(dir_path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

    def cleanup_temp_dir(self, dir_path: str):
        if os.path.exists(dir_path):
            self.delete_dir_files(dir_path)
            os.rmdir(dir_path)

    def cleanup_base_dir(self):
        if self.base_dir and os.path.exists(self.base_dir):
            self.cleanup_temp_dir(self.base_dir)
