from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QPushButton, QStackedWidget, QLabel, QFrame
)
from PySide6.QtCore import Qt
from core.config_manager import ConfigManager
from ui.styles import get_stylesheet
from ui.transcribe_panel import TranscribePanel
from ui.editor_panel import EditorPanel
from ui.settings_panel import SettingsPanel

class MainWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.setWindowTitle("Whisper 語音轉繁體中文字幕工具")
        self.resize(1050, 700)
        self.setMinimumSize(900, 600)
        
        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        # 主中央 Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 左側側邊導覽欄
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 30, 15, 30)
        sidebar_layout.setSpacing(10)

        # Logo / 標題
        logo_label = QLabel("🎯 SRT Subtitle")
        logo_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF; padding-bottom: 20px;")
        sidebar_layout.addWidget(logo_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 導覽按鈕
        self.btn_transcribe = QPushButton("📥 字幕轉譯")
        self.btn_transcribe.setCheckable(True)
        self.btn_transcribe.setChecked(True)
        
        self.btn_editor = QPushButton("✏️ 字幕編輯")
        self.btn_editor.setCheckable(True)
        
        self.btn_settings = QPushButton("⚙️ 系統設定")
        self.btn_settings.setCheckable(True)

        # 排列按鈕組 (以互斥選取實現 Tab 切換效果)
        self.nav_buttons = [self.btn_transcribe, self.btn_editor, self.btn_settings]
        for btn in self.nav_buttons:
            btn.clicked.connect(self.on_nav_clicked)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()
        
        # 版權/版本資訊
        footer_label = QLabel("© 2026 by Famidoc Chang & Antigravity")
        footer_label.setStyleSheet("color: #8C8C9A; font-size: 10px; padding-bottom: 2px;")
        footer_label.setWordWrap(True)
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(footer_label)

        ver_label = QLabel("v1.0.0 Stable")
        ver_label.setStyleSheet("color: #666677; font-size: 11px;")
        sidebar_layout.addWidget(ver_label, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(sidebar)

        # 2. 右側多頁切換區 (QStackedWidget)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("MainContent")

        # 實作三個分頁 Panel
        self.transcribe_panel = TranscribePanel(self.config_manager)
        self.editor_panel = EditorPanel(self.config_manager)
        self.settings_panel = SettingsPanel(self.config_manager)

        self.stacked_widget.addWidget(self.transcribe_panel)
        self.stacked_widget.addWidget(self.editor_panel)
        self.stacked_widget.addWidget(self.settings_panel)

        main_layout.addWidget(self.stacked_widget, stretch=1)

        # 3. 訊號與槽連線
        # 設定頁面主題切換
        self.settings_panel.theme_changed.connect(self.apply_theme)
        
        # 轉譯完成後自動跳轉到編輯分頁
        self.transcribe_panel.transcription_completed.connect(self.on_transcription_completed)

    def on_nav_clicked(self):
        sender = self.sender()
        for idx, btn in enumerate(self.nav_buttons):
            if btn == sender:
                btn.setChecked(True)
                self.stacked_widget.setCurrentIndex(idx)
            else:
                btn.setChecked(False)

    def on_transcription_completed(self, items: list, media_file: str):
        # 載入字幕至編輯器中
        self.editor_panel.set_subtitles(items, media_file)
        
        # UI 跳轉到字幕編輯分頁 (Index = 1)
        for idx, btn in enumerate(self.nav_buttons):
            btn.setChecked(idx == 1)
        self.stacked_widget.setCurrentIndex(1)

    def apply_theme(self, theme=None):
        if theme is None:
            theme = self.config_manager.get("theme", "dark")
            
        stylesheet = get_stylesheet(theme)
        self.setStyleSheet(stylesheet)
        
        # 額外美化側邊欄 Logo 文字顏色
        if theme == "dark":
            self.findChild(QLabel, "").setStyleSheet("") # 清空預設，套用 QSS
        else:
            # 亮色主題下，讓 sidebar 文字也是深色的
            pass

    def closeEvent(self, event):
        # 通知各面板釋放資源 (特別是 editor_panel 播放器釋放臨時音訊)
        self.editor_panel.stop_play()
        self.transcribe_panel.cancel_process()
        
        # 主動關閉
        self.editor_panel.close()
        self.transcribe_panel.close()
        event.accept()
