import unittest
import os
import json
import shutil
import tempfile
from core.config_manager import ConfigManager
from core.subtitle_parser import SubtitleItem, SubtitleParser, format_time, parse_time
from core.ffmpeg_helper import FFmpegHelper
from core.subtitle_splitter import SubtitleSplitter

class TestSubtitleGenerator(unittest.TestCase):
    def setUp(self):
        # 建立暫存檔用於測試 Config
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")

    def tearDown(self):
        # 清除暫存目錄
        shutil.rmtree(self.temp_dir)

    def test_config_obfuscation(self):
        """測試設定檔的金鑰加密混淆與還原"""
        manager = ConfigManager(config_path=self.config_path)
        
        # 測試預設值
        self.assertEqual(manager.get("whisper_mode"), "local")
        
        # 設定敏感金鑰
        test_key = "sk-proj-test1234567890abcdef"
        manager.set("openai_api_key", test_key)
        manager.save()
        
        # 讀取剛剛寫入的設定檔，直接讀取 JSON 檢查是否已經被混淆（不是明文）
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertNotEqual(data["openai_api_key"], test_key)
            self.assertTrue(len(data["openai_api_key"]) > 0)
            
        # 重新實體化 manager，驗證讀取時是否自動解密回明文
        new_manager = ConfigManager(config_path=self.config_path)
        self.assertEqual(new_manager.get("openai_api_key"), test_key)

    def test_subtitle_parser(self):
        """測試 SRT/VTT 時間轉換與解析功能"""
        # 測試時間格式化 (SRT)
        self.assertEqual(format_time(1.5, is_vtt=False), "00:00:01,500")
        self.assertEqual(format_time(3665.25, is_vtt=False), "01:01:05,250")
        
        # 測試時間解析
        self.assertEqual(parse_time("00:00:01,500"), 1.5)
        self.assertEqual(parse_time("01:01:05.250"), 3665.25)
        
        # 測試 SRT 輸出與解析
        items = [
            SubtitleItem(1, 1.0, 3.5, "第一句字幕內容"),
            SubtitleItem(2, 4.2, 7.8, "第二句字幕內容\n帶有分行")
        ]
        
        srt_content = SubtitleParser.to_srt(items)
        self.assertIn("00:00:01,000 --> 00:00:03,500", srt_content)
        self.assertIn("第一句字幕內容", srt_content)
        self.assertIn("第二句字幕內容", srt_content)
        
        # 解析還原測試
        parsed_items = SubtitleParser.parse_srt(srt_content)
        self.assertEqual(len(parsed_items), 2)
        self.assertEqual(parsed_items[0].start, 1.0)
        self.assertEqual(parsed_items[0].end, 3.5)
        self.assertEqual(parsed_items[0].text, "第一句字幕內容")
        self.assertEqual(parsed_items[1].text, "第二句字幕內容\n帶有分行")

    def test_ffmpeg_helper(self):
        """測試 FFmpegHelper 是否能正常初始化並檢測"""
        helper = FFmpegHelper(bin_dir=self.temp_dir)
        # 本地 bin 目錄目前是空的，且此處可能沒有系統 FFmpeg
        # 我們只測試 is_available 在無 ffmpeg 時的回傳值
        if not helper.check_system_ffmpeg():
            self.assertFalse(helper.is_available())

    def test_subtitle_splitter(self):
        """測試 SubtitleSplitter 的切分功能與時間軸分配"""
        # 1. 測試文字切分 (標點符號優先)
        text = "今天天氣很好，我們一起去公園玩吧，你覺得怎麼樣？"
        segments = SubtitleSplitter.split_text_by_punctuation(text, max_len=10)
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0], "今天天氣很好，")
        self.assertEqual(segments[1], "我們一起去公園玩吧，")
        self.assertEqual(segments[2], "你覺得怎麼樣？")

        # 2. 測試無標點符號的強制切分
        text_no_punc = "今天天氣很好我們一起去公園玩吧你覺得怎麼樣"
        segments_no_punc = SubtitleSplitter.split_text_by_punctuation(text_no_punc, max_len=10)
        self.assertEqual(len(segments_no_punc), 3)
        self.assertEqual(segments_no_punc[0], "今天天氣很好我們一起")
        self.assertEqual(segments_no_punc[1], "去公園玩吧你覺得怎麼")
        self.assertEqual(segments_no_punc[2], "樣")

        # 3. 測試單條 SubtitleItem 的切分與時間等比例分配
        item = SubtitleItem(1, 0.0, 10.0, "今天天氣很好，我們一起去公園玩吧，你覺得怎麼樣？")
        split_items = SubtitleSplitter.split_item(item, max_len=10)
        self.assertEqual(len(split_items), 3)
        self.assertAlmostEqual(split_items[0].start, 0.0)
        self.assertTrue(split_items[0].end > 0.0)
        self.assertAlmostEqual(split_items[2].end, 10.0)
        self.assertEqual(split_items[0].text, "今天天氣很好，")
        self.assertEqual(split_items[1].text, "我們一起去公園玩吧，")
        self.assertEqual(split_items[2].text, "你覺得怎麼樣？")

        # 4. 測試防範鄰近字幕重疊與微小間隙無縫對齊問題
        items = [
            SubtitleItem(1, 149.258, 153.840, "而且至少跑過五場馬拉松，或兩場超馬的超級資深跑者。"),
            SubtitleItem(2, 154.040, 156.720, "結果，大家深呼吸準備好了嗎？")
        ]
        res = SubtitleSplitter.split_subtitles(items, max_len=22)
        # 驗證切分後的微小間隙已被無縫對齊 (第 50 行結束時間對齊第 51 行開始時間 154.040)
        self.assertEqual(res[0].end, res[1].start)
        self.assertEqual(res[1].end, res[2].start)

    def test_bilingual_subtitles(self):
        """測試雙語字幕物件與多模式 SRT 匯出」"""
        items = [
            SubtitleItem(1, 1.0, 3.5, "你好，世界！", "Hello World!"),
            SubtitleItem(2, 4.0, 6.0, "歡迎使用 Whisper 字幕產生器。", "Welcome to Whisper Subtitle Generator.")
        ]
        
        # 測試雙語合一 (原文在上)
        srt_bilingual = SubtitleParser.to_srt(items, mode="bilingual_top_orig")
        self.assertIn("你好，世界！\nHello World!", srt_bilingual)
        
        # 測試雙語合一 (譯文在上)
        srt_bilingual_trans = SubtitleParser.to_srt(items, mode="bilingual_top_trans")
        self.assertIn("Hello World!\n你好，世界！", srt_bilingual_trans)
        
        # 測試僅譯文
        srt_trans_only = SubtitleParser.to_srt(items, mode="translation")
        self.assertIn("Hello World!", srt_trans_only)
        self.assertNotIn("你好，世界！", srt_trans_only)

if __name__ == "__main__":
    unittest.main()
