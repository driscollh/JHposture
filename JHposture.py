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
# MODULAR WORKER THREAD
# =============================================================================
class JointSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Interpersonal Links")
        self.setFixedSize(300, 250)
        self.setStyleSheet("background-color: #f2f1ec; color: #222222;")
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select which cross-body distances to track:"))
        
        self.checkboxes = {}
        categories = ["Nose", "Shoulders", "Elbows", "Wrists", "Hips", "Ankles"]
        
        for cat in categories:
            chk = QCheckBox(cat)
            chk.setChecked(True) # Default all to checked
            layout.addWidget(chk)
            self.checkboxes[cat] = chk
            
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Analyse")
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
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Top Bar ---
        top_bar = QHBoxLayout()
        self.lbl_current_dir = QLabel("No directory selected")
        self.lbl_current_dir.setStyleSheet("color: #666; font-style: italic; background-color: transparent;")
        
        btn_browse = QPushButton("Browse SSD / Folder")
        btn_browse.clicked.connect(self._browse_directory)
        
        top_bar.addWidget(btn_browse)
        top_bar.addWidget(self.lbl_current_dir, 1)
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
        
        self.lbl_selected_file = QLabel("Ready to process.")
        self.lbl_selected_file.setStyleSheet("border: none; font-weight: bold;")
        
        self.btn_run = QPushButton("RUN PROCESSING")
        self.btn_run.setObjectName("AccentButton")
        self.btn_run.clicked.connect(self._run_pipeline)

        self.btn_analyse = QPushButton("2. RUN BEHAVIORAL ANALYSIS")
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
            self.lbl_selected_file.setText(f"Selected: {os.path.basename(path)}")
            # Load video into the player!
            self.video_player.load_video(path)

    def _run_pipeline(self):
        if not self.selected_file:
            QMessageBox.warning(self, "Warning", "Please select a video file from the tree first.")
            return

        # Auto-correct to original video if an overlay is selected
        target_file = self._get_original_video_path(self.selected_file)

        # OVERWRITE CHECK
        csv_path = os.path.splitext(target_file)[0] + "_tracking_data.csv"
        if os.path.exists(csv_path):
            reply = QMessageBox.question(
                self, 'Overwrite Tracking Data?', 
                f"Tracking data already exists for:\n{os.path.basename(target_file)}\n\nDo you want to overwrite it?", 
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # POPUP 1: Ask for Frame Skip
        skip_val, ok = QInputDialog.getInt(
            self, "Processing Speed", 
            "Process every Nth frame\n(1 = Slowest/Highest Fidelity, 3 = Balanced, 10 = Fastest):\n\nNote: This sets the baseline FPS for analysis filtering.",
            3, 1, 30, 1
        )
        if not ok: return # User clicked cancel

        self.btn_run.setEnabled(False)
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
        if not self.selected_file:
            QMessageBox.warning(self, "Warning", "Please select a video file first.")
            return

        # Auto-correct to original video if an overlay is selected
        target_file = self._get_original_video_path(self.selected_file)

        # Ensure the CSV actually exists before trying to analyse it
        csv_path = os.path.splitext(target_file)[0] + "_tracking_data.csv"
        if not os.path.exists(csv_path):
            QMessageBox.warning(self, "Error", "No tracking data found for this video. Please run tracking first.")
            return

        # OVERWRITE CHECK (For analysis graphs/videos)
        graph_path = os.path.splitext(target_file)[0] + "_kinematics_comparison.png"
        if os.path.exists(graph_path):
            reply = QMessageBox.question(
                self, 'Overwrite Analysis Data?', 
                f"Analysis graphs and videos already exist for:\n{os.path.basename(target_file)}\n\nDo you want to overwrite them?", 
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # POPUP 2: Ask for Joint Selection
        dialog = JointSelectionDialog(self)
        if dialog.exec_():
            selected_joints = dialog.get_selected()
            if not selected_joints:
                QMessageBox.warning(self, "Warning", "You must select at least one joint pair.")
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
            menu = QMenu()
            delete_action = menu.addAction("Delete File")
            
            # Show the menu at the cursor's location
            action = menu.exec_(self.tree.viewport().mapToGlobal(position))
            
            if action == delete_action:
                reply = QMessageBox.question(
                    self, 'Confirm Delete', 
                    f"Are you sure you want to permanently delete:\n{os.path.basename(path)}?", 
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    try:
                        os.remove(path)
                        self.log_box.append(f"> Deleted: {os.path.basename(path)}")
                        # If they deleted the currently loaded video, clear the viewer
                        if self.selected_file == path:
                            self.selected_file = None
                            self.lbl_selected_file.setText("Ready to process.")
                            self.video_player.stop()
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Could not delete file:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JHposeGUI()
    window.show()
    sys.exit(app.exec_())