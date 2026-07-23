import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess

# 定義 gyan.dev 的 FFmpeg Essentials Release 下載網址
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

class FFmpegHelper:
    def __init__(self, bin_dir=None):
        if bin_dir is None:
            # 預設 bin 目錄位於專案根目錄下的 bin/
            self.bin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
        else:
            self.bin_dir = bin_dir
            
        self.ffmpeg_path = os.path.join(self.bin_dir, "ffmpeg.exe")
        self.ffprobe_path = os.path.join(self.bin_dir, "ffprobe.exe")

    def check_system_ffmpeg(self) -> bool:
        """檢查系統 PATH 中是否有 ffmpeg"""
        try:
            # 在 Windows 上使用 shell=True 來執行並隱藏視窗
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def is_available(self) -> bool:
        """檢查系統有 FFmpeg，或者本地 bin 有 ffmpeg.exe & ffprobe.exe"""
        if self.check_system_ffmpeg():
            return True
        return os.path.exists(self.ffmpeg_path) and os.path.exists(self.ffprobe_path)

    def get_ffmpeg_cmd(self) -> str:
        """獲取可以用於運行的 ffmpeg 指令路徑"""
        if self.check_system_ffmpeg():
            return "ffmpeg"
        if os.path.exists(self.ffmpeg_path):
            return self.ffmpeg_path
        raise FileNotFoundError("找不到 FFmpeg。請先下載 FFmpeg。")

    def get_ffprobe_cmd(self) -> str:
        """獲取可以用於運行的 ffprobe 指令路徑"""
        if self.check_system_ffmpeg():
            return "ffprobe"
        if os.path.exists(self.ffprobe_path):
            return self.ffprobe_path
        raise FileNotFoundError("找不到 FFprobe。請先下載 FFmpeg。")

    def download_ffmpeg(self, progress_callback=None) -> bool:
        """
        下載並解壓縮 FFmpeg
        progress_callback: 接收一個參數，表示下載進度 (0~100) 的 int
        """
        if not os.path.exists(self.bin_dir):
            os.makedirs(self.bin_dir, exist_ok=True)

        temp_zip = os.path.join(self.bin_dir, "ffmpeg.zip")
        
        try:
            # 自訂 urllib 請求的下載進度顯示
            def reporthook(blocknum, blocksize, totalsize):
                if totalsize > 0 and progress_callback:
                    percent = int(blocknum * blocksize * 100 / totalsize)
                    # 限制在 0-100 之間，且最後由解壓縮程序控制進度
                    progress_callback(min(percent, 99))

            if progress_callback:
                progress_callback(1)

            # 下載 zip
            # 使用 urllib.request 來避免依賴額外的 requests 進度顯示複雜度
            urllib.request.urlretrieve(FFMPEG_ZIP_URL, temp_zip, reporthook)
            
            if progress_callback:
                progress_callback(99) # 下載完成，準備解壓

            # 解壓縮需要的 exe
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    filename = file_info.filename
                    # 我們只需要 ffmpeg.exe 與 ffprobe.exe
                    if filename.endswith("ffmpeg.exe") or filename.endswith("ffprobe.exe"):
                        # 去除層級目錄，直接把 exe 放到 bin_dir 底下
                        base_name = os.path.basename(filename)
                        target_path = os.path.join(self.bin_dir, base_name)
                        with zip_ref.open(file_info) as source, open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)

            # 刪除暫存 zip
            if os.path.exists(temp_zip):
                os.remove(temp_zip)

            if progress_callback:
                progress_callback(100)
            return True
            
        except Exception as e:
            print(f"下載或解壓縮 FFmpeg 失敗: {e}")
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            return False
