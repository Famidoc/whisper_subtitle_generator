from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QComboBox, QPushButton, QCheckBox, QFileDialog, QFormLayout,
    QSpinBox
)
from PySide6.QtCore import Signal
from core.config_manager import ConfigManager

class SettingsPanel(QWidget):
    # 訊號：當主題切換時通知主視窗更新
    theme_changed = Signal(str)

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.init_ui()

    def init_ui(self):
        # 主佈局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 標題
        title_label = QLabel("系統設定")
        title_label.setObjectName("Title")
        subtitle_label = QLabel("配置語音辨識、AI 潤飾金鑰與外觀偏好")
        subtitle_label.setObjectName("Subtitle")
        
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        # 設定表單容器 (以 Card 樣式包覆)
        card = QWidget()
        card.setObjectName("SettingCard")
        card.setProperty("class", "Card")
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(15)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # 1. 預設轉譯模式
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["本地免費辨識 (faster-whisper)", "雲端 API 辨識 (OpenAI Whisper)"])
        # 對應到 config 裡的 "local" 與 "api"
        current_mode = self.config_manager.get("whisper_mode", "local")
        self.mode_combo.setCurrentIndex(0 if current_mode == "local" else 1)
        form_layout.addRow(QLabel("語音辨識模式："), self.mode_combo)

        # 2. 本地模型大小
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny (快、體積小 ~75MB)", "base (平衡、~140MB)", "small (較準確、~460MB)", "medium (極準確、~1.5GB)"])
        model_map = ["tiny", "base", "small", "medium"]
        current_model = self.config_manager.get("local_model_size", "base")
        try:
            self.model_combo.setCurrentIndex(model_map.index(current_model))
        except ValueError:
            self.model_combo.setCurrentIndex(1)
        form_layout.addRow(QLabel("本地 Whisper 模型："), self.model_combo)

        # 3. OpenAI API 金鑰
        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_input.setPlaceholderText("輸入 OpenAI API Key (sk-...)")
        self.openai_key_input.setText(self.config_manager.get("openai_api_key", ""))
        
        # 顯示/隱藏按鈕
        self.show_openai_btn = QPushButton("顯示")
        self.show_openai_btn.setFixedWidth(50)
        self.show_openai_btn.clicked.connect(lambda: self.toggle_password_visibility(self.openai_key_input, self.show_openai_btn))
        
        openai_layout = QHBoxLayout()
        openai_layout.addWidget(self.openai_key_input)
        openai_layout.addWidget(self.show_openai_btn)
        form_layout.addRow(QLabel("OpenAI API 金鑰："), openai_layout)

        # 4. Gemini API 金鑰
        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_input.setPlaceholderText("輸入 Gemini API Key")
        self.gemini_key_input.setText(self.config_manager.get("gemini_api_key", ""))
        
        self.show_gemini_btn = QPushButton("顯示")
        self.show_gemini_btn.setFixedWidth(50)
        self.show_gemini_btn.clicked.connect(lambda: self.toggle_password_visibility(self.gemini_key_input, self.show_gemini_btn))
        
        gemini_layout = QHBoxLayout()
        gemini_layout.addWidget(self.gemini_key_input)
        gemini_layout.addWidget(self.show_gemini_btn)
        form_layout.addRow(QLabel("Gemini API 金鑰："), gemini_layout)

        # 5. 是否啟用 LLM 潤飾
        self.use_llm_check = QCheckBox("啟用 AI 字幕優化與潤飾（二次校對）")
        self.use_llm_check.setChecked(self.config_manager.get("use_llm_refine", False))
        form_layout.addRow(QLabel("AI 潤飾設定："), self.use_llm_check)

        # 6. LLM 服務商
        self.llm_combo = QComboBox()
        self.llm_combo.addItems(["Gemini (推薦、速度快)", "OpenAI GPT-4o-mini"])
        current_llm = self.config_manager.get("llm_provider", "gemini")
        self.llm_combo.setCurrentIndex(0 if current_llm == "gemini" else 1)
        form_layout.addRow(QLabel("AI 潤飾模型："), self.llm_combo)

        # 7. 主題設定
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色主題 (Dark Theme)", "淺色主題 (Light Theme)"])
        current_theme = self.config_manager.get("theme", "dark")
        self.theme_combo.setCurrentIndex(0 if current_theme == "dark" else 1)
        form_layout.addRow(QLabel("外觀主題："), self.theme_combo)

        # 7.5 字幕自動切分設定
        self.auto_split_check = QCheckBox("啟用過長字幕自動切分")
        self.auto_split_check.setChecked(self.config_manager.get("enable_auto_split", True))
        form_layout.addRow(QLabel("自動切分長字幕："), self.auto_split_check)

        self.max_len_spin = QSpinBox()
        self.max_len_spin.setRange(5, 100)
        self.max_len_spin.setValue(self.config_manager.get("max_line_length", 18))
        self.max_len_spin.setSuffix(" 字")
        form_layout.addRow(QLabel("單行最大字數："), self.max_len_spin)

        # 8. 預設匯出路徑
        self.export_input = QLineEdit()
        self.export_input.setPlaceholderText("留空則預設存放在影音檔案同目錄下")
        self.export_input.setText(self.config_manager.get("export_dir", ""))
        self.browse_btn = QPushButton("瀏覽")
        self.browse_btn.clicked.connect(self.browse_export_dir)
        
        export_layout = QHBoxLayout()
        export_layout.addWidget(self.export_input)
        export_layout.addWidget(self.browse_btn)
        form_layout.addRow(QLabel("預設字幕匯出目錄："), export_layout)

        card_layout.addLayout(form_layout)
        layout.addWidget(card)

        # 按鈕列
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("儲存設定")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()

    def toggle_password_visibility(self, line_edit: QLineEdit, button: QPushButton):
        if line_edit.echoMode() == QLineEdit.EchoMode.Password:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            button.setText("隱藏")
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            button.setText("顯示")

    def browse_export_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "選擇預設匯出目錄")
        if dir_path:
            self.export_input.setText(dir_path)

    def save_settings(self):
        # 讀取 UI 值
        whisper_mode = "local" if self.mode_combo.currentIndex() == 0 else "api"
        
        model_map = ["tiny", "base", "small", "medium"]
        local_model_size = model_map[self.model_combo.currentIndex()]
        
        openai_api_key = self.openai_key_input.text().strip()
        gemini_api_key = self.gemini_key_input.text().strip()
        use_llm_refine = self.use_llm_check.isChecked()
        llm_provider = "gemini" if self.llm_combo.currentIndex() == 0 else "openai"
        theme = "dark" if self.theme_combo.currentIndex() == 0 else "light"
        export_dir = self.export_input.text().strip()
        enable_auto_split = self.auto_split_check.isChecked()
        max_line_length = self.max_len_spin.value()

        # 儲存到 config
        self.config_manager.set("whisper_mode", whisper_mode)
        self.config_manager.set("local_model_size", local_model_size)
        self.config_manager.set("openai_api_key", openai_api_key)
        self.config_manager.set("gemini_api_key", gemini_api_key)
        self.config_manager.set("use_llm_refine", use_llm_refine)
        self.config_manager.set("llm_provider", llm_provider)
        self.config_manager.set("theme", theme)
        self.config_manager.set("export_dir", export_dir)
        self.config_manager.set("enable_auto_split", enable_auto_split)
        self.config_manager.set("max_line_length", max_line_length)

        # 觸發主題變更訊號
        self.theme_changed.emit(theme)
        
        # 簡單提示儲存成功
        self.save_btn.setText("設定已儲存！")
        self.save_btn.setEnabled(False)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: (self.save_btn.setText("儲存設定"), self.save_btn.setEnabled(True)))
