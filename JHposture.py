import sys
import os
import cv2
import tracker
import analyser
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTreeView, QFileSystemModel, QLabel, QFileDialog, 
    QSplitter, QTextEdit, QProgressBar, QMessageBox, QFrame, QSlider, 
    QSizePolicy, QInputDialog, QDialog, QCheckBox, QMenu
)
from PyQt5.QtCore import Qt, QDir, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap

# =============================================================================
# TRANSLATIONS
# =============================================================================
# =============================================================================
# TRANSLATIONS
# =============================================================================
LANG = {
    "en": {
        "browse": "Browse SSD / Folder",
        "no_dir": "No directory selected",
        "ready": "Ready to process.",
        "selected": "Selected: {file}",
        "btn_track": "1. RUN TRACKING",
        "btn_analyse": "2. RUN BEHAVIOURAL ANALYSIS",
        "warn_title": "Warning",
        "err_title": "Error",
        "warn_no_file": "Please select a video file first.",
        "warn_no_csv": "No tracking data found for this video. Please run tracking first.",
        "warn_no_joint": "You must select at least one joint pair.",
        "overwrite_title": "Overwrite Data?",
        "overwrite_msg": "Data already exists for:\n{file}\n\nDo you want to overwrite it?",
        "overwrite_analysis_title": "Overwrite Analysis Data?",
        "overwrite_analysis_msg": "Analysis graphs and videos already exist for:\n{file}\n\nDo you want to overwrite them?",
        "speed_title": "Processing Speed",
        "speed_msg": "Process every Nth frame\n(1 = Slowest/Highest Fidelity, 3 = Balanced, 10 = Fastest):\n\nNote: This sets the baseline FPS for analysis filtering.",
        "del_menu": "Delete File",
        "del_title": "Confirm Delete",
        "delete_confirm": "Are you sure you want to permanently delete:\n{file}?",
        "del_err": "Could not delete file:\n{err}",
        "joint_title": "Select Interpersonal Links",
        "joint_desc": "Select which cross-body distances to track:",
        "btn_ok": "Analyse",
        "btn_lang": "🇰🇷 한국어로 변경"
    },
    "ko": {
        "browse": "SSD / 폴더 찾아보기",
        "no_dir": "선택된 디렉토리 없음",
        "ready": "처리 준비 완료.",
        "selected": "선택됨: {file}",
        "btn_track": "1. 트래킹 실행",
        "btn_analyse": "2. 행동 분석 실행",
        "warn_title": "경고",
        "err_title": "오류",
        "warn_no_file": "먼저 비디오 파일을 선택해 주세요.",
        "warn_no_csv": "이 비디오의 트래킹 데이터를 찾을 수 없습니다. 먼저 트래킹을 실행해 주세요.",
        "warn_no_joint": "최소 하나 이상의 관절 쌍을 선택해야 합니다.",
        "overwrite_title": "데이터 덮어쓰기?",
        "overwrite_msg": "다음 파일의 데이터가 이미 존재합니다:\n{file}\n\n덮어쓰시겠습니까?",
        "overwrite_analysis_title": "분석 데이터 덮어쓰기?",
        "overwrite_analysis_msg": "다음 파일의 분석 그래프와 비디오가 이미 존재합니다:\n{file}\n\n덮어쓰시겠습니까?",
        "speed_title": "처리 속도",
        "speed_msg": "N번째 프레임마다 처리\n(1 = 가장 느림/최고 품질, 3 = 균형, 10 = 가장 빠름):\n\n참고: 이것은 분석 필터링의 기준 FPS를 설정합니다.",
        "del_menu": "파일 삭제",
        "del_title": "삭제 확인",
        "delete_confirm": "다음을 영구적으로 삭제하시겠습니까:\n{file}?",
        "del_err": "파일을 삭제할 수 없습니다:\n{err}",
        "joint_title": "대인 간 링크 선택",
        "joint_desc": "추적할 교차 신체 거리를 선택하세요:",
        "btn_ok": "분석 실행",
        "btn_lang": "🇬🇧 Switch to English"
    }
}

# =============================================================================
# MODULAR WORKER THREAD
# =============================================================================
class JointSelectionDialog(QDialog):
    def __init__(self, t, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t["joint_title"])
        self.setFixedSize(300, 250)
        self.setStyleSheet("background-color: #f2f1ec; color: #222222;")
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(t["joint_desc"]))
        
        self.checkboxes = {}
        categories = ["Nose", "Shoulders", "Elbows", "Wrists", "Hips", "Ankles"]
        
        for cat in categories:
            chk = QCheckBox(cat)
            chk.setChecked(True)
            layout.addWidget(chk)
            self.checkboxes[cat] = chk
            
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(t["btn_ok"])
        btn_ok.setStyleSheet("background-color: #6184D8; color: white; font-weight: bold;")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def get_selected(self):
        return [cat for cat, chk in self.checkboxes.items() if chk.isChecked()]

class ProcessingWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, file_path, frame_skip):
        super().__init__()
        self.file_path = file_path
        self.frame_skip = frame_skip # <-- Added

    def run(self):
        try:
            pose_tracker = tracker.JHTracker()
            def update_gui(percent, message):
                scaled_percent = 5 + int(percent * 0.85)
                self.progress.emit(scaled_percent, message)

            # Pass the frame_skip variable into the tracker
            output_csv_path = pose_tracker.process_video(self.file_path, frame_skip=self.frame_skip, progress_callback=update_gui)
            self.finished.emit(True, "Successfully generated output CSV.")
        except Exception as e:
            self.finished.emit(False, str(e))

class AnalysisWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, video_path, selected_joints):
        super().__init__()
        self.video_path = video_path
        self.selected_joints = selected_joints # <-- Added

    def run(self):
        try:
            csv_path = os.path.splitext(self.video_path)[0] + "_tracking_data.csv"
            data_analyser = analyser.BehavioAnalyser()
            
            def update_gui(percent, message):
                self.progress.emit(percent, message)
                
            # Pass the selected joints into the analyser
            graph_path, vid_path = data_analyser.run_analysis(self.video_path, csv_path, self.selected_joints, progress_callback=update_gui)
            
            self.finished.emit(True, "Successfully generated kinematic data.")
        except Exception as e:
            self.finished.emit(False, str(e))

# =============================================================================
# STREAMING VIDEO PLAYER (Disk-Based for Long Videos)
# =============================================================================
class StreamingVideoPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.cap = None
        self.total_frames = 0
        self.current_frame = 0
        self.playing = False
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._timer_tick)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Video Display
        self.video_label = QLabel("No Video Loaded")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #000000; color: #ffffff; border-radius: 4px;")
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setMinimumSize(100, 100)
        layout.addWidget(self.video_label, 1) # '1' makes it expand to fill space
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedWidth(40)
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.toggle_play)
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.sliderMoved.connect(self.seek)
        
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.slider)
        
        layout.addLayout(controls_layout)

    def load_video(self, path):
        self.stop()
        if self.cap:
            self.cap.release()
            
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            self.video_label.setText("Error loading video.")
            return

        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps == 0: fps = 30
        
        self.timer.setInterval(int(1000 / fps))
        self.slider.setRange(0, max(0, self.total_frames - 1))
        
        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        
        self.show_frame(0)

    def show_frame(self, idx):
        if not self.cap: return
        
        # If the requested frame is not the next sequential frame, we must seek
        if idx != self.current_frame + 1:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            
        ret, frame = self.cap.read()
        if not ret:
            self.stop()
            return
            
        self.current_frame = idx
        
        # Update Slider silently
        self.slider.blockSignals(True)
        self.slider.setValue(idx)
        self.slider.blockSignals(False)

        # Convert OpenCV BGR to PyQt RGB
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        # Scale to fit label
        self.video_label.setPixmap(pixmap.scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def toggle_play(self):
        self.playing = not self.playing
        if self.playing:
            self.btn_play.setText("||")
            self.timer.start()
        else:
            self.btn_play.setText("▶")
            self.timer.stop()

    def _timer_tick(self):
        if self.current_frame < self.total_frames - 1:
            self.show_frame(self.current_frame + 1)
        else:
            self.stop() # Auto-stop at end of video

    def seek(self, val):
        self.show_frame(val)

    def stop(self):
        self.playing = False
        self.timer.stop()
        self.btn_play.setText("▶")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.cap and not self.playing:
            # Refresh the current frame to scale it to the new window size
            self.show_frame(self.current_frame)

# =============================================================================
# MAIN GUI
# =============================================================================
class JHposeGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JHposture - Behavioural Tracking")
        self.resize(1200, 750) # Made slightly wider to accommodate 3 panels
        self._apply_theme()
        self._init_ui()
        self.selected_file = None

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #f2f1ec; color: #222222; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QPushButton { background-color: #e0e0e0; color: #000; border: 1px solid #bbb; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #d0d0d0; border-color: #aaa; }
            QPushButton:disabled { background-color: #f0f0f0; color: #aaa; border-color: #ddd; }
            QPushButton#AccentButton { background-color: #6184D8; color: white; border: 1px solid #6184D8; }
            QPushButton#AccentButton:hover { background-color: #4f6cb3; }
            QTreeView { background-color: #ffffff; border: 1px solid #cccccc; color: #222222; outline: 0; }
            QTreeView::item:selected { background-color: #e0e0e0; color: #000; }
            QTextEdit { background-color: #ffffff; border: 1px solid #cccccc; font-family: 'Consolas', monospace; color: #222222; }
            QSplitter::handle { background-color: #cccccc; }
        """)

    def _init_ui(self):
        self.current_lang = "en"

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Top Bar ---
        top_bar = QHBoxLayout()
        self.lbl_current_dir = QLabel(LANG[self.current_lang]["no_dir"])
        self.lbl_current_dir.setStyleSheet("color: #666; background-color: transparent;")
        
        self.btn_browse = QPushButton(LANG[self.current_lang]["browse"])
        self.btn_browse.clicked.connect(self._browse_directory)
        
        # --- Language Toggle Button ---
        self.btn_lang_toggle = QPushButton(LANG[self.current_lang]["btn_lang"])
        self.btn_lang_toggle.setStyleSheet("""
            QPushButton {
                background-color: #ffffff; 
                border: 1px solid #6184D8; 
                color: #6184D8; 
                border-radius: 4px; 
                padding: 4px 12px; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e6ebf7;
            }
        """)
        self.btn_lang_toggle.clicked.connect(self._toggle_language)
        
        top_bar.addWidget(self.btn_browse)
        top_bar.addWidget(self.lbl_current_dir, 1)
        top_bar.addWidget(self.btn_lang_toggle)
        layout.addLayout(top_bar)

        # --- Main Splitter (3 Panels) ---
        splitter = QSplitter(Qt.Horizontal)
        
        # 1. Left: File Explorer
        self.file_model = QFileSystemModel()
        self.file_model.setNameFilters(["*.mp4", "*.avi", "*.mov"])
        self.file_model.setNameFilterDisables(False)
        self.file_model.setFilter(QDir.Files | QDir.Dirs | QDir.NoDotAndDotDot)
        
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.hideColumn(1); self.tree.hideColumn(2); self.tree.hideColumn(3)
        self.tree.clicked.connect(self._on_file_selected)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._open_context_menu)
        splitter.addWidget(self.tree)

        # 2. Center: Video Player
        video_panel = QFrame()
        video_panel.setStyleSheet("background-color: #ffffff; border: 1px solid #cccccc; border-radius: 4px;")
        video_layout = QVBoxLayout(video_panel)
        self.video_player = StreamingVideoPlayer()
        video_layout.addWidget(self.video_player)
        splitter.addWidget(video_panel)

        # 3. Right: Controls & Logs
        right_panel = QFrame()
        right_panel.setStyleSheet("QFrame { background-color: #ffffff; border: 1px solid #cccccc; border-radius: 4px; }")
        right_layout = QVBoxLayout(right_panel)
        
        self.lbl_selected_file = QLabel(LANG[self.current_lang]["ready"])
        self.lbl_selected_file.setStyleSheet("border: none; font-weight: bold;")
        
        self.btn_run = QPushButton(LANG[self.current_lang]["btn_track"])
        self.btn_run.setObjectName("AccentButton")
        self.btn_run.clicked.connect(self._run_pipeline)

        self.btn_analyse = QPushButton(LANG[self.current_lang]["btn_analyse"])
        self.btn_analyse.setStyleSheet("background-color: #388e3c; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
        self.btn_analyse.clicked.connect(self._run_analysis)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("border: 1px solid #cccccc; border-radius: 4px; text-align: center;")
        
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        right_layout.addWidget(self.lbl_selected_file)
        right_layout.addWidget(self.btn_run)
        right_layout.addWidget(self.btn_analyse)
        right_layout.addWidget(self.progress_bar)
        right_layout.addWidget(self.log_box)
        splitter.addWidget(right_panel)

        # Set default proportions: 20% Tree, 55% Video, 25% Controls
        splitter.setSizes([240, 660, 300])
        layout.addWidget(splitter, 1)

    def _toggle_language(self):
        # Swap language
        self.current_lang = "ko" if self.current_lang == "en" else "en"
        
        # Update UI Elements
        t = LANG[self.current_lang]
        self.btn_lang_toggle.setText(t["btn_lang"])
        self.btn_browse.setText(t["browse"])
        self.btn_run.setText(t["btn_track"])
        self.btn_analyse.setText(t["btn_analyse"])
        
        # Update labels if they are in their default state
        if "Ready" in self.lbl_selected_file.text() or "준비" in self.lbl_selected_file.text():
            self.lbl_selected_file.setText(t["ready"])
        if "No directory" in self.lbl_current_dir.text() or "선택된 디렉토리" in self.lbl_current_dir.text():
            self.lbl_current_dir.setText(t["no_dir"])

    def _browse_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if folder:
            self.lbl_current_dir.setText(folder)
            self.file_model.setRootPath(folder)
            self.tree.setRootIndex(self.file_model.index(folder))
            self.log_box.append(f"> Set root directory: {folder}")

    def _on_file_selected(self, index):
        path = self.file_model.filePath(index)
        if os.path.isfile(path):
            self.selected_file = path
            # Translate the "Selected: " prefix
            t = LANG[self.current_lang]
            self.lbl_selected_file.setText(t["selected"].format(file=os.path.basename(path)))
            self.video_player.load_video(path)

    def _run_pipeline(self):
        t = LANG[self.current_lang] 
        
        if not self.selected_file:
            QMessageBox.warning(self, t["warn_title"], t["warn_no_file"])
            return

        target_file = self._get_original_video_path(self.selected_file)

        csv_path = os.path.splitext(target_file)[0] + "_tracking_data.csv"
        if os.path.exists(csv_path):
            reply = QMessageBox.question(
                self, t["overwrite_title"], 
                t["overwrite_msg"].format(file=os.path.basename(target_file)), 
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # POPUP 1: Fully Translated Speed Prompt
        skip_val, ok = QInputDialog.getInt(
            self, t["speed_title"], t["speed_msg"], 3, 1, 30, 1
        )
        if not ok: return 

        self.btn_run.setEnabled(False)
        self.btn_analyse.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_box.append(f"\n>>> Starting pipeline for: {os.path.basename(self.selected_file)}")
        
        self.worker = ProcessingWorker(target_file, skip_val)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self._pipeline_finished)
        self.worker.start()

    def _update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.log_box.append(msg)

    def _pipeline_finished(self, success, msg):
        self.btn_run.setEnabled(True)
        self.btn_analyse.setEnabled(True)
        if success:
            self.log_box.append(f">>> SUCCESS: {msg}")
            # Wait 2 seconds, then reset the bar to 0
            QTimer.singleShot(2000, lambda: self.progress_bar.setValue(0))
        else:
            self.log_box.append(f">>> ERROR: {msg}")
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #e57373; }") # Red if error

    def _run_analysis(self):
        t = LANG[self.current_lang] # <-- Define 't' first!

        if not self.selected_file:
            QMessageBox.warning(self, t["warn_title"], t["warn_no_file"])
            return

        target_file = self._get_original_video_path(self.selected_file)

        csv_path = os.path.splitext(target_file)[0] + "_tracking_data.csv"
        if not os.path.exists(csv_path):
            QMessageBox.warning(self, t["err_title"], t["warn_no_csv"])
            return

        graph_path = os.path.splitext(target_file)[0] + "_kinematics_comparison.png"
        if os.path.exists(graph_path):
            reply = QMessageBox.question(
                self, t["overwrite_analysis_title"], 
                t["overwrite_analysis_msg"].format(file=os.path.basename(target_file)), 
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # POPUP 2: Pass the language dictionary into the dialog
        dialog = JointSelectionDialog(t, self)
        if dialog.exec_():
            selected_joints = dialog.get_selected()
            if not selected_joints:
                QMessageBox.warning(self, t["warn_title"], t["warn_no_joint"])
                return

            self.btn_run.setEnabled(False)
            self.btn_analyse.setEnabled(False)
            self.progress_bar.setValue(0)
            self.log_box.append(f"\n>>> Starting Analysis for: {os.path.basename(self.selected_file)}")
            
            self.analysis_worker = AnalysisWorker(target_file, selected_joints)
            self.analysis_worker.progress.connect(self._update_progress)
            self.analysis_worker.finished.connect(self._analysis_finished)
            self.analysis_worker.start()

    def _analysis_finished(self, success, msg):
        self.btn_run.setEnabled(True)
        self.btn_analyse.setEnabled(True)
        if success:
            self.log_box.append(f">>> SUCCESS: {msg}")
            # Wait 2 seconds, then reset the bar to 0
            QTimer.singleShot(2000, lambda: self.progress_bar.setValue(0))
        else:
            self.log_box.append(f">>> ERROR: {msg}")

    def _get_original_video_path(self, path):
        """Helper to resolve overlay paths back to the original source video."""
        if path.endswith("_overlay.mp4"):
            base = path.replace("_overlay.mp4", "")
        elif path.endswith("_interpersonal_links.mp4"):
            base = path.replace("_interpersonal_links.mp4", "")
        else:
            return path
            
        # Try to find the original video matching the base name
        for ext in [".mp4", ".avi", ".mov"]:
            if os.path.exists(base + ext):
                self.log_box.append(f"> Auto-corrected target to original: {os.path.basename(base + ext)}")
                return base + ext
                
        return path # Fallback if original is somehow missing

    def _open_context_menu(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid():
            return
            
        path = self.file_model.filePath(index)
        if os.path.isfile(path):
            t = LANG[self.current_lang] # <-- Get translation
            menu = QMenu()
            delete_action = menu.addAction(t["del_menu"])
            
            action = menu.exec_(self.tree.viewport().mapToGlobal(position))
            
            if action == delete_action:
                reply = QMessageBox.question(
                    self, t["del_title"], 
                    t["delete_confirm"].format(file=os.path.basename(path)), 
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    try:
                        os.remove(path)
                        self.log_box.append(f"> Deleted: {os.path.basename(path)}")
                        if self.selected_file == path:
                            self.selected_file = None
                            self.lbl_selected_file.setText(t["ready"])
                            self.video_player.stop()
                    except Exception as e:
                        QMessageBox.warning(self, t["err_title"], t["del_err"].format(err=str(e)))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JHposeGUI()
    window.show()
    sys.exit(app.exec_())