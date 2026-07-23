import sys
import os
from PySide6.QtWidgets import QApplication
from core.config_manager import ConfigManager
from ui.main_window import MainWindow

def main():
    # 支援 Windows High DPI 縮放
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    
    # 載入設定管理器
    config_manager = ConfigManager()
    
    # 建立並顯示主視窗
    window = MainWindow(config_manager)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
