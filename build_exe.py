import os
import sys
import subprocess
import shutil

def build():
    print("🚀 開始為 Whisper Subtitle Generator 打包免安裝檔 (.exe)...")
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(project_dir, "dist")
    build_dir = os.path.join(project_dir, "build")
    
    # 確保 PyInstaller 已安裝
    try:
        import PyInstaller
    except ImportError:
        print("📦 正在安裝 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
    main_py = os.path.join(project_dir, "main.py")
    app_name = "WhisperSubtitleGenerator"
    
    # PyInstaller 參數配置
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",  # 打包為資料夾模式以提供最佳相容性與啟動速度
        "--windowed", # GUI 視窗模式，隱藏主控台
        "--name", app_name,
        "--add-data", f"{os.path.join(project_dir, 'core')}{os.path.pathsep}core",
        "--add-data", f"{os.path.join(project_dir, 'ui')}{os.path.pathsep}ui",
        "--hidden-import", "PySide6",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "PySide6.QtMultimedia",
        "--hidden-import", "faster_whisper",
        "--hidden-import", "openai",
        "--hidden-import", "google.generativeai",
        "--hidden-import", "opencc",
        "--hidden-import", "cryptography",
        main_py
    ]
    
    print(f"🔧 執行指令: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    output_path = os.path.join(dist_dir, app_name)
    print(f"\n✅ 打包完成！免安裝檔案發布於：\n{output_path}")

if __name__ == "__main__":
    build()
