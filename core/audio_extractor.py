import os
import subprocess
import tempfile
from core.ffmpeg_helper import FFmpegHelper

class AudioExtractor:
    def __init__(self, ffmpeg_helper: FFmpegHelper = None):
        self.ffmpeg_helper = ffmpeg_helper if ffmpeg_helper else FFmpegHelper()

    def extract_audio(self, input_filepath: str) -> str:
        """
        使用 ffmpeg 將輸入影音檔的音軌轉為 16kHz, 單聲道, 16bit PCM WAV 檔。
        回傳轉碼後的 WAV 暫存檔案路徑。
        """
        if not self.ffmpeg_helper.is_available():
            raise FileNotFoundError("FFmpeg 尚未安裝，無法提取音訊。")

        ffmpeg_cmd = self.ffmpeg_helper.get_ffmpeg_cmd()
        
        # 建立系統暫存目錄中的目標 WAV 檔名
        temp_dir = tempfile.gettempdir()
        file_basename = os.path.splitext(os.path.basename(input_filepath))[0]
        output_wav_path = os.path.join(temp_dir, f"{file_basename}_temp_16k.wav")

        # ffmpeg 轉碼指令：
        # -y: 強制覆寫
        # -i: 輸入檔案
        # -ar 16000: 採樣率 16kHz
        # -ac 1: 單聲道
        # -acodec pcm_s16le: 16bit PCM 格式
        cmd = [
            ffmpeg_cmd,
            "-y",
            "-i", input_filepath,
            "-ar", "16000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            output_wav_path
        ]

        try:
            # 隱藏 CMD 視窗 (適用於 Windows)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # 執行轉碼
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                check=True
            )
            return output_wav_path
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode('utf-8', errors='ignore')
            raise RuntimeError(f"音訊提取失敗: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"執行 FFmpeg 時發生錯誤: {e}")

    def clean_temp_audio(self, temp_wav_path: str):
        """清除轉譯產生的暫存 WAV 檔"""
        if temp_wav_path and os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except Exception as e:
                print(f"無法刪除暫存檔 {temp_wav_path}: {e}")
