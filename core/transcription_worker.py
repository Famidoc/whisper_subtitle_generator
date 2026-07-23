import os
from PySide6.QtCore import QThread, Signal
from core.subtitle_parser import SubtitleItem, SubtitleParser
from core.subtitle_splitter import SubtitleSplitter

class TranscriptionWorker(QThread):
    # 定義訊號
    progress_changed = Signal(int)       # 進度百分比 (0~100)
    status_changed = Signal(str)         # 當前狀態文字
    finished_transcription = Signal(list) # 轉譯完成，傳回 SubtitleItem 串列
    error_occurred = Signal(str)         # 錯誤訊息

    def __init__(self, audio_path: str, config: dict):
        super().__init__()
        self.audio_path = audio_path
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            self.status_changed.emit("正在準備音訊檔...")
            self.progress_changed.emit(5)
            
            if self._is_cancelled:
                return

            whisper_mode = self.config.get("whisper_mode", "local")
            
            if whisper_mode == "local":
                self.run_local_transcription()
            else:
                self.run_api_transcription()

        except Exception as e:
            if self._is_cancelled:
                self.status_changed.emit("已取消轉譯。")
            else:
                self.error_occurred.emit(str(e))

    def run_local_transcription(self):
        self.status_changed.emit("正在載入本地 Whisper 模型 (首次需下載)...")
        self.progress_changed.emit(10)

        # 動態載入 faster_whisper，以利在未安裝時不會導致主程式直接崩潰
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError("未安裝 faster-whisper 套件，請執行 pip install faster-whisper")

        model_size = self.config.get("local_model_size", "base")
        
        # 偵測是否可使用 CUDA 加速
        device = "cpu"
        compute_type = "int8"
        
        # 嘗試使用 CUDA，若失敗則退回 CPU
        try:
            # 這裡只做極簡的 CUDA 偵測
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
                self.status_changed.emit("檢測到 NVIDIA 顯示卡，已啟用 CUDA 加速模式！")
        except Exception:
            pass
            
        try:
            self.status_changed.emit(f"正在初始化 Whisper 模型 ({model_size}，裝置: {device})...")
            # 初始化模型，若需要下載，faster-whisper 會自動將進度印在 stderr 中
            # 為了下載時不會凍結，我們可以透過指定 download_root 來確認
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as e:
            if device == "cuda":
                # CUDA 初始化失敗，嘗試退回 CPU 模式
                self.status_changed.emit("CUDA 啟動失敗，正在嘗試切換至 CPU 模式...")
                model = WhisperModel(model_size, device="cpu", compute_type="int8")
            else:
                raise e

        if self._is_cancelled:
            return

        self.status_changed.emit("模型初始化成功，開始辨識語音...")
        self.progress_changed.emit(20)

        # 執行語音辨識
        # initial_prompt: 提示 Whisper 繁體中文，改善中文語音轉繁體中文效果
        segments, info = model.transcribe(
            self.audio_path,
            beam_size=5,
            initial_prompt="以下是繁體中文字幕：",
            language="zh" # 鎖定中文，減少語言飄移
        )

        total_duration = info.duration
        raw_items = []
        index = 1

        # 疊代 segments，獲取時間與文字
        for segment in segments:
            if self._is_cancelled:
                return
                
            raw_items.append(SubtitleItem(
                index=index,
                start=segment.start,
                end=segment.end,
                text=segment.text
            ))
            index += 1

            # 計算進度 (從 20% 到 90% 區間)
            if total_duration > 0:
                percent = 20 + int((segment.end / total_duration) * 70)
                self.progress_changed.emit(min(percent, 90))
                self.status_changed.emit(f"正在轉譯語音: {int(segment.end)}秒 / {int(total_duration)}秒")

        # 轉譯完成，進行簡轉繁
        self.status_changed.emit("語音辨識完成，正在進行繁體中文轉換...")
        self.progress_changed.emit(92)
        
        traditional_items = self.convert_to_traditional(raw_items)
        
        # 自動切分長字幕
        self.progress_changed.emit(96)
        final_items = self.apply_auto_split(traditional_items)
        
        self.progress_changed.emit(100)
        self.status_changed.emit("轉譯成功！")
        self.finished_transcription.emit(final_items)

    def run_api_transcription(self):
        api_key = self.config.get("openai_api_key", "")
        if not api_key:
            raise ValueError("請先在設定中配置 OpenAI API Key")

        self.status_changed.emit("正在呼叫 OpenAI API 轉譯...")
        self.progress_changed.emit(30)

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("未安裝 openai 套件，請執行 pip install openai")

        client = OpenAI(api_key=api_key)
        
        if self._is_cancelled:
            return

        # 雲端 Whisper 1 只能處理小於 25MB 的檔案
        # 如果音訊檔案太大，需要在此處提醒或切片。但一般 16kHz WAV 壓縮後通常不大，
        # 如果長度真的很長，我們可以提醒使用者。
        # 呼叫 API 進行轉譯
        with open(self.audio_path, "rb") as audio_file:
            transcript_srt = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="srt",
                prompt="繁體中文，台灣習慣用語。",
                language="zh"
            )

        if self._is_cancelled:
            return

        self.status_changed.emit("API 辨識成功，解析字幕格式並進行簡轉繁...")
        self.progress_changed.emit(85)

        # 解析 API 回傳的 SRT
        raw_items = SubtitleParser.parse_srt(transcript_srt)
        
        # 進行簡轉繁
        traditional_items = self.convert_to_traditional(raw_items)

        # 自動切分長字幕
        final_items = self.apply_auto_split(traditional_items)

        self.progress_changed.emit(100)
        self.status_changed.emit("轉譯成功！")
        self.finished_transcription.emit(final_items)

    def convert_to_traditional(self, items: list[SubtitleItem]) -> list[SubtitleItem]:
        """使用 opencc 將字幕轉成繁體中文 (台灣習慣用語)"""
        try:
            from opencc import OpenCC
            cc = OpenCC('s2twp') # 簡體到台灣正體並進行習慣詞彙轉換
        except ImportError:
            # Fallback，若 opencc 安裝失敗則不做轉換
            return items

        for item in items:
            item.text = cc.convert(item.text)
        return items

    def apply_auto_split(self, items: list[SubtitleItem]) -> list[SubtitleItem]:
        """自動切分過長的字幕"""
        enable_split = self.config.get("enable_auto_split", True)
        if enable_split:
            max_len = self.config.get("max_line_length", 18)
            self.status_changed.emit("正在自動切分過長的字幕...")
            return SubtitleSplitter.split_subtitles(items, max_len)
        return items
