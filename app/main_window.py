from __future__ import annotations
import bisect
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton, QSlider, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QDoubleSpinBox
)

from .alignment import align_untimed_to_base, align_untimed_to_duration
from .formats import load_track, fmt_time, to_srt, to_vtt
from .html_export import export_html_package
from .models import TextTrack
from .project import load_project, save_project

AUDIO_FILTER = "音訊 (*.m4a *.mp3 *.wav *.aac *.flac *.ogg *.wma *.mp4);;所有檔案 (*.*)"
TRACK_FILTER = "逐字稿/字幕 (*.srt *.vtt *.txt *.json *.csv *.docx *.html *.htm);;所有檔案 (*.*)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("峻爸 KTV 多文字軌核對器 v1.0")
        self.resize(1280, 820)
        self.audio_path = ""
        self.tracks: list[TextTrack] = []
        self._ranges = []
        self._last_index = -1

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.9)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.playbackStateChanged.connect(self._state_changed)
        self.player.errorOccurred.connect(self._player_error)

        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # Audio
        g_audio = QGroupBox("1. 錄音檔")
        la = QHBoxLayout(g_audio)
        self.audio_label = QLabel("尚未選擇錄音檔"); self.audio_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        b_audio = QPushButton("選擇錄音檔"); b_audio.clicked.connect(self.choose_audio)
        la.addWidget(self.audio_label, 1); la.addWidget(b_audio)
        layout.addWidget(g_audio)

        # Tracks
        g_tracks = QGroupBox("2. 多文字軌（可讀本程式或其他軟體輸出的文字）")
        lt = QVBoxLayout(g_tracks)
        top = QHBoxLayout()
        for text, cb in [("加入文字/字幕", self.add_tracks), ("移除選取", self.remove_track), ("自動對齊未定時文字", self.align_tracks)]:
            b=QPushButton(text); b.clicked.connect(cb); top.addWidget(b)
        top.addStretch(1)
        lt.addLayout(top)
        self.track_table = QTableWidget(0, 5)
        self.track_table.setHorizontalHeaderLabels(["名稱", "格式", "時間軸", "對齊精度", "來源"])
        self.track_table.horizontalHeader().setStretchLastSection(True)
        self.track_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.track_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.track_table.itemChanged.connect(self._track_item_changed)
        lt.addWidget(self.track_table)
        layout.addWidget(g_tracks)

        # Player controls
        ctrl = QHBoxLayout()
        self.play_btn = QPushButton("▶ 播放"); self.play_btn.clicked.connect(self.toggle_play)
        back = QPushButton("↶ 5秒"); back.clicked.connect(lambda: self.seek_delta(-5000))
        fwd = QPushButton("5秒 ↷"); fwd.clicked.connect(lambda: self.seek_delta(5000))
        self.pos_label = QLabel("00:00:00 / 00:00:00")
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(0, 0); self.slider.sliderMoved.connect(self.player.setPosition)
        self.speed = QComboBox(); self.speed.addItems(["0.75x","1.0x","1.25x","1.5x","2.0x"]); self.speed.setCurrentText("1.0x"); self.speed.currentTextChanged.connect(self._speed_changed)
        ctrl.addWidget(self.play_btn); ctrl.addWidget(back); ctrl.addWidget(fwd); ctrl.addWidget(self.pos_label); ctrl.addWidget(self.slider, 1); ctrl.addWidget(QLabel("速度")); ctrl.addWidget(self.speed)
        layout.addLayout(ctrl)

        # Track selectors
        sel = QHBoxLayout()
        self.active_combo = QComboBox(); self.active_combo.currentIndexChanged.connect(self.rebuild_views)
        self.compare_combo = QComboBox(); self.compare_combo.currentIndexChanged.connect(self.rebuild_views)
        sel.addWidget(QLabel("上方 KTV 文字軌")); sel.addWidget(self.active_combo, 1)
        sel.addWidget(QLabel("下方比較文字軌")); sel.addWidget(self.compare_combo, 1)
        layout.addLayout(sel)

        splitter = QSplitter(Qt.Vertical)
        # KTV full text
        self.full_text = QTextEdit(); self.full_text.setReadOnly(True); self.full_text.setPlaceholderText("完整全文會顯示在這裡；播放時目前句段會像 KTV 一樣反白。")
        self.full_text.setStyleSheet("QTextEdit { font-size: 18px; line-height: 1.7; }")
        splitter.addWidget(self.full_text)
        # Timeline
        self.timeline = QTableWidget(0, 5)
        self.timeline.setHorizontalHeaderLabels(["開始", "結束", "講者", "目前文字軌", "比較文字軌"])
        self.timeline.horizontalHeader().setStretchLastSection(True)
        self.timeline.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.timeline.cellDoubleClicked.connect(self._timeline_seek)
        splitter.addWidget(self.timeline)
        splitter.setSizes([360, 300])
        layout.addWidget(splitter, 1)

        # Export/project
        foot = QHBoxLayout()
        for text, cb in [
            ("開啟專案", self.open_project), ("儲存專案", self.save_project),
            ("匯出目前軌 SRT", lambda: self.export_track("srt")), ("匯出目前軌 VTT", lambda: self.export_track("vtt")),
            ("產生離線 KTV 網頁包", self.export_html),
        ]:
            b=QPushButton(text); b.clicked.connect(cb); foot.addWidget(b)
        foot.addStretch(1)
        layout.addLayout(foot)

    def choose_audio(self):
        p, _ = QFileDialog.getOpenFileName(self, "選擇錄音檔", "", AUDIO_FILTER)
        if not p: return
        self.audio_path = p
        self.audio_label.setText(p)
        self.player.setSource(QUrl.fromLocalFile(p))

    def add_tracks(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "加入文字/字幕", "", TRACK_FILTER)
        for p in paths:
            try:
                tr = load_track(p)
                self.tracks.append(tr)
            except Exception as e:
                QMessageBox.warning(self, "讀取失敗", f"{Path(p).name}\n{e}")
        self.refresh_tracks()
        self.align_tracks(auto_only=True)

    def remove_track(self):
        rows = sorted({x.row() for x in self.track_table.selectedItems()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.tracks): self.tracks.pop(r)
        self.refresh_tracks()

    def refresh_tracks(self):
        self.track_table.blockSignals(True)
        self.track_table.setRowCount(len(self.tracks))
        for r,t in enumerate(self.tracks):
            vals=[t.name,t.format_name,"有" if t.timed else "無","估算" if t.estimated else "原始時間碼",t.source_path]
            for c,v in enumerate(vals): self.track_table.setItem(r,c,QTableWidgetItem(v))
        self.track_table.blockSignals(False)
        active = self.active_combo.currentIndex()
        comp = self.compare_combo.currentIndex()-1
        self.active_combo.blockSignals(True); self.compare_combo.blockSignals(True)
        self.active_combo.clear(); self.compare_combo.clear(); self.compare_combo.addItem("不比較")
        for t in self.tracks:
            suffix="（估算）" if t.estimated else ""
            self.active_combo.addItem(t.name+suffix); self.compare_combo.addItem(t.name+suffix)
        if self.tracks: self.active_combo.setCurrentIndex(min(max(active,0),len(self.tracks)-1))
        if comp >= 0: self.compare_combo.setCurrentIndex(min(comp+1,len(self.tracks)))
        self.active_combo.blockSignals(False); self.compare_combo.blockSignals(False)
        self.rebuild_views()

    def _track_item_changed(self, item):
        if item.column()==0 and 0<=item.row()<len(self.tracks):
            self.tracks[item.row()].name=item.text().strip() or self.tracks[item.row()].name
            self.refresh_tracks()

    def _base_track(self):
        return next((t for t in self.tracks if t.timed and not t.estimated and t.segments), next((t for t in self.tracks if t.timed and t.segments), None))

    def align_tracks(self, auto_only=False):
        if not self.tracks: return
        base = self._base_track()
        duration = self.player.duration()/1000.0 if self.player.duration()>0 else 0.0
        changed=False
        for i,t in enumerate(list(self.tracks)):
            if t.timed: continue
            if base and base is not t:
                self.tracks[i]=align_untimed_to_base(t,base); changed=True
            elif duration>0:
                self.tracks[i]=align_untimed_to_duration(t,duration); changed=True
        if changed: self.refresh_tracks()
        elif not auto_only:
            QMessageBox.information(self,"對齊","目前沒有需要對齊的未定時文字，或尚未載入可用時間軸/音訊長度。")

    def rebuild_views(self):
        self._ranges=[]; self._last_index=-1
        if not self.tracks or self.active_combo.currentIndex()<0:
            self.full_text.clear(); self.timeline.setRowCount(0); return
        tr=self.tracks[self.active_combo.currentIndex()]
        self.full_text.clear(); cur=self.full_text.textCursor()
        for s in tr.segments:
            start=cur.position(); cur.insertText(s.text.strip()+" "); end=cur.position(); self._ranges.append((start,end))
        self.full_text.setTextCursor(QTextCursor(self.full_text.document()))
        comp_idx=self.compare_combo.currentIndex()-1
        comp=self.tracks[comp_idx] if 0<=comp_idx<len(self.tracks) else None
        self.timeline.setRowCount(len(tr.segments))
        for r,s in enumerate(tr.segments):
            other = ""
            if comp and comp.segments:
                mid = (s.start + s.end) / 2 if s.end > s.start else s.start
                match = next((x for x in comp.segments if x.start <= mid < max(x.end, x.start + 0.05)), None)
                if match is None:
                    match = min(comp.segments, key=lambda x: abs(x.start - mid))
                other = match.text
            vals=[fmt_time(s.start)[:8],fmt_time(s.end)[:8],s.speaker,s.text,other]
            for c,v in enumerate(vals):
                it=QTableWidgetItem(v); it.setData(Qt.UserRole,s.start); self.timeline.setItem(r,c,it)
        self.timeline.resizeColumnsToContents(); self.timeline.horizontalHeader().setStretchLastSection(True)
        self._position_changed(self.player.position())

    def toggle_play(self):
        if not self.audio_path:
            QMessageBox.information(self,"尚未選擇音訊","請先選擇錄音檔。")
            return
        if self.player.playbackState()==QMediaPlayer.PlayingState: self.player.pause()
        else: self.player.play()

    def seek_delta(self, ms): self.player.setPosition(max(0,min(self.player.duration(),self.player.position()+ms)))
    def _state_changed(self,state): self.play_btn.setText("⏸ 暫停" if state==QMediaPlayer.PlayingState else "▶ 播放")
    def _duration_changed(self,d): self.slider.setRange(0,max(0,d)); self.align_tracks(auto_only=True)
    def _speed_changed(self,s): self.player.setPlaybackRate(float(s.rstrip('x')))
    def _player_error(self,*_):
        if self.player.error()!=QMediaPlayer.NoError:
            self.statusBar().showMessage("播放器無法直接開啟此音訊格式；可先用其他工具轉 WAV/MP3 後再載入。",10000)

    def _position_changed(self,ms):
        self.slider.blockSignals(True); self.slider.setValue(ms); self.slider.blockSignals(False)
        self.pos_label.setText(f"{fmt_time(ms/1000)[:8]} / {fmt_time(self.player.duration()/1000)[:8]}")
        if not self.tracks or self.active_combo.currentIndex()<0: return
        tr=self.tracks[self.active_combo.currentIndex()]
        now=ms/1000.0
        starts=[s.start for s in tr.segments]
        i=bisect.bisect_right(starts,now)-1
        if i<0 or i>=len(tr.segments): return
        seg=tr.segments[i]
        if seg.end>seg.start and now>seg.end and i+1<len(tr.segments): return
        self._highlight(i,now)

    def _highlight(self,i,now):
        if i>=len(self._ranges): return
        start,end=self._ranges[i]
        seg=self.tracks[self.active_combo.currentIndex()].segments[i]
        p=max(0.0,min(1.0,(now-seg.start)/max(.08,seg.end-seg.start))) if seg.end>seg.start else 1.0
        mid=start+int((end-start)*p)
        sels=[]
        # Whole current sentence
        c=QTextCursor(self.full_text.document()); c.setPosition(start); c.setPosition(end,QTextCursor.KeepAnchor)
        s=self.full_text.ExtraSelection(); s.cursor=c; f=QTextCharFormat(); f.setBackground(QColor("#665500")); s.format=f; sels.append(s)
        # KTV progressed prefix
        c2=QTextCursor(self.full_text.document()); c2.setPosition(start); c2.setPosition(mid,QTextCursor.KeepAnchor)
        s2=self.full_text.ExtraSelection(); s2.cursor=c2; f2=QTextCharFormat(); f2.setBackground(QColor("#ffd54f")); f2.setForeground(QColor("#111111")); s2.format=f2; sels.append(s2)
        self.full_text.setExtraSelections(sels)
        if i!=self._last_index:
            self.timeline.selectRow(i)
            self.timeline.scrollToItem(self.timeline.item(i,0),QAbstractItemView.PositionAtCenter)
            c3=QTextCursor(self.full_text.document()); c3.setPosition(start); self.full_text.setTextCursor(c3); self.full_text.ensureCursorVisible()
            self._last_index=i

    def _timeline_seek(self,row,col):
        it=self.timeline.item(row,0)
        if it: self.player.setPosition(int(float(it.data(Qt.UserRole) or 0)*1000)); self.player.play()

    def save_project(self):
        p,_=QFileDialog.getSaveFileName(self,"儲存 KTV 專案","峻爸_KTV專案.jktv","峻爸 KTV 專案 (*.jktv)")
        if p: save_project(p,self.audio_path,self.tracks,self.active_combo.currentIndex(),self.compare_combo.currentIndex()-1)
    def open_project(self):
        p,_=QFileDialog.getOpenFileName(self,"開啟 KTV 專案","","峻爸 KTV 專案 (*.jktv)")
        if not p:return
        try:
            audio,tracks,a,c=load_project(p); self.audio_path=audio; self.tracks=tracks
            self.audio_label.setText(audio or "尚未指定錄音檔")
            if audio and Path(audio).exists(): self.player.setSource(QUrl.fromLocalFile(audio))
            self.refresh_tracks();
            if tracks: self.active_combo.setCurrentIndex(max(0,min(a,len(tracks)-1)))
            self.compare_combo.setCurrentIndex(c+1 if 0<=c<len(tracks) else 0)
        except Exception as e: QMessageBox.critical(self,"專案讀取失敗",str(e))

    def export_track(self,kind):
        if not self.tracks or self.active_combo.currentIndex()<0:return
        tr=self.tracks[self.active_combo.currentIndex()]
        ext=kind.lower(); p,_=QFileDialog.getSaveFileName(self,"匯出文字軌",f"{tr.name}.{ext}",f"{ext.upper()} (*.{ext})")
        if p: Path(p).write_text(to_srt(tr) if ext=="srt" else to_vtt(tr),encoding="utf-8")

    def export_html(self):
        if not self.audio_path or not self.tracks:
            QMessageBox.information(self,"資料不足","請先選擇錄音檔並加入至少一個文字軌。")
            return
        out=QFileDialog.getExistingDirectory(self,"選擇 KTV 網頁包輸出資料夾")
        if not out:return
        try:
            p=export_html_package(out,self.audio_path,self.tracks)
            QMessageBox.information(self,"完成",f"已建立離線核對網頁：\n{p}")
            if sys.platform.startswith("win"): os.startfile(str(p))
            else: subprocess.Popen(["xdg-open",str(p)])
        except Exception as e: QMessageBox.critical(self,"匯出失敗",str(e))
