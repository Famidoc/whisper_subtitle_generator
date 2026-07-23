import os
import sys
import subprocess
import shutil

def build():
    print("=== Starting build for Whisper Subtitle Generator (.exe) ===")
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(project_dir, "dist")
    
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
    main_py = os.path.join(project_dir, "main.py")
    app_name = "WhisperSubtitleGenerator"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name", app_name,
        "--add-data", f"{os.path.join(project_dir, 'core')}{os.path.pathsep}core",
        "--add-data", f"{os.path.join(project_dir, 'ui')}{os.path.pathsep}ui",
        "--collect-all", "PySide6",
        "--collect-all", "faster_whisper",
        "--hidden-import", "openai",
        "--hidden-import", "google.generativeai",
        "--hidden-import", "opencc",
        "--hidden-import", "cryptography",
        main_py
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    output_path = os.path.join(dist_dir, app_name)
    print(f"=== Build finished! Executable located at: {output_path} ===")

if __name__ == "__main__":
    build()
