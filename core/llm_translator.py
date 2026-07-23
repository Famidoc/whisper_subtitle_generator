import json
import time
from PySide6.QtCore import QThread, Signal
from core.subtitle_parser import SubtitleItem

class LLMTranslatorWorker(QThread):
    progress_changed = Signal(int)
    status_changed = Signal(str)
    finished_translating = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, items: list[SubtitleItem], target_lang: str, config: dict):
        super().__init__()
        self.items = items
        self.target_lang = target_lang
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            self.status_changed.emit(f"正在準備字幕進行 AI 翻譯 ({self.target_lang})...")
            self.progress_changed.emit(5)
            
            provider = self.config.get("llm_provider", "gemini")
            chunk_size = 40
            chunks = [self.items[i:i + chunk_size] for i in range(0, len(self.items), chunk_size)]
            
            translated_items = []
            
            for idx, chunk in enumerate(chunks):
                if self._is_cancelled:
                    return
                
                if idx > 0:
                    time.sleep(1.5)
                
                self.status_changed.emit(f"AI 正在翻譯中 [{self.target_lang}] (批次 {idx+1}/{len(chunks)})...")
                payload = [{"id": item.index, "text": item.text} for item in chunk]
                
                translated_data = self.call_llm_api_with_retry(provider, payload)
                
                if self._is_cancelled:
                    return

                translated_dict = {d["id"]: d["translation"] for d in translated_data if "id" in d and "translation" in d}
                
                for item in chunk:
                    trans_text = translated_dict.get(item.index, "")
                    new_item = SubtitleItem(
                        index=item.index,
                        start=item.start,
                        end=item.end,
                        text=item.text,
                        translation=trans_text
                    )
                    translated_items.append(new_item)
                
                percent = 5 + int(((idx + 1) / len(chunks)) * 90)
                self.progress_changed.emit(min(percent, 95))
            
            self.progress_changed.emit(100)
            self.status_changed.emit("AI 字幕翻譯完成！")
            self.finished_translating.emit(translated_items)
            
        except Exception as e:
            if self._is_cancelled:
                self.status_changed.emit("已取消 AI 翻譯。")
            else:
                self.error_occurred.emit(str(e))

    def call_llm_api_with_retry(self, provider: str, payload: list) -> list:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.call_llm_api(provider, payload)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        self.status_changed.emit(f"觸發 API 頻率限制，等待 {wait_time} 秒後重試...")
                        time.sleep(wait_time)
                        continue
                raise e

    def call_llm_api(self, provider: str, payload: list) -> list:
        prompt = (
            f"你是一個專業的字幕翻譯專家。請將以下 JSON 陣列中的字幕內文精確翻譯為「{self.target_lang}」。\n"
            "翻譯原則：\n"
            "1. 語意精準、通順且符合該語言自然口語習慣。\n"
            "2. 嚴格保持每一條 id 對應，絕對不可合併、刪除或新增條目。\n"
            "3. 不要包含任何 Markdown 格式包裝（如 ```json），請直接回傳合法的 JSON 陣列：\n"
            "[{\"id\": 1, \"translation\": \"翻譯後的文字\"}]\n"
            "4. 注意：回傳的 Key 必須為 \"translation\"。"
        )
        
        system_instruction = "你是一個只會輸出合法 JSON 格式的專業字幕翻譯助手。"

        if provider == "gemini":
            api_key = self.config.get("gemini_api_key", "")
            if not api_key:
                raise ValueError("請先在設定中配置 Gemini API Key")
                
            try:
                import google.generativeai as genai
            except ImportError:
                raise ImportError("未安裝 google-generativeai 套件，請執行 pip install google-generativeai")
                
            genai.configure(api_key=api_key)
            model_name = self.config.get("gemini_model", "gemini-2.5-flash")
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"},
                system_instruction=system_instruction
            )
            
            contents = f"{prompt}\n\n待翻譯字幕資料：\n{json.dumps(payload, ensure_ascii=False)}"
            response = model.generate_content(contents)
            
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                text_clean = response.text.replace("```json", "").replace("```", "").strip()
                return json.loads(text_clean)
                
        else: # openai
            api_key = self.config.get("openai_api_key", "")
            if not api_key:
                raise ValueError("請先在設定中配置 OpenAI API Key")
                
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError("未安裝 openai 套件，請執行 pip install openai")
                
            client = OpenAI(api_key=api_key)
            user_content = f"{prompt}\n\n待翻譯字幕資料：\n{json.dumps(payload, ensure_ascii=False)}"
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content}
                ]
            )
            
            try:
                result_raw = json.loads(response.choices[0].message.content)
                if isinstance(result_raw, list):
                    return result_raw
                elif isinstance(result_raw, dict):
                    for val in result_raw.values():
                        if isinstance(val, list):
                            return val
                raise ValueError("無法解析 OpenAI 回傳的 JSON 結構")
            except Exception as e:
                text_clean = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
                result_raw = json.loads(text_clean)
                if isinstance(result_raw, list):
                    return result_raw
                elif isinstance(result_raw, dict):
                    for val in result_raw.values():
                        if isinstance(val, list):
                            return val
                raise e
