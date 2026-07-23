def get_stylesheet(theme="dark") -> str:
    """回傳現代 Windows 11 Fluent 風格的 QSS 樣式表"""
    if theme == "dark":
        return """
        /* 全域樣式 */
        QWidget {
            font-family: 'Segoe UI', 'Outfit', 'Microsoft JhengHei', sans-serif;
            font-size: 13px;
            color: #E3E3E3;
            background-color: #1E1E24;
        }

        /* 側邊導覽欄 */
        #Sidebar {
            background-color: #141417;
            border-right: 1px solid #2D2D37;
        }

        #Sidebar QPushButton {
            background-color: transparent;
            border: none;
            border-radius: 6px;
            padding: 10px 15px;
            text-align: left;
            font-weight: 500;
            color: #A0A0A5;
        }

        #Sidebar QPushButton:hover {
            background-color: #24242B;
            color: #FFFFFF;
        }

        #Sidebar QPushButton:checked {
            background-color: #0078D4;
            color: #FFFFFF;
            font-weight: bold;
        }

        /* 主工作面板 */
        #MainContent {
            background-color: #1E1E24;
        }

        /* 卡片/區塊容器 */
        .Card {
            background-color: #25252D;
            border: 1px solid #33333F;
            border-radius: 8px;
        }

        /* 拖放檔案區域 */
        #DropZone {
            background-color: #1C1C22;
            border: 2px dashed #0078D4;
            border-radius: 10px;
            padding: 30px;
        }

        #DropZone:hover {
            background-color: #24242E;
            border-color: #26A0FC;
        }

        /* 輸入框 */
        QLineEdit, QTextEdit, QComboBox {
            background-color: #25252D;
            border: 1px solid #3B3C4A;
            border-radius: 5px;
            padding: 6px 12px;
            color: #FFFFFF;
        }

        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border: 1px solid #0078D4;
            background-color: #2A2A35;
        }

        /* 按鈕 */
        QPushButton {
            background-color: #33333F;
            border: 1px solid #444452;
            border-radius: 5px;
            padding: 8px 16px;
            color: #FFFFFF;
            font-weight: 500;
        }

        QPushButton:hover {
            background-color: #3E3E4C;
            border-color: #555566;
        }

        QPushButton:pressed {
            background-color: #2A2A35;
        }

        /* 主動作按鈕 (Highlight) */
        QPushButton#PrimaryButton {
            background-color: #0078D4;
            border: 1px solid #006CC2;
            color: #FFFFFF;
        }

        QPushButton#PrimaryButton:hover {
            background-color: #1A85DF;
            border-color: #1A85DF;
        }

        QPushButton#PrimaryButton:pressed {
            background-color: #006CC2;
        }

        /* 標題與文字 */
        QLabel#Title {
            font-size: 20px;
            font-weight: bold;
            color: #FFFFFF;
        }

        QLabel#Subtitle {
            font-size: 13px;
            color: #8C8C9A;
        }

        /* 進度條 */
        QProgressBar {
            background-color: #2D2D37;
            border: none;
            border-radius: 4px;
            text-align: center;
            color: #FFFFFF;
            font-weight: bold;
        }

        QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078D4, stop:1 #26A0FC);
            border-radius: 4px;
        }

        /* 字幕編輯器表格 */
        QTableWidget {
            background-color: #202026;
            border: 1px solid #2D2D37;
            gridline-color: #2D2D37;
            border-radius: 6px;
            alternate-background-color: #25252C;
        }

        QTableWidget::item {
            padding: 8px;
            border-bottom: 1px solid #2D2D37;
        }

        QTableWidget::item:selected {
            background-color: #0078D4;
            color: #FFFFFF;
        }

        QTableWidget QLineEdit {
            padding: 2px 6px;
            margin: 0px;
            border: 1px solid #0078D4;
            background-color: #2A2A35;
            color: #FFFFFF;
            border-radius: 3px;
        }

        QHeaderView::section {
            background-color: #18181F;
            color: #A0A0A5;
            padding: 8px;
            border: none;
            border-bottom: 2px solid #2D2D37;
            font-weight: bold;
        }

        /* 捲軸 (Scrollbar) 美化 */
        QScrollBar:vertical {
            border: none;
            background: #18181F;
            width: 8px;
            margin: 0px;
        }

        QScrollBar::handle:vertical {
            background: #3B3C4A;
            min-height: 20px;
            border-radius: 4px;
        }

        QScrollBar::handle:vertical:hover {
            background: #505164;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        """
    else: # light theme
        return """
        /* 全域樣式 */
        QWidget {
            font-family: 'Segoe UI', 'Outfit', 'Microsoft JhengHei', sans-serif;
            font-size: 13px;
            color: #2B2B2B;
            background-color: #F3F3F3;
        }

        /* 側邊導覽欄 */
        #Sidebar {
            background-color: #EAEAEA;
            border-right: 1px solid #D1D1D1;
        }

        #Sidebar QPushButton {
            background-color: transparent;
            border: none;
            border-radius: 6px;
            padding: 10px 15px;
            text-align: left;
            font-weight: 500;
            color: #5F5F5F;
        }

        #Sidebar QPushButton:hover {
            background-color: #DFDFDF;
            color: #1A1A1A;
        }

        #Sidebar QPushButton:checked {
            background-color: #0078D4;
            color: #FFFFFF;
            font-weight: bold;
        }

        /* 主工作面板 */
        #MainContent {
            background-color: #F3F3F3;
        }

        /* 卡片/區塊容器 */
        .Card {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
        }

        /* 拖放檔案區域 */
        #DropZone {
            background-color: #FAFAFA;
            border: 2px dashed #0078D4;
            border-radius: 10px;
            padding: 30px;
        }

        #DropZone:hover {
            background-color: #F0F6FC;
            border-color: #1A85DF;
        }

        /* 輸入框 */
        QLineEdit, QTextEdit, QComboBox {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
            border-radius: 5px;
            padding: 6px 12px;
            color: #2B2B2B;
        }

        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border: 1px solid #0078D4;
            background-color: #FFFFFF;
        }

        /* 按鈕 */
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
            border-radius: 5px;
            padding: 8px 16px;
            color: #2B2B2B;
            font-weight: 500;
        }

        QPushButton:hover {
            background-color: #F7F7F7;
            border-color: #BBBBBB;
        }

        QPushButton:pressed {
            background-color: #EEEEEE;
        }

        /* 主動作按鈕 (Highlight) */
        QPushButton#PrimaryButton {
            background-color: #0078D4;
            border: 1px solid #006CC2;
            color: #FFFFFF;
        }

        QPushButton#PrimaryButton:hover {
            background-color: #1A85DF;
            border-color: #1A85DF;
        }

        QPushButton#PrimaryButton:pressed {
            background-color: #006CC2;
        }

        /* 標題與文字 */
        QLabel#Title {
            font-size: 20px;
            font-weight: bold;
            color: #1A1A1A;
        }

        QLabel#Subtitle {
            font-size: 13px;
            color: #666666;
        }

        /* 進度條 */
        QProgressBar {
            background-color: #E0E0E0;
            border: none;
            border-radius: 4px;
            text-align: center;
            color: #2B2B2B;
            font-weight: bold;
        }

        QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078D4, stop:1 #26A0FC);
            border-radius: 4px;
        }

        /* 字幕編輯器表格 */
        QTableWidget {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            gridline-color: #EAEAEA;
            border-radius: 6px;
            alternate-background-color: #FAFAFA;
        }

        QTableWidget::item {
            padding: 8px;
            border-bottom: 1px solid #EAEAEA;
        }

        QTableWidget::item:selected {
            background-color: #0078D4;
            color: #FFFFFF;
        }

        QTableWidget QLineEdit {
            padding: 2px 6px;
            margin: 0px;
            border: 1px solid #0078D4;
            background-color: #FFFFFF;
            color: #2B2B2B;
            border-radius: 3px;
        }

        QHeaderView::section {
            background-color: #F0F0F0;
            color: #555555;
            padding: 8px;
            border: none;
            border-bottom: 2px solid #E0E0E0;
            font-weight: bold;
        }

        /* 捲軸 (Scrollbar) 美化 */
        QScrollBar:vertical {
            border: none;
            background: #F0F0F0;
            width: 8px;
            margin: 0px;
        }

        QScrollBar::handle:vertical {
            background: #CCCCCC;
            min-height: 20px;
            border-radius: 4px;
        }

        QScrollBar::handle:vertical:hover {
            background: #AAAAAA;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        """
