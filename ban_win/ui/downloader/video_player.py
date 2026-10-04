"""
Widget xem trước video đã tải bằng QMediaPlayer nhúng hoặc mở trình phát mặc định hệ thống.
"""
import os
import subprocess
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSlider
)
from qfluentwidgets import PrimaryPushButton, PushButton, FluentIcon, SubtitleLabel

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    MULTIMEDIA_AVAILABLE = False


class VideoPlayerDialog(QDialog):
    def __init__(self, video_path: str, title: str = "Xem trước video", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 520)
        self.video_path = video_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        lbl_t = SubtitleLabel(title, self)
        header.addWidget(lbl_t)
        header.addStretch()
        layout.addLayout(header)

        if MULTIMEDIA_AVAILABLE and os.path.isfile(video_path):
            self.video_widget = QVideoWidget(self)
            self.video_widget.setStyleSheet("background-color: #000000; border-radius: 8px;")
            layout.addWidget(self.video_widget, 1)

            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.player.setAudioOutput(self.audio_output)
            self.player.setVideoOutput(self.video_widget)

            # Controls
            ctrl_box = QHBoxLayout()
            self.btn_play = PushButton(FluentIcon.PLAY, "Phát", self)
            self.btn_play.clicked.connect(self._toggle_playback)
            ctrl_box.addWidget(self.btn_play)

            self.slider = QSlider(Qt.Horizontal, self)
            self.slider.sliderMoved.connect(self._set_position)
            ctrl_box.addWidget(self.slider, 1)

            layout.addLayout(ctrl_box)

            self.player.positionChanged.connect(self._on_pos_changed)
            self.player.durationChanged.connect(self._on_dur_changed)
            self.player.setSource(QUrl.fromLocalFile(video_path))
            self.player.play()
            self.btn_play.setIcon(FluentIcon.PAUSE)
            self.btn_play.setText("Tạm dừng")
        else:
            fallback_box = QVBoxLayout()
            fallback_lbl = QLabel(f"Đường dẫn file: {video_path}\nBấm nút bên dưới để mở bằng trình phát video mặc định.", self)
            fallback_lbl.setAlignment(Qt.AlignCenter)
            fallback_lbl.setStyleSheet("color: #475569; font-size: 14px; padding: 40px;")
            fallback_box.addWidget(fallback_lbl)

            btn_open_ext = PrimaryPushButton(FluentIcon.PLAY, "Mở bằng trình phát Windows", self)
            btn_open_ext.clicked.connect(lambda: subprocess.Popen(f'explorer /select,"{video_path}"') if os.path.isfile(video_path) else None)
            fallback_box.addWidget(btn_open_ext, alignment=Qt.AlignCenter)
            layout.addLayout(fallback_box, 1)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        btn_close = PushButton("Đóng", self)
        btn_close.clicked.connect(self._on_close)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def _toggle_playback(self):
        if not MULTIMEDIA_AVAILABLE:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setIcon(FluentIcon.PLAY)
            self.btn_play.setText("Phát")
        else:
            self.player.play()
            self.btn_play.setIcon(FluentIcon.PAUSE)
            self.btn_play.setText("Tạm dừng")

    def _on_pos_changed(self, pos: int):
        self.slider.setValue(pos)

    def _on_dur_changed(self, dur: int):
        self.slider.setRange(0, dur)

    def _set_position(self, pos: int):
        if MULTIMEDIA_AVAILABLE:
            self.player.setPosition(pos)

    def _on_close(self):
        if MULTIMEDIA_AVAILABLE and hasattr(self, "player"):
            self.player.stop()
        self.accept()

    def closeEvent(self, event):
        if MULTIMEDIA_AVAILABLE and hasattr(self, "player"):
            self.player.stop()
        super().closeEvent(event)
