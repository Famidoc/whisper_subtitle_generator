import json
import time
from PySide6.QtCore import QThread, Signal
from core.subtitle_parser import SubtitleItem

class LLMRefinerWorker(QThread):
    progress_changed = Signal(int)
    status_changed = Signal(str)
    finished_refining = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, items: list[SubtitleItem], config: dict):
        super().__init__()
        self.items = items
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            self.status_changed.emit("正在準備字幕進行 AI 潤飾...")
            self.progress_changed.emit(5)
            
            provider = self.config.get("llm_provider", "gemini")
            
            # 分批處理以避免單次 API 請求過載，將每批數量從 120 減少至 40，以防止 AI 因為生成長度過長而漏句，進而導致時間軸錯位。
            chunk_size = 40
            chunks = [self.items[i:i + chunk_size] for i in range(0, len(self.items), chunk_size)]
            
            refined_items = []
            
            for idx, chunk in enumerate(chunks):
                if self._is_cancelled:
                    return
                
                # 每次批次之間主動間隔 1.5 秒，避免免費 API 呼叫過於頻繁
                if idx > 0:
                    time.sleep(1.5)
                
                self.status_changed.emit(f"AI 正在潤飾字幕中 (批次 {idx+1}/{len(chunks)})...")
                
                # 將該批次的字幕轉為簡易 JSON 格式，減少 Token 浪費並保證對齊
                payload = [{"id": item.index, "text": item.text} for item in chunk]
                
                # 呼叫 API 潤飾 (支援 429 頻率限制自動重試)
                refined_data = self.call_llm_api_with_retry(provider, payload)
                
                if self._is_cancelled:
                    return

                # 將潤飾後的結果對應回原本的 SubtitleItem 中
                # 建立對照表
                refined_dict = {d["id"]: d["text"] for d in refined_data if "id" in d and "text" in d}
                
                for item in chunk:
                    # 如果 AI 回傳的 text 不為空，就更新 it；否則保留原樣
                    new_text = refined_dict.get(item.index, item.text)
                    refined_items.append(SubtitleItem(
                        index=item.index,
                        start=item.start,
                        end=item.end,
                        text=new_text
                    ))
                
                percent = 5 + int(((idx + 1) / len(chunks)) * 90)
                self.progress_changed.emit(min(percent, 95))
            
            self.progress_changed.emit(100)
            self.status_changed.emit("AI 字幕潤飾完成！")
            self.finished_refining.emit(refined_items)
            
        except Exception as e:
            if self._is_cancelled:
                self.status_changed.emit("已取消 AI 潤飾。")
            else:
                self.error_occurred.emit(str(e))

    def call_llm_api_with_retry(self, provider: str, payload: list) -> list:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.call_llm_api(provider, payload)
            except Exception as e:
                err_str = str(e)
                # 偵測是否為 429 Rate Limit 或 Quota 限制錯誤
                if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        self.status_changed.emit(f"觸發 API 頻率限制，等待 {wait_time} 秒後重試 (第 {attempt+1}/{max_retries} 次)...")
                        time.sleep(wait_time)
                        continue
                raise e

    def call_llm_api(self, provider: str, payload: list) -> list:
        max_len = self.config.get("max_line_length", 18)
        prompt = (
            "你是一個專業的繁體中文字幕潤飾助理。請幫我優化以下 JSON 陣列中的字幕文本。\n"
            "優化規則：\n"
            "1. 修正語音辨識錯誤的錯別字。\n"
            "2. 刪除口語贅字（例如「呃」、「然後」、「對」、「那」等不影響意思的字）。\n"
            "3. 確保詞彙與語法完全符合「台灣繁體中文」的習慣用語（例如將「視頻」改為「影片」、「計算機」改為「電腦」等）。\n"
            "4. 保持原本的字幕分句結構，不要合併或分裂句子，也絕對不要新增或刪除字幕條目。請嚴格確保輸入的每一條 id 與優化後的 text 一一對應，絕對不能漏掉任何一條，也不能將後續的句子往前遞補，以防造成嚴重的字幕與時間軸錯位。\n"
            f"5. 【字數與排版限制】我們希望單條字幕字數儘量不超過 {max_len} 字。如果單條字幕文字過長，請在校對時儘量精簡口語贅字，但「絕對禁止」丟棄重要語意，也「絕對禁止」自行插入 \\n 換行符號或任何折行標記。請確保輸出的 text 為純粹的單行文字，不要有任何換行。\n"
            f"6. 【絕對禁止截斷】必須保留完整且全部的字幕主要內容，絕對禁止為了字數限制而刪減關鍵字詞、截斷句子，或使用「...」等省略號代替原本的內容。寧可長度超出限制，也必須保證語意的完整！\n"
            "7. 請務必嚴格回傳一個合法的 JSON 陣列，格式與輸入完全相同：[{\"id\": 數字, \"text\": \"優化後的文字\"}]，不要有任何 Markdown 包裝（如 ```json）或額外的解釋文字。"
        )
        
        system_instruction = "你是一個只會輸出合法 JSON 格式的字幕校對與繁體化 AI 助手。"

        if provider == "gemini":
            api_key = self.config.get("gemini_api_key", "")
            if not api_key:
                raise ValueError("請先在設定中配置 Gemini API Key")
                
            try:
                import google.generativeai as genai
            except ImportError:
                raise ImportError("未安裝 google-generativeai 套件，請執行 pip install google-generativeai")
                
            genai.configure(api_key=api_key)
            # 優先使用設定中的模型，若無則預設為 gemini-2.5-flash
            model_name = self.config.get("gemini_model", "gemini-2.5-flash")
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"},
                system_instruction=system_instruction
            )
            
            contents = f"{prompt}\n\n輸入字幕資料如下：\n{json.dumps(payload, ensure_ascii=False)}"
            response = model.generate_content(contents)
            
            try:
                result = json.loads(response.text)
                return result
            except json.JSONDecodeError:
                # 容錯：有時 LLM 會回傳包覆在 ```json 中的字串
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
            
            user_content = f"{prompt}\n\n輸入字幕資料如下：\n{json.dumps(payload, ensure_ascii=False)}"
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content}
                ]
            )
            
            try:
                # OpenAI json_object 通常會回傳一個包含陣列的物件，如 {"subtitles": [...]} 或是直接一個 array 的 JSON
                # 為了確保安全，我們解析後看看
                result_raw = json.loads(response.choices[0].message.content)
                if isinstance(result_raw, list):
                    return result_raw
                elif isinstance(result_raw, dict):
                    # 如果回傳的是帶 key 的字典，嘗試找尋 list 物件
                    for val in result_raw.values():
                        if isinstance(val, list):
                            return val
                raise ValueError("無法解析 OpenAI 回傳的 JSON 結構")
            except Exception as e:
                # 容錯
                text_clean = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
                result_raw = json.loads(text_clean)
                if isinstance(result_raw, list):
                    return result_raw
                elif isinstance(result_raw, dict):
                    for val in result_raw.values():
                        if isinstance(val, list):
                            return val
                raise e
