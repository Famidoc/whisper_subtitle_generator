import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, Qt, QThread
from core.config_manager import ConfigManager
from core.ffmpeg_helper import FFmpegHelper
from core.audio_extractor import AudioExtractor
from core.transcription_worker import TranscriptionWorker
from core.llm_refiner import LLMRefinerWorker

class FFmpegDownloadWorker(QThread):
    progress = Signal(int)
    finished = Signal(bool)

    def __init__(self, helper: FFmpegHelper):
        super().__init__()
        self.helper = helper

    def run(self):
        success = self.helper.download_ffmpeg(progress_callback=self.progress.emit)
        self.finished.emit(success)

class TranscribePanel(QWidget):
    # 轉譯與優化完成訊號：(字幕清單, 原始影音檔案路徑)
    transcription_completed = Signal(list, str)

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.ffmpeg_helper = FFmpegHelper()
        self.selected_file = ""
        
        self.ffmpeg_worker = None
        self.transcribe_worker = None
        self.llm_worker = None
        self.temp_wav_path = ""
        
        self.init_ui()
        self.setAcceptDrops(True)

    def init_ui(self):
        # 主佈局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # 標題
        title_label = QLabel("字幕轉譯")
        title_label.setObjectName("Title")
        subtitle_label = QLabel("請將 MP4 影片或 MP3 語音檔拖曳至下方，或點擊按鈕選取檔案")
        subtitle_label.setObjectName("Subtitle")
        
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        # 拖放卡片區
        self.drop_zone = QWidget()
        self.drop_zone.setObjectName("DropZone")
        
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.setSpacing(15)
        
        self.drop_icon_label = QLabel("📥")
        self.drop_icon_label.setStyleSheet("font-size: 48px;")
        self.drop_text_label = QLabel("拖曳檔案到此處，或")
        self.drop_text_label.setStyleSheet("font-size: 15px; font-weight: 500;")
        
        self.select_btn = QPushButton("選擇影音檔案")
        self.select_btn.setObjectName("PrimaryButton")
        self.select_btn.clicked.connect(self.select_file)
        
        drop_layout.addWidget(self.drop_icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.drop_text_label, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.select_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.drop_zone, stretch=2)

        # 檔案資訊顯示區
        self.info_card = QWidget()
        self.info_card.setProperty("class", "Card")
        self.info_card.hide()
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(15, 15, 15, 15)
        
        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(self.file_info_label)
        
        layout.addWidget(self.info_card)

        # 轉譯與進度控制區
        self.control_layout = QVBoxLayout()
        self.control_layout.setSpacing(10)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #0078D4; font-weight: 500;")
        self.control_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        self.control_layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("開始轉譯字幕")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_process)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self.cancel_process)
        
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        self.control_layout.addLayout(btn_row)
        
        layout.addLayout(self.control_layout)
        layout.addStretch()

    # 拖放處理
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                # 支援常見影音格式
                ext = os.path.splitext(file_path)[1].lower()
                if ext in [".mp4", ".mp3", ".wav", ".m4a", ".mkv", ".mov", ".flac", ".aac"]:
                    self.set_selected_file(file_path)
                    break
                else:
                    QMessageBox.warning(self, "格式不支援", f"不支援的檔案格式：{ext}\n請載入常見的影片或音訊檔。")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "選擇影音檔案", "", 
            "影音檔案 (*.mp4 *.mp3 *.wav *.m4a *.mkv *.mov *.flac *.aac);;所有檔案 (*.*)"
        )
        if file_path:
            self.set_selected_file(file_path)

    def set_selected_file(self, filepath: str):
        self.selected_file = filepath
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        
        # UI 更新
        self.file_info_label.setText(
            f"📄 已選取檔案：{os.path.basename(filepath)}\n"
            f"📂 路徑：{filepath}\n"
            f"💾 大小：{file_size_mb:.2f} MB"
        )
        self.info_card.show()
        self.start_btn.setEnabled(True)
        self.status_label.setText("準備就緒。點擊「開始轉譯字幕」按鈕開始處理。")

    def start_process(self):
        # 1. 檢查 FFmpeg
        if not self.ffmpeg_helper.is_available():
            reply = QMessageBox.question(
                self, "需要 FFmpeg", 
                "偵測到系統未安裝 FFmpeg（用於音訊分離與格式轉換）。\n程式將自動為您背景下載並配置 Windows 靜態版 FFmpeg (約 70~100MB)，是否繼續？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.download_ffmpeg_process()
            return
        
        # 2. 啟動音訊提取與辨識流程
        self.run_transcription_pipeline()

    def download_ffmpeg_process(self):
        self.start_btn.setEnabled(False)
        self.cancel_btn.show()
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_label.setText("正在背景下載 FFmpeg Essentials 套件...")

        self.ffmpeg_worker = FFmpegDownloadWorker(self.ffmpeg_helper)
        self.ffmpeg_worker.progress.connect(self.progress_bar.setValue)
        self.ffmpeg_worker.finished.connect(self.on_ffmpeg_download_finished)
        self.ffmpeg_worker.start()

    def on_ffmpeg_download_finished(self, success: bool):
        self.progress_bar.hide()
        self.cancel_btn.hide()
        self.start_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "配置成功", "FFmpeg 配置完成！請再次點擊「開始轉譯字幕」以開始辨識。")
            self.status_changed_ui("FFmpeg 安裝成功！", False)
        else:
            QMessageBox.critical(self, "下載失敗", "FFmpeg 下載失敗，請檢查網路連線或稍後再試。")
            self.status_changed_ui("FFmpeg 下載失敗，請重試或手動配置。", False)

    def run_transcription_pipeline(self):
        self.status_changed_ui("正在提取音訊軌...", True)
        self.progress_bar.setValue(5)
        
        # 提取音軌到 WAV (耗時極短，可同步執行，或若有延遲，可放入 Thread，但一般極快)
        try:
            extractor = AudioExtractor(self.ffmpeg_helper)
            self.temp_wav_path = extractor.extract_audio(self.selected_file)
        except Exception as e:
            QMessageBox.critical(self, "音訊提取出錯", f"無法提取音訊：\n{e}")
            self.status_changed_ui("音訊提取失敗。", False)
            return

        # 啟動辨識線程
        self.transcribe_worker = TranscriptionWorker(self.temp_wav_path, self.config_manager.config)
        self.transcribe_worker.progress_changed.connect(self.progress_bar.setValue)
        self.transcribe_worker.status_changed.connect(self.status_label.setText)
        self.transcribe_worker.finished_transcription.connect(self.on_transcription_finished)
        self.transcribe_worker.error_occurred.connect(self.on_process_error)
        self.transcribe_worker.start()

    def on_transcription_finished(self, items: list):
        # 刪除辨識用的暫存 WAV 檔
        extractor = AudioExtractor(self.ffmpeg_helper)
        extractor.clean_temp_audio(self.temp_wav_path)
        self.temp_wav_path = ""

        # 檢查是否需要 LLM 潤飾
        if self.config_manager.get("use_llm_refine", False):
            self.run_llm_refinement(items)
        else:
            self.status_changed_ui("轉譯完成！", False)
            # 發送成功訊號，傳遞字幕與影音檔案
            self.transcription_completed.emit(items, self.selected_file)

    def run_llm_refinement(self, items: list):
        self.status_changed_ui("轉譯完成，正在啟動 AI 潤飾...", True)
        self.progress_bar.setValue(5)

        self.llm_worker = LLMRefinerWorker(items, self.config_manager.config)
        self.llm_worker.progress_changed.connect(self.progress_bar.setValue)
        self.llm_worker.status_changed.connect(self.status_label.setText)
        self.llm_worker.finished_refining.connect(self.on_llm_refinement_finished)
        self.llm_worker.error_occurred.connect(self.on_process_error)
        self.llm_worker.start()

    def on_llm_refinement_finished(self, refined_items: list):
        self.status_changed_ui("AI 潤飾完成！", False)
        self.transcription_completed.emit(refined_items, self.selected_file)

    def on_process_error(self, error_msg: str):
        # 清理暫存音訊
        if self.temp_wav_path:
            extractor = AudioExtractor(self.ffmpeg_helper)
            extractor.clean_temp_audio(self.temp_wav_path)
            self.temp_wav_path = ""

        QMessageBox.critical(self, "處理過程出錯", f"發生錯誤：\n{error_msg}")
        self.status_changed_ui(f"執行出錯：{error_msg}", False)

    def cancel_process(self):
        if self.ffmpeg_worker and self.ffmpeg_worker.isRunning():
            self.ffmpeg_worker.terminate()
            self.ffmpeg_worker.wait()
            self.status_changed_ui("已取消 FFmpeg 下載。", False)
            
        if self.transcribe_worker and self.transcribe_worker.isRunning():
            self.transcribe_worker.cancel()
            self.transcribe_worker.wait()
            self.status_changed_ui("已取消語音轉譯。", False)

        if self.llm_worker and self.llm_worker.isRunning():
            self.llm_worker.cancel()
            self.llm_worker.wait()
            self.status_changed_ui("已取消 AI 潤飾。", False)

    def status_changed_ui(self, msg: str, is_running: bool):
        self.status_label.setText(msg)
        if is_running:
            self.start_btn.setEnabled(False)
            self.select_btn.setEnabled(False)
            self.drop_zone.setAcceptDrops(False)
            self.cancel_btn.show()
            self.progress_bar.show()
        else:
            self.start_btn.setEnabled(True if self.selected_file else False)
            self.select_btn.setEnabled(True)
            self.drop_zone.setAcceptDrops(True)
            self.cancel_btn.hide()
            self.progress_bar.hide()
