import pandas as pd
import numpy as np
import cv2
import os
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

class BehavioAnalyser:
    def __init__(self):
        # Maps the joint category to the specific cross-body COCO index pairs
        # Format: (Name A, Idx A, Name B, Idx B)
        self.CROSS_LINKS = {
            "Nose": [("Nose", 0, "Nose", 0)],
            "Shoulders": [("L_Shoulder", 5, "R_Shoulder", 6), ("R_Shoulder", 6, "L_Shoulder", 5)],
            "Elbows": [("L_Elbow", 7, "R_Elbow", 8), ("R_Elbow", 8, "L_Elbow", 7)],
            "Wrists": [("L_Wrist", 9, "R_Wrist", 10), ("R_Wrist", 10, "L_Wrist", 9)],
            "Hips": [("L_Hip", 11, "R_Hip", 12), ("R_Hip", 12, "L_Hip", 11)],
            "Ankles": [("L_Ankle", 15, "R_Ankle", 16), ("R_Ankle", 16, "L_Ankle", 15)]
        }
        
        self.colors = [
            (0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255),
            (255, 0, 255), (255, 255, 0), (128, 0, 0), (0, 128, 0)
        ]

    def _butter_lowpass_filter(self, data, fps, cutoff):
        nyq = 0.5 * fps
        # Safely cap the cutoff just below the Nyquist limit
        if cutoff >= nyq: cutoff = nyq * 0.9 
        
        normal_cutoff = cutoff / nyq
        b, a = butter(4, normal_cutoff, btype='low', analog=False)
        
        padlen = min(15, len(data) - 1)
        if padlen > 3:
            return filtfilt(b, a, data, padlen=padlen)
        return data

    def run_analysis(self, video_path, csv_path, selected_categories, progress_callback=None):
        if not os.path.exists(csv_path):
            raise FileNotFoundError("Tracking CSV not found. Please run processing first.")
            
        df = pd.read_csv(csv_path)
        df_A = df[df['Person_ID'] == 'Person_A'].set_index('Frame')
        df_B = df[df['Person_ID'] == 'Person_B'].set_index('Frame')
        
        common_frames = df_A.index.intersection(df_B.index).sort_values()
        df_A = df_A.loc[common_frames]
        df_B = df_B.loc[common_frames]
        
        cap = cv2.VideoCapture(video_path)
        orig_fps = cap.get(cv2.CAP_PROP_FPS)
        if orig_fps == 0: orig_fps = 30
        
        frame_diffs = np.diff(common_frames)
        median_skip = np.median(frame_diffs) if len(frame_diffs) > 0 else 1
        effective_fps = orig_fps / median_skip
        
        # Calculate Distances for selected categories
        raw_distances = {}
        std_distances = {}
        agg_distances = {}
        
        active_pairs = []
        for cat in selected_categories:
            if cat in self.CROSS_LINKS:
                active_pairs.extend(self.CROSS_LINKS[cat])

        for (name_A, idx_A, name_B, idx_B) in active_pairs:
            link_name = f"{name_A} to {name_B}"
            xA = df_A[f'KP_{idx_A}_X'].values
            yA = df_A[f'KP_{idx_A}_Y'].values
            xB = df_B[f'KP_{idx_B}_X'].values
            yB = df_B[f'KP_{idx_B}_Y'].values
            
            raw_dist = np.sqrt((xB - xA)**2 + (yB - yA)**2)
            
            # Standard Filter (e.g., 4Hz for standard kinematics)
            std_dist = self._butter_lowpass_filter(raw_dist, effective_fps, cutoff=4.0)
            # Aggressive Filter (e.g., 0.5Hz for macro posture leaning)
            agg_dist = self._butter_lowpass_filter(raw_dist, effective_fps, cutoff=0.5)
            
            raw_distances[link_name] = raw_dist
            std_distances[link_name] = std_dist
            agg_distances[link_name] = agg_dist

        # ==========================================
        # 1. GENERATE THE TRIPLE GRAPH
        # ==========================================
        if progress_callback: progress_callback(30, "Generating kinematic graphs...")
        
        time_axis = common_frames.values / orig_fps 
        
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
        
        for link_name in raw_distances.keys():
            ax1.plot(time_axis, raw_distances[link_name], alpha=0.6)
            ax2.plot(time_axis, std_distances[link_name], linewidth=1.5)
            ax3.plot(time_axis, agg_distances[link_name], linewidth=2.0, label=link_name)
            
        ax1.set_title(f'Raw Pixel Distances (Effective FPS: {effective_fps:.1f})')
        ax2.set_title('Standard Kinematic Filter (Cutoff ~4Hz)')
        ax3.set_title('Aggressive Posture Filter (Cutoff 0.5Hz - Smooth Macro Shifts)')
        
        ax3.set_xlabel('Time (Seconds)')
        for ax in [ax1, ax2, ax3]:
            ax.set_ylabel('Distance (Pixels)')
            ax.grid(True, linestyle='--', alpha=0.7)
            
        ax3.legend(bbox_to_anchor=(1.02, 3.5), loc='upper left') # Push legend outside
        plt.tight_layout()
        
        graph_path = os.path.splitext(video_path)[0] + "_kinematics_comparison.png"
        plt.savefig(graph_path, dpi=300, bbox_inches='tight')
        plt.close()

        # ==========================================
        # 2. GENERATE THE LINKED OVERLAY VIDEO
        # ==========================================
        if progress_callback: progress_callback(60, "Generating interpersonal overlay video...")
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        output_vid = os.path.splitext(video_path)[0] + "_interpersonal_links.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        vid_writer = cv2.VideoWriter(output_vid, fourcc, effective_fps, (width, height))
        
        frame_idx = 0
        total_common = len(common_frames)
        
        for frame_num in common_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if not ret: break
            
            frame = cv2.addWeighted(frame, 0.4, np.zeros(frame.shape, frame.dtype), 0, 0)
            
            for i, (name_A, idx_A, name_B, idx_B) in enumerate(active_pairs):
                x1 = int(df_A.loc[frame_num, f'KP_{idx_A}_X'])
                y1 = int(df_A.loc[frame_num, f'KP_{idx_A}_Y'])
                x2 = int(df_B.loc[frame_num, f'KP_{idx_B}_X'])
                y2 = int(df_B.loc[frame_num, f'KP_{idx_B}_Y'])
                
                conf1 = df_A.loc[frame_num, f'KP_{idx_A}_Conf']
                conf2 = df_B.loc[frame_num, f'KP_{idx_B}_Conf']
                
                if conf1 > 0.3 and conf2 > 0.3:
                    color = self.colors[i % len(self.colors)]
                    cv2.line(frame, (x1, y1), (x2, y2), color, 3)
                    cv2.circle(frame, (x1, y1), 5, (255, 255, 255), -1)
                    cv2.circle(frame, (x2, y2), 5, (255, 255, 255), -1)

            vid_writer.write(frame)
            frame_idx += 1
            if progress_callback and frame_idx % 20 == 0:
                percent = 60 + int((frame_idx / total_common) * 40)
                progress_callback(percent, f"Drawing links: {frame_idx}/{total_common} frames...")

        cap.release()
        vid_writer.release()
        return graph_path, output_vid