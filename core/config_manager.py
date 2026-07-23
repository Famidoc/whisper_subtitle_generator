import os
import json
import base64

# 使用簡單的 XOR/Base64 來混淆 API Key，防止明文暴露在設定檔中
OBFUSCATION_KEY = b"whisper_subtitle_sec_key"

def _obfuscate(text: str) -> str:
    if not text:
        return ""
    try:
        # 簡單混淆
        enc = []
        for i in range(len(text)):
            key_c = OBFUSCATION_KEY[i % len(OBFUSCATION_KEY)]
            enc_c = chr((ord(text[i]) + key_c) % 256)
            enc.append(enc_c)
        return base64.urlsafe_b64encode("".join(enc).encode('latin-1')).decode('utf-8')
    except Exception:
        return ""

def _deobfuscate(obfuscated_text: str) -> str:
    if not obfuscated_text:
        return ""
    try:
        dec = base64.urlsafe_b64decode(obfuscated_text.encode('utf-8')).decode('latin-1')
        text = []
        for i in range(len(dec)):
            key_c = OBFUSCATION_KEY[i % len(OBFUSCATION_KEY)]
            dec_c = chr((ord(dec[i]) - key_c) % 256)
            text.append(dec_c)
        return "".join(text)
    except Exception:
        return ""

class ConfigManager:
    DEFAULT_CONFIG = {
        "whisper_mode": "local",
        "local_model_size": "base",
        "openai_api_key": "",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "use_llm_refine": False,
        "llm_provider": "gemini",
        "theme": "dark",
        "export_dir": "",
        "max_line_length": 18,
        "enable_auto_split": True
    }

    def __init__(self, config_path="config.json"):
        # 取得程式所在目錄下的 config.json
        if os.path.isabs(config_path):
            self.config_path = config_path
        else:
            self.config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config_path)
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 更新設定值
                    for k, v in data.items():
                        if k in self.config:
                            self.config[k] = v
                
                # 解密敏感資訊
                if self.config["openai_api_key"]:
                    self.config["openai_api_key"] = _deobfuscate(self.config["openai_api_key"])
                if self.config["gemini_api_key"]:
                    self.config["gemini_api_key"] = _deobfuscate(self.config["gemini_api_key"])
            except Exception as e:
                print(f"讀取設定檔失敗: {e}")
                self.config = self.DEFAULT_CONFIG.copy()

    def save(self):
        try:
            # 複製一份以進行加密
            save_data = self.config.copy()
            if save_data["openai_api_key"]:
                save_data["openai_api_key"] = _obfuscate(save_data["openai_api_key"])
            if save_data["gemini_api_key"]:
                save_data["gemini_api_key"] = _obfuscate(save_data["gemini_api_key"])
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def get_all(self):
        return self.config.copy()

    def set(self, key, value):
        if key in self.config:
            self.config[key] = value
            self.save()
