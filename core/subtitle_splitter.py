import re
from core.subtitle_parser import SubtitleItem

class SubtitleSplitter:
    @staticmethod
    def split_text_by_punctuation(text: str, max_len: int) -> list[str]:
        """
        將文字依標點符號、空格或字數切分為符合 max_len 的多個子段落。
        優先在標點符號或空格處切分，以保持語意完整。
        """
        text = text.strip()
        if len(text) <= max_len:
            return [text]

        # 定義常見的停頓與結束標點符號 (全形與半形，包含空格)
        punctuations = r'[,.!?;:，。！？、；：\s]'
        
        # 尋找所有標點符號的位置
        matches = list(re.finditer(punctuations, text))
        
        segments = []
        start_idx = 0
        
        while start_idx < len(text):
            remaining_len = len(text) - start_idx
            if remaining_len <= max_len:
                segments.append(text[start_idx:].strip())
                break
                
            # 在 [start_idx, start_idx + max_len] 範圍內尋找最後一個標點符號
            best_split = -1
            for m in matches:
                pos = m.start()
                if start_idx < pos <= start_idx + max_len:
                    best_split = pos
                elif pos > start_idx + max_len:
                    break
                    
            if best_split != -1:
                # 包含標點符號在內一起切分 (例如「我，」)
                split_pos = best_split + 1
                segments.append(text[start_idx:split_pos].strip())
                start_idx = split_pos
            else:
                # 範圍內找不到標點符號，只好強行在 max_len 處均分
                split_pos = start_idx + max_len
                segments.append(text[start_idx:split_pos].strip())
                start_idx = split_pos
                
        return [s for s in segments if s]

    @classmethod
    def split_item(cls, item: SubtitleItem, max_len: int) -> list[SubtitleItem]:
        """
        將單個過長的 SubtitleItem 依據字數比例切分為多個 SubtitleItem，
        並重新分配對應的時間軸。
        """
        text = item.text.strip()
        if len(text) <= max_len:
            return [item]
            
        sub_texts = cls.split_text_by_punctuation(text, max_len)
        if len(sub_texts) <= 1:
            return [item]
            
        total_chars = sum(len(t) for t in sub_texts)
        if total_chars == 0:
            return [item]
            
        split_items = []
        current_start = item.start
        duration = item.end - item.start
        k = len(sub_texts)
        
        # 決定每條子字幕的最短保障時間（預設 0.5 秒）
        min_dur = 0.5
        if duration < min_dur * k:
            # 若總時間不夠每條分配 0.5 秒，則退回純依字數比例分配
            min_dur = 0.0
            
        rem_duration = duration - (min_dur * k)
        
        for idx, sub_text in enumerate(sub_texts):
            sub_len = len(sub_text)
            ratio = sub_len / total_chars
            
            # 計算該段落的時間長度：保障最低時間 + 剩餘時間依字數比例分配
            sub_duration = min_dur + (rem_duration * ratio)
            current_end = current_start + sub_duration
            
            # 確保最後一項的結束時間與原本條目完全吻合，避免時間溢出或缺漏
            if idx == k - 1:
                current_end = item.end
                
            split_items.append(SubtitleItem(
                index=0,  # 後續會再重新統一編號
                start=round(current_start, 3),
                end=round(current_end, 3),
                text=sub_text
            ))
            current_start = current_end
            
        return split_items

    @classmethod
    def split_subtitles(cls, items: list[SubtitleItem], max_len: int) -> list[SubtitleItem]:
        """
        處理整個字幕清單，將其中所有過長字幕切分，並重新計算 index。
        同時防範鄰近字幕項目的時間軸重疊與微小間隙問題。
        """
        new_items = []
        for item in items:
            split_results = cls.split_item(item, max_len)
            new_items.extend(split_results)
            
        # 防護與自動對齊：若上一條的 end 與下一條的 start 重疊 (gap < 0) 或有微小間隙 (gap <= 0.5 秒)，自動對齊銜接
        for idx in range(len(new_items) - 1):
            gap = new_items[idx + 1].start - new_items[idx].end
            if gap <= 0.5:
                new_items[idx].end = new_items[idx + 1].start
                
        # 重新整理編號
        for idx, item in enumerate(new_items):
            item.index = idx + 1
            
        return new_items
