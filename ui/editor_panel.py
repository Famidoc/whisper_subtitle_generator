import os
import copy
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, 
    QLineEdit, QHeaderView, QAbstractItemView, QStyledItemDelegate,
    QDialog, QRadioButton, QButtonGroup, QComboBox, QProgressDialog
)
from PySide6.QtCore import Qt, QUrl, QEvent
from PySide6.QtGui import QUndoStack, QUndoCommand, QShortcut, QKeySequence
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from core.subtitle_parser import SubtitleItem, SubtitleParser, format_time, parse_time
from core.config_manager import ConfigManager
from core.audio_extractor import AudioExtractor
from core.subtitle_splitter import SubtitleSplitter
from core.llm_translator import LLMTranslatorWorker

# Undo / Redo Command 類別實作
class CellEditCommand(QUndoCommand):
    def __init__(self, panel, row: int, col: int, old_val: str, new_val: str):
        super().__init__(f"編輯字幕格 (行 {row+1}, 列 {col})")
        self.panel = panel
        self.row = row
        self.col = col
        self.old_val = old_val
        self.new_val = new_val

    def _apply_val(self, val: str):
        if self.row >= len(self.panel.items):
            return
        item = self.panel.items[self.row]
        if self.col == 1:
            item.start = parse_time(val)
        elif self.col == 2:
            item.end = parse_time(val)
        elif self.col == 3:
            item.text = val
        elif self.col == 4:
            item.translation = val
            
        # 僅更新該格單元格內文與調適單行高度，不重繪整張表格
        table_item = self.panel.table.item(self.row, self.col)
        if table_item and table_item.text() != val:
            try:
                self.panel.table.itemChanged.disconnect(self.panel.on_table_item_changed)
            except Exception:
                pass
            table_item.setText(val)
            self.panel.table.itemChanged.connect(self.panel.on_table_item_changed)
            
        self.panel.table.resizeRowToContents(self.row)

    def undo(self):
        self._apply_val(self.old_val)

    def redo(self):
        self._apply_val(self.new_val)

class AddRowCommand(QUndoCommand):
    def __init__(self, panel, insert_row: int, new_item: SubtitleItem):
        super().__init__("新增字幕行")
        self.panel = panel
        self.insert_row = insert_row
        self.new_item = new_item

    def undo(self):
        if 0 <= self.insert_row < len(self.panel.items):
            self.panel.items.pop(self.insert_row)
            self.panel.populate_table()

    def redo(self):
        self.panel.items.insert(self.insert_row, copy.deepcopy(self.new_item))
        self.panel.populate_table()
        self.panel.table.selectRow(self.insert_row)

class DeleteRowCommand(QUndoCommand):
    def __init__(self, panel, row: int, deleted_item: SubtitleItem, prev_item_old_end: float):
        super().__init__("刪除字幕行")
        self.panel = panel
        self.row = row
        self.deleted_item = deleted_item
        self.prev_item_old_end = prev_item_old_end

    def undo(self):
        self.panel.items.insert(self.row, copy.deepcopy(self.deleted_item))
        if self.row > 0 and self.row - 1 < len(self.panel.items):
            self.panel.items[self.row - 1].end = self.prev_item_old_end
        self.panel.populate_table()
        self.panel.table.selectRow(self.row)

    def redo(self):
        if 0 <= self.row < len(self.panel.items):
            if self.row > 0:
                self.panel.items[self.row - 1].end = max(self.panel.items[self.row - 1].end, self.panel.items[self.row].end)
            self.panel.items.pop(self.row)
            self.panel.populate_table()

class SplitRowCommand(QUndoCommand):
    def __init__(self, panel, row: int, text1: str, text2: str, mid_time: float, orig_end: float, orig_text: str):
        super().__init__("於游標處斷行")
        self.panel = panel
        self.row = row
        self.text1 = text1
        self.text2 = text2
        self.mid_time = mid_time
        self.orig_end = orig_end
        self.orig_text = orig_text

    def undo(self):
        if 0 <= self.row < len(self.panel.items):
            self.panel.items[self.row].text = self.orig_text
            self.panel.items[self.row].end = self.orig_end
            if self.row + 1 < len(self.panel.items):
                self.panel.items.pop(self.row + 1)
            self.panel.populate_table()
            self.panel.table.selectRow(self.row)

    def redo(self):
        if 0 <= self.row < len(self.panel.items):
            item = self.panel.items[self.row]
            item.text = self.text1
            item.end = self.mid_time
            new_item = SubtitleItem(
                index=item.index + 1,
                start=self.mid_time,
                end=self.orig_end,
                text=self.text2,
                translation=""
            )
            self.panel.items.insert(self.row + 1, new_item)
            self.panel.populate_table()
            self.panel.table.setCurrentCell(self.row + 1, 3)

class BatchReplaceItemsCommand(QUndoCommand):
    def __init__(self, panel, descr: str, old_items: list[SubtitleItem], new_items: list[SubtitleItem]):
        super().__init__(descr)
        self.panel = panel
        self.old_items = copy.deepcopy(old_items)
        self.new_items = copy.deepcopy(new_items)

    def undo(self):
        self.panel.items = copy.deepcopy(self.old_items)
        self.panel.populate_table()

    def redo(self):
        self.panel.items = copy.deepcopy(self.new_items)
        self.panel.populate_table()

class SubtitleDelegate(QStyledItemDelegate):
    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.installEventFilter(self)
        return editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            # 偵測 Ctrl + Enter
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                if isinstance(obj, QLineEdit):
                    cursor_pos = obj.cursorPosition()
                    text = obj.text()
                    row = self.panel.table.currentIndex().row()
                    col = self.panel.table.currentIndex().column()
                    
                    if col == 3: # 僅在原文列支援斷行
                        self.commitData.emit(obj)
                        self.closeEditor.emit(obj)
                        self.panel.split_row(row, cursor_pos, text)
                        return True
        return super().eventFilter(obj, event)

class EditorPanel(QWidget):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.items = []
        self.audio_file = ""
        self.media_file = ""
        
        self.undo_stack = QUndoStack(self)
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.is_jumping = False
        self.translator_worker = None
        
        self.init_ui()
        self.setup_connections()
        self.setup_shortcuts()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # 標題與頂部工具列
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_label = QLabel("字幕編輯器")
        title_label.setObjectName("Title")
        self.subtitle_label = QLabel("尚無載入的字幕。請先在「字幕轉譯」分頁中處理檔案。")
        self.subtitle_label.setObjectName("Subtitle")
        title_box.addWidget(title_label)
        title_box.addWidget(self.subtitle_label)
        header_layout.addLayout(title_box)
        
        header_layout.addStretch()
        
        self.undo_btn = QPushButton("↩ 復原 (Ctrl+Z)")
        self.redo_btn = QPushButton("↪ 重做 (Ctrl+Y)")
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)
        header_layout.addWidget(self.undo_btn)
        header_layout.addWidget(self.redo_btn)
        
        self.import_btn = QPushButton("開啟字幕檔")
        self.import_btn.clicked.connect(self.import_subtitles)
        header_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("匯出字幕檔")
        self.export_btn.setObjectName("PrimaryButton")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_subtitles)
        header_layout.addWidget(self.export_btn)
        
        layout.addLayout(header_layout)

        # 搜尋與取代列
        search_card = QWidget()
        search_card.setProperty("class", "Card")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(10, 8, 10, 8)
        search_layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜尋文字...")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("替換為...")
        
        self.search_btn = QPushButton("搜尋")
        self.replace_btn = QPushButton("替換當前")
        self.replace_all_btn = QPushButton("全部替換")
        
        search_layout.addWidget(QLabel("🔍 搜尋與替換："))
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.replace_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.replace_btn)
        search_layout.addWidget(self.replace_all_btn)
        
        layout.addWidget(search_card)

        # 字幕表格 (5 欄位)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "開始時間", "結束時間", "原文 / 主字幕", "譯文 / 副字幕"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setWordWrap(True)
        
        self.delegate = SubtitleDelegate(self)
        self.table.setItemDelegateForColumn(3, self.delegate)
        self.table.setItemDelegateForColumn(4, self.delegate)
        
        layout.addWidget(self.table, stretch=5)

        # 播放器與操作面板
        player_card = QWidget()
        player_card.setProperty("class", "Card")
        player_layout = QHBoxLayout(player_card)
        player_layout.setContentsMargins(15, 10, 15, 10)
        player_layout.setSpacing(10)
        
        self.play_btn = QPushButton("▶ 播放 (Space)")
        self.stop_btn = QPushButton("⏹ 停止")
        
        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        
        self.add_row_btn = QPushButton("➕ 新增字幕行")
        self.split_row_btn = QPushButton("✂ 於游標處斷行")
        self.auto_split_btn = QPushButton("✂ 一鍵切分長句")
        self.auto_split_btn.setEnabled(False)
        self.translate_btn = QPushButton("🌐 AI 翻譯字幕")
        self.translate_btn.setEnabled(False)
        self.del_row_btn = QPushButton("➖ 刪除選取行")
        
        player_layout.addWidget(self.play_btn)
        player_layout.addWidget(self.stop_btn)
        player_layout.addWidget(self.time_label)
        player_layout.addStretch()
        player_layout.addWidget(self.add_row_btn)
        player_layout.addWidget(self.split_row_btn)
        player_layout.addWidget(self.auto_split_btn)
        player_layout.addWidget(self.translate_btn)
        player_layout.addWidget(self.del_row_btn)
        
        layout.addWidget(player_card)

    def setup_connections(self):
        self.player.positionChanged.connect(self.on_player_position_changed)
        self.player.durationChanged.connect(self.on_player_duration_changed)
        
        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn.clicked.connect(self.stop_play)
        
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table.itemChanged.connect(self.on_table_item_changed)
        
        self.add_row_btn.clicked.connect(self.add_row)
        self.split_row_btn.clicked.connect(self.show_split_tip)
        self.auto_split_btn.clicked.connect(self.auto_split_subtitles)
        self.translate_btn.clicked.connect(self.show_translation_dialog)
        self.del_row_btn.clicked.connect(self.delete_row)
        
        self.search_btn.clicked.connect(self.search_text)
        self.replace_btn.clicked.connect(self.replace_text)
        self.replace_all_btn.clicked.connect(self.replace_all_text)
        
        self.undo_btn.clicked.connect(self.undo_stack.undo)
        self.redo_btn.clicked.connect(self.undo_stack.redo)
        self.undo_stack.canUndoChanged.connect(self.undo_btn.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.redo_btn.setEnabled)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo_stack.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.undo_stack.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self.undo_stack.redo)
        
        # 空白鍵控制播放 / 暫停 (當未處於單元格編輯模式時)
        space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space_shortcut.activated.connect(self.on_space_pressed)

    def on_space_pressed(self):
        # 若表格正在編輯文字，不觸發播放跳轉
        if self.table.state() != QAbstractItemView.State.EditingState:
            self.toggle_play()

    def set_subtitles(self, items: list[SubtitleItem], media_file: str):
        self.stop_play()
        self.undo_stack.clear()
        
        self.items = copy.deepcopy(items)
        self.media_file = media_file
        self.export_btn.setEnabled(True)
        self.auto_split_btn.setEnabled(True if items else False)
        self.translate_btn.setEnabled(True if items else False)
        
        ext = os.path.splitext(media_file)[1].lower()
        if ext in (".srt", ".vtt", ".txt"):
            self.subtitle_label.setText(f"已載入字幕檔：{os.path.basename(media_file)}")
            self.audio_file = ""
            self.player.setSource(QUrl())
        else:
            self.subtitle_label.setText(f"已載入：{os.path.basename(media_file)}")
            try:
                extractor = AudioExtractor()
                self.audio_file = extractor.extract_audio(media_file)
                self.player.setSource(QUrl.fromLocalFile(self.audio_file))
            except Exception as e:
                print(f"無法提取音軌做為播放器來源，改為直接播放原始檔案：{e}")
                self.audio_file = media_file
                self.player.setSource(QUrl.fromLocalFile(media_file))

        self.populate_table()

    def import_subtitles(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "開啟字幕檔案", "",
            "字幕檔案 (*.srt *.vtt);;SubRip 字幕檔 (*.srt);;WebGL 網頁字幕檔 (*.vtt)"
        )
        if not file_path:
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".srt":
                items = SubtitleParser.parse_srt(content)
            elif ext == ".vtt":
                items = SubtitleParser.parse_vtt(content)
            else:
                raise ValueError("不支援的字幕格式")
                
            if not items:
                raise ValueError("字幕檔案內容為空或無法解析")
                
            self.set_subtitles(items, file_path)
            QMessageBox.information(self, "載入成功", f"已成功載入 {len(items)} 條字幕！")
        except Exception as e:
            QMessageBox.critical(self, "載入失敗", f"無法讀取字幕檔案：\n{e}")

    def populate_table(self):
        try:
            self.table.itemChanged.disconnect(self.on_table_item_changed)
        except Exception:
            pass
        
        self.table.setRowCount(len(self.items))
        for idx, item in enumerate(self.items):
            item.index = idx + 1
            
            idx_item = QTableWidgetItem(str(item.index))
            idx_item.setFlags(idx_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(idx, 0, idx_item)
            
            start_item = QTableWidgetItem(format_time(item.start, is_vtt=False))
            start_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(idx, 1, start_item)
            
            end_item = QTableWidgetItem(format_time(item.end, is_vtt=False))
            end_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(idx, 2, end_item)
            
            text_item = QTableWidgetItem(item.text)
            self.table.setItem(idx, 3, text_item)
            
            trans_item = QTableWidgetItem(item.translation)
            self.table.setItem(idx, 4, trans_item)
            
        self.table.resizeRowsToContents()
        self.table.itemChanged.connect(self.on_table_item_changed)

    def on_table_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()
        
        if row >= len(self.items):
            return
            
        subtitle_item = self.items[row]
        old_val = ""
        new_val = item.text()
        
        if col == 1:
            old_val = format_time(subtitle_item.start, is_vtt=False)
        elif col == 2:
            old_val = format_time(subtitle_item.end, is_vtt=False)
        elif col == 3:
            old_val = subtitle_item.text
        elif col == 4:
            old_val = subtitle_item.translation
            
        if old_val != new_val:
            cmd = CellEditCommand(self, row, col, old_val, new_val)
            self.undo_stack.push(cmd)

    def on_table_selection_changed(self):
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return
            
        row = selected_ranges[0].topRow()
        if row < len(self.items) and not self.is_jumping:
            item = self.items[row]
            self.is_jumping = True
            self.player.setPosition(int(item.start * 1000))
            self.is_jumping = False

    def on_player_position_changed(self, position: int):
        current_sec = position / 1000.0
        total_sec = self.player.duration() / 1000.0
        
        self.time_label.setText(
            f"{format_time(current_sec, is_vtt=False)} / {format_time(total_sec, is_vtt=False)}"
        )
        
        if not self.is_jumping:
            matched_row = -1
            for idx, item in enumerate(self.items):
                if item.start <= current_sec <= item.end:
                    matched_row = idx
                    break
            
            if matched_row != -1:
                self.is_jumping = True
                self.table.selectRow(matched_row)
                self.table.scrollToItem(self.table.item(matched_row, 0))
                self.is_jumping = False

    def on_player_duration_changed(self, duration: int):
        current_sec = self.player.position() / 1000.0
        total_sec = duration / 1000.0
        self.time_label.setText(
            f"{format_time(current_sec, is_vtt=False)} / {format_time(total_sec, is_vtt=False)}"
        )

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶ 播放 (Space)")
        else:
            self.player.play()
            self.play_btn.setText("⏸ 暫停 (Space)")

    def stop_play(self):
        self.player.stop()
        self.play_btn.setText("▶ 播放 (Space)")

    def add_row(self):
        selected_ranges = self.table.selectedRanges()
        insert_row = len(self.items)
        
        if selected_ranges:
            insert_row = selected_ranges[0].topRow() + 1
            
        start_time = 0.0
        if insert_row > 0 and insert_row - 1 < len(self.items):
            start_time = self.items[insert_row - 1].end
            
        new_item = SubtitleItem(
            index=insert_row + 1,
            start=start_time,
            end=start_time + 3.0,
            text="[新增的字幕內容]",
            translation=""
        )
        
        cmd = AddRowCommand(self, insert_row, new_item)
        self.undo_stack.push(cmd)

    def show_split_tip(self):
        QMessageBox.information(
            self, "如何拆分字幕", 
            "💡 拆分字幕提示：\n\n"
            "請直接雙擊您要修改的字幕文字，將游標移到要切斷的位置，然後在鍵盤上按下：\n"
            "【 Ctrl + Enter 】\n\n"
            "程式就會自動幫您將文字與時間軸切分成兩半喔！"
        )

    def split_row(self, row: int, cursor_pos: int, current_text: str):
        if row < 0 or row >= len(self.items):
            return
            
        text1 = current_text[:cursor_pos].strip()
        text2 = current_text[cursor_pos:].strip()
        
        item = self.items[row]
        start_time = item.start
        end_time = item.end
        duration = end_time - start_time
        
        len1 = len(text1)
        len2 = len(text2)
        total_len = len1 + len2
        
        if len1 > 0 and len2 > 0:
            ratio = len1 / total_len
            split_duration = max(0.5, min(duration - 0.5, duration * ratio))
            mid_time = start_time + split_duration
        else:
            mid_time = start_time + duration / 2
            
        cmd = SplitRowCommand(self, row, text1, text2, mid_time, end_time, item.text)
        self.undo_stack.push(cmd)

    def delete_row(self):
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            QMessageBox.information(self, "提示", "請先點選您要刪除的字幕行。")
            return
            
        row = selected_ranges[0].topRow()
        if row < len(self.items):
            deleted_item = self.items[row]
            prev_item_old_end = self.items[row - 1].end if row > 0 else 0.0
            cmd = DeleteRowCommand(self, row, deleted_item, prev_item_old_end)
            self.undo_stack.push(cmd)

    def auto_split_subtitles(self):
        if not self.items:
            return
            
        max_len = self.config_manager.get("max_line_length", 18)
        
        reply = QMessageBox.question(
            self, "確認一鍵切分",
            f"是否將整份字幕中長度大於 {max_len} 字的句子自動切分？\n"
            "這會依字數比例重新分配對應的時間軸並重新編號。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                old_items = copy.deepcopy(self.items)
                new_items = SubtitleSplitter.split_subtitles(self.items, max_len)
                cmd = BatchReplaceItemsCommand(self, "一鍵切分長句", old_items, new_items)
                self.undo_stack.push(cmd)
                
                QMessageBox.information(
                    self, "切分完畢",
                    f"自動切分長字幕完成！\n"
                    f"原本條目數：{len(old_items)}\n"
                    f"切分後條目數：{len(new_items)}\n"
                    f"新增了 {len(new_items) - len(old_items)} 條字幕。"
                )
            except Exception as e:
                QMessageBox.critical(self, "切分失敗", f"自動切分長字幕時發生錯誤：\n{e}")

    # AI 自動翻譯
    def show_translation_dialog(self):
        if not self.items:
            return
            
        dlg = QDialog(self)
        dlg.setWindowTitle("🌐 AI 字幕翻譯設定")
        dlg.resize(360, 200)
        layout = QVBoxLayout(dlg)
        
        layout.addWidget(QLabel("請選擇欲翻譯的目標語言："))
        
        combo = QComboBox()
        langs = [
            ("英文 (English)", "英文"),
            ("繁體中文 (Traditional Chinese)", "繁體中文"),
            ("簡體中文 (Simplified Chinese)", "簡體中文"),
            ("日文 (Japanese)", "日文"),
            ("韓文 (Korean)", "韓文"),
            ("法文 (French)", "法文"),
            ("德文 (German)", "德文"),
            ("西班牙文 (Spanish)", "西班牙文")
        ]
        for label, val in langs:
            combo.addItem(label, val)
        layout.addWidget(combo)
        
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("開始 AI 翻譯")
        ok_btn.setObjectName("PrimaryButton")
        cancel_btn = QPushButton("取消")
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(ok_btn)
        layout.addLayout(btn_box)
        
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            target_lang = combo.currentData()
            self.start_translation(target_lang)

    def start_translation(self, target_lang: str):
        config = self.config_manager.get_all()
        
        provider = config.get("llm_provider", "gemini")
        if provider == "gemini":
            if not config.get("gemini_api_key"):
                QMessageBox.warning(
                    self, "缺少 API Key", 
                    "請先在「全域設定」分頁中設定 Gemini API Key 才能使用 AI 翻譯功能喔！"
                )
                return
        else:
            if not config.get("openai_api_key"):
                QMessageBox.warning(
                    self, "缺少 API Key", 
                    "請先在「全域設定」分頁中設定 OpenAI API Key 才能使用 AI 翻譯功能喔！"
                )
                return
        
        self.progress_dialog = QProgressDialog(f"正在準備 AI 翻譯 ({target_lang})...", "取消", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()
        
        self.translator_worker = LLMTranslatorWorker(self.items, target_lang, config)
        self.translator_worker.progress_changed.connect(self.progress_dialog.setValue)
        self.translator_worker.status_changed.connect(self.progress_dialog.setLabelText)
        
        def on_finished(translated_items):
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
            cmd = BatchReplaceItemsCommand(self, f"AI 字幕翻譯 ({target_lang})", self.items, translated_items)
            self.undo_stack.push(cmd)
            QMessageBox.information(self, "翻譯完成", f"已成功完成【{target_lang}】字幕翻譯！")
            
        def on_error(err_msg):
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
            QMessageBox.critical(self, "翻譯失敗", f"AI 翻譯時發生錯誤：\n{err_msg}")
            
        self.translator_worker.finished_translating.connect(on_finished)
        self.translator_worker.error_occurred.connect(on_error)
        self.progress_dialog.canceled.connect(self.translator_worker.cancel)
        
        self.translator_worker.start()

    # 搜尋與取代
    def search_text(self):
        query = self.search_input.text().strip()
        if not query:
            return
            
        selected_ranges = self.table.selectedRanges()
        start_row = selected_ranges[0].topRow() + 1 if selected_ranges else 0
        
        found = False
        for r in range(start_row, len(self.items)):
            if query.lower() in self.items[r].text.lower() or query.lower() in self.items[r].translation.lower():
                self.table.selectRow(r)
                self.table.scrollToItem(self.table.item(r, 0))
                found = True
                break
                
        if not found and start_row > 0:
            for r in range(0, start_row):
                if query.lower() in self.items[r].text.lower() or query.lower() in self.items[r].translation.lower():
                    self.table.selectRow(r)
                    self.table.scrollToItem(self.table.item(r, 0))
                    found = True
                    break
                    
        if not found:
            QMessageBox.information(self, "尋找結果", f"找不到「{query}」")

    def replace_text(self):
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return
            
        row = selected_ranges[0].topRow()
        query = self.search_input.text().strip()
        replace = self.replace_input.text()
        
        if row < len(self.items) and query:
            import re
            insens_re = re.compile(re.escape(query), re.IGNORECASE)
            
            old_item = copy.deepcopy(self.items[row])
            new_item = copy.deepcopy(self.items[row])
            
            changed = False
            if query.lower() in new_item.text.lower():
                new_item.text = insens_re.sub(replace, new_item.text)
                changed = True
            if query.lower() in new_item.translation.lower():
                new_item.translation = insens_re.sub(replace, new_item.translation)
                changed = True
                
            if changed:
                old_items = copy.deepcopy(self.items)
                new_items = copy.deepcopy(self.items)
                new_items[row] = new_item
                cmd = BatchReplaceItemsCommand(self, "搜尋取代文字", old_items, new_items)
                self.undo_stack.push(cmd)
                self.search_text()

    def replace_all_text(self):
        query = self.search_input.text().strip()
        replace = self.replace_input.text()
        if not query:
            return
            
        reply = QMessageBox.question(
            self, "確認替換", f"是否將所有「{query}」替換為「{replace}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            import re
            insens_re = re.compile(re.escape(query), re.IGNORECASE)
            
            old_items = copy.deepcopy(self.items)
            new_items = copy.deepcopy(self.items)
            count = 0
            
            for row in range(len(new_items)):
                item_text = new_items[row].text
                item_trans = new_items[row].translation
                c1, c2 = False, False
                if query.lower() in item_text.lower():
                    new_items[row].text = insens_re.sub(replace, item_text)
                    c1 = True
                if query.lower() in item_trans.lower():
                    new_items[row].translation = insens_re.sub(replace, item_trans)
                    c2 = True
                if c1 or c2:
                    count += 1
            
            if count > 0:
                cmd = BatchReplaceItemsCommand(self, "全部替換文字", old_items, new_items)
                self.undo_stack.push(cmd)
                QMessageBox.information(self, "替換完畢", f"成功替換了 {count} 處文字。")
            else:
                QMessageBox.information(self, "替換完畢", "未找到符合的文字。")

    # 匯出字幕 (支援雙語合一與多檔案匯出)
    def export_subtitles(self):
        if not self.items:
            return
            
        has_translation = any(item.translation.strip() for item in self.items)
        export_mode = "original"
        export_split_files = False
        
        if has_translation:
            dlg = QDialog(self)
            dlg.setWindowTitle("📤 選擇雙語字幕匯出模式")
            dlg.resize(400, 260)
            vbox = QVBoxLayout(dlg)
            vbox.addWidget(QLabel("檢測到已包含翻譯字幕，請選擇欲匯出的模式："))
            
            bg = QButtonGroup(dlg)
            r1 = QRadioButton("雙語合一字幕 (原文在上，譯文在下)")
            r2 = QRadioButton("雙語合一字幕 (譯文在上，原文在下)")
            r3 = QRadioButton("僅匯出原文檔")
            r4 = QRadioButton("僅匯出譯文檔")
            r5 = QRadioButton("拆分匯出 2 個單語檔 (如 filename_orig.srt 與 filename_trans.srt)")
            
            r1.setChecked(True)
            bg.addButton(r1, 1)
            bg.addButton(r2, 2)
            bg.addButton(r3, 3)
            bg.addButton(r4, 4)
            bg.addButton(r5, 5)
            
            vbox.addWidget(r1)
            vbox.addWidget(r2)
            vbox.addWidget(r3)
            vbox.addWidget(r4)
            vbox.addWidget(r5)
            
            btn_box = QHBoxLayout()
            ok_btn = QPushButton("確認匯出")
            ok_btn.setObjectName("PrimaryButton")
            cancel_btn = QPushButton("取消")
            btn_box.addWidget(cancel_btn)
            btn_box.addWidget(ok_btn)
            vbox.addLayout(btn_box)
            
            ok_btn.clicked.connect(dlg.accept)
            cancel_btn.clicked.connect(dlg.reject)
            
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
                
            choice = bg.checkedId()
            if choice == 1:
                export_mode = "bilingual_top_orig"
            elif choice == 2:
                export_mode = "bilingual_top_trans"
            elif choice == 3:
                export_mode = "original"
            elif choice == 4:
                export_mode = "translation"
            elif choice == 5:
                export_split_files = True

        default_dir = self.config_manager.get("export_dir", "")
        if not default_dir:
            default_dir = os.path.dirname(self.media_file)
            
        media_basename = os.path.splitext(os.path.basename(self.media_file))[0]
        default_save_path = os.path.join(default_dir, f"{media_basename}.srt")

        save_path, _ = QFileDialog.getSaveFileName(
            self, "匯出字幕檔案", default_save_path,
            "SubRip 字幕檔 (*.srt);;WebGL 網頁字幕檔 (*.vtt);;純文字檔 (*.txt)"
        )
        
        if save_path:
            try:
                if export_split_files:
                    base_path, ext = os.path.splitext(save_path)
                    orig_path = f"{base_path}_orig{ext}"
                    trans_path = f"{base_path}_trans{ext}"
                    SubtitleParser.save_subtitles(self.items, orig_path, mode="original")
                    SubtitleParser.save_subtitles(self.items, trans_path, mode="translation")
                    QMessageBox.information(self, "匯出成功", f"已成功分開儲存為 2 個單語檔：\n1. {orig_path}\n2. {trans_path}")
                else:
                    SubtitleParser.save_subtitles(self.items, save_path, mode=export_mode)
                    QMessageBox.information(self, "匯出成功", f"字幕已成功儲存至：\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "匯出失敗", f"無法儲存字幕：\n{e}")

    def closeEvent(self, event):
        self.stop_play()
        if self.audio_file and self.audio_file != self.media_file:
            try:
                if os.path.exists(self.audio_file):
                    os.remove(self.audio_file)
            except Exception:
                pass
        event.accept()
