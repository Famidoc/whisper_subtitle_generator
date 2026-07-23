import re
import os

class SubtitleItem:
    def __init__(self, index: int, start: float, end: float, text: str, translation: str = ""):
        self.index = index
        self.start = start  # 以秒為單位 (float)
        self.end = end    # 以秒為單位 (float)
        self.text = text
        self.translation = translation

def format_time(seconds: float, is_vtt: bool = False) -> str:
    """將秒數轉換為 00:00:00,000 (SRT) 或 00:00:00.000 (VTT) 格式"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int(round((seconds - int(seconds)) * 1000))
    if msecs >= 1000:
        msecs = 999  # 防止進位超出
        
    sep = "." if is_vtt else ","
    return f"{hrs:02d}:{mins:02d}:{secs:02d}{sep}{msecs:03d}"

def parse_time(time_str: str) -> float:
    """將 00:00:00,000 或 00:00:00.000 時間字串轉回秒數 (float)"""
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    if len(parts) == 3:
        hrs = int(parts[0])
        mins = int(parts[1])
        secs_parts = parts[2].split('.')
        secs = int(secs_parts[0])
        msecs = int(secs_parts[1]) if len(secs_parts) > 1 else 0
        return hrs * 3600 + mins * 60 + secs + msecs / 1000.0
    elif len(parts) == 2:
        mins = int(parts[0])
        secs_parts = parts[1].split('.')
        secs = int(secs_parts[0])
        msecs = int(secs_parts[1]) if len(secs_parts) > 1 else 0
        return mins * 60 + secs + msecs / 1000.0
    return 0.0

class SubtitleParser:
    @staticmethod
    def _get_display_text(item: SubtitleItem, mode: str = "original") -> str:
        """根據模式取得輸出之字幕內文"""
        text = item.text.strip()
        trans = item.translation.strip()
        
        if mode == "translation":
            return trans if trans else text
        elif mode == "bilingual_top_orig":
            return f"{text}\n{trans}" if trans else text
        elif mode == "bilingual_top_trans":
            return f"{trans}\n{text}" if trans else text
        else: # original
            return text

    @staticmethod
    def to_srt(items: list[SubtitleItem], mode: str = "original") -> str:
        """將字幕清單轉為 SRT 格式字串"""
        lines = []
        for item in items:
            start_str = format_time(item.start, is_vtt=False)
            end_str = format_time(item.end, is_vtt=False)
            display_text = SubtitleParser._get_display_text(item, mode)
            lines.append(f"{item.index}")
            lines.append(f"{start_str} --> {end_str}")
            lines.append(display_text)
            lines.append("") # 空行分隔
        return "\n".join(lines)

    @staticmethod
    def to_vtt(items: list[SubtitleItem], mode: str = "original") -> str:
        """將字幕清單轉為 VTT 格式字串"""
        lines = ["WEBVTT", ""]
        for item in items:
            start_str = format_time(item.start, is_vtt=True)
            end_str = format_time(item.end, is_vtt=True)
            display_text = SubtitleParser._get_display_text(item, mode)
            lines.append(f"{item.index}")
            lines.append(f"{start_str} --> {end_str}")
            lines.append(display_text)
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def to_txt(items: list[SubtitleItem], mode: str = "original") -> str:
        """將字幕清單轉為純文字 (段落)"""
        return "\n".join([SubtitleParser._get_display_text(item, mode) for item in items])

    @staticmethod
    def _is_bilingual_pair(line1: str, line2: str) -> bool:
        """檢測兩行文字是否為雙語對照 (例如中英、日英對照)"""
        has_cjk1 = bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', line1))
        has_latin1 = bool(re.search(r'[a-zA-Z]', line1))
        has_cjk2 = bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', line2))
        has_latin2 = bool(re.search(r'[a-zA-Z]', line2))
        
        if (has_cjk1 and not has_cjk2 and has_latin2) or (has_cjk2 and not has_cjk1 and has_latin1):
            return True
        return False

    @staticmethod
    def parse_srt(content: str) -> list[SubtitleItem]:
        """解析 SRT 內容字串，回傳 SubtitleItem 串列 (自動識別並拆分雙語字幕)"""
        items = []
        blocks = re.split(r'\n\s*\n', content.strip())
        index_counter = 1
        
        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if len(lines) < 2:
                continue
                
            if "-->" in lines[0]:
                time_line = lines[0]
                raw_text_lines = lines[1:]
            elif "-->" in lines[1]:
                time_line = lines[1]
                raw_text_lines = lines[2:]
            else:
                continue
            
            time_match = re.match(r'(\d+:\d+:\d+[\,\.]\d+)\s*-->\s*(\d+:\d+:\d+[\,\.]\d+)', time_line)
            if time_match:
                start = parse_time(time_match.group(1))
                end = parse_time(time_match.group(2))
                
                if len(raw_text_lines) >= 2:
                    if SubtitleParser._is_bilingual_pair(raw_text_lines[0], raw_text_lines[1]):
                        text_val = raw_text_lines[0]
                        trans_val = "\n".join(raw_text_lines[1:])
                    else:
                        text_val = "\n".join(raw_text_lines)
                        trans_val = ""
                elif len(raw_text_lines) == 1:
                    text_val = raw_text_lines[0]
                    trans_val = ""
                else:
                    text_val = ""
                    trans_val = ""
                    
                items.append(SubtitleItem(index_counter, start, end, text_val, trans_val))
                index_counter += 1
                
        return items

    @staticmethod
    def parse_vtt(content: str) -> list[SubtitleItem]:
        """解析 VTT 內容字串，回傳 SubtitleItem 串列 (自動識別並拆分雙語字幕)"""
        if content.startswith("WEBVTT"):
            content = content.replace("WEBVTT", "", 1)
        
        items = []
        blocks = re.split(r'\n\s*\n', content.strip())
        index_counter = 1
        
        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue
                
            time_line = ""
            text_start_idx = 1
            
            if "-->" in lines[0]:
                time_line = lines[0]
                text_start_idx = 1
            elif len(lines) > 1 and "-->" in lines[1]:
                time_line = lines[1]
                text_start_idx = 2
            else:
                continue
                
            time_match = re.match(r'(\d+:?\d+:\d+[\,\.]\d+)\s*-->\s*(\d+:?\d+:\d+[\,\.]\d+)', time_line)
            if time_match:
                start = parse_time(time_match.group(1))
                end = parse_time(time_match.group(2))
                raw_text_lines = lines[text_start_idx:]
                
                if len(raw_text_lines) >= 2:
                    if SubtitleParser._is_bilingual_pair(raw_text_lines[0], raw_text_lines[1]):
                        text_val = raw_text_lines[0]
                        trans_val = "\n".join(raw_text_lines[1:])
                    else:
                        text_val = "\n".join(raw_text_lines)
                        trans_val = ""
                elif len(raw_text_lines) == 1:
                    text_val = raw_text_lines[0]
                    trans_val = ""
                else:
                    text_val = ""
                    trans_val = ""
                    
                items.append(SubtitleItem(index_counter, start, end, text_val, trans_val))
                index_counter += 1
                
        return items

    @staticmethod
    def save_subtitles(items: list[SubtitleItem], filepath: str, mode: str = "original"):
        """根據副檔名自動儲存字幕檔案"""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".srt":
            content = SubtitleParser.to_srt(items, mode=mode)
        elif ext == ".vtt":
            content = SubtitleParser.to_vtt(items, mode=mode)
        elif ext == ".txt":
            content = SubtitleParser.to_txt(items, mode=mode)
        else:
            raise ValueError(f"不支援的副檔名: {ext}")
            
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
