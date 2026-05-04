import cv2
import csv
import os
from rtmlib import Wholebody # <-- Switched to the 133-keypoint model

class JHTracker:
    def __init__(self):
        # Initialize the Wholebody ONNX tracker
        self.tracker = Wholebody(mode='balanced', backend='onnxruntime', device='cpu')
        
        # Standard COCO 17 Body Links for drawing the skeleton
        self.BODY_LINKS = [
            (0, 1), (1, 3), (0, 2), (2, 4),      # Head/Face outline
            (5, 6), (5, 11), (6, 12), (11, 12),  # Torso
            (5, 7), (7, 9),                      # Left Arm
            (6, 8), (8, 10),                     # Right Arm
            (11, 13), (13, 15),                  # Left Leg
            (12, 14), (14, 16)                   # Right Leg
        ]

        # Standard Hand Links (21 points per hand)
        self.HAND_LINKS = [
            (0,1), (1,2), (2,3), (3,4),          # Thumb
            (0,5), (5,6), (6,7), (7,8),          # Index
            (0,9), (9,10), (10,11), (11,12),     # Middle
            (0,13), (13,14), (14,15), (15,16),   # Ring
            (0,17), (17,18), (18,19), (19,20)    # Pinky
        ]

    def process_video(self, video_path, frame_skip=3, progress_callback=None):
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0 or fps is None: fps = 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        output_csv = os.path.splitext(video_path)[0] + "_tracking_data.csv"
        output_vid = os.path.splitext(video_path)[0] + "_overlay.mp4"
        
        # We now use the frame_skip passed from the GUI!
        out_fps = fps / frame_skip
        
        # Video Writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        vid_writer = cv2.VideoWriter(output_vid, fourcc, out_fps, (width, height))
        
        # Dynamic Header for 133 Keypoints
        header = ["Frame", "Person_ID"]
        for i in range(133):
            header.extend([f"KP_{i}_X", f"KP_{i}_Y", f"KP_{i}_Conf"])

        with open(output_csv, mode='w', newline='') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow(header)

            current_frame = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Only run the heavy AI tracking if it's the 3rd frame
                if current_frame % frame_skip == 0:
                    
                    # rtmlib handles the YOLO detection and RTMPose extraction
                    keypoints, scores = self.tracker(frame) 
                    
                    # Sort people left-to-right based on Nose X-coordinate
                    people_data = []
                    for p_idx in range(len(keypoints)):
                        nose_x = keypoints[p_idx][0][0]
                        people_data.append((nose_x, p_idx))
                    people_data.sort(key=lambda x: x[0]) 
                    
                    # Extract and Draw the top 2 people
                    for i, (_, p_idx) in enumerate(people_data[:2]):
                        person_id = "Person_A" if i == 0 else "Person_B"
                        row = [current_frame, person_id]
                        
                        color = (255, 100, 0) if i == 0 else (0, 150, 255)
                        
                        # 1. DRAW BOUNDING BOX
                        valid_x = [kp[0] for kp, score in zip(keypoints[p_idx], scores[p_idx]) if score > 0.3]
                        valid_y = [kp[1] for kp, score in zip(keypoints[p_idx], scores[p_idx]) if score > 0.3]
                        
                        if valid_x and valid_y:
                            x_min, x_max = int(min(valid_x)), int(max(valid_x))
                            y_min, y_max = int(min(valid_y)), int(max(valid_y))
                            
                            pad = 20
                            x_min, y_min = max(0, x_min - pad), max(0, y_min - pad)
                            x_max, y_max = min(width, x_max + pad), min(height, y_max + pad)
                            
                            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)
                            cv2.putText(frame, person_id, (x_min, y_min - 10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                        # 2. DRAW SKELETON LINES (BODY)
                        for (idx1, idx2) in self.BODY_LINKS:
                            if scores[p_idx][idx1] > 0.3 and scores[p_idx][idx2] > 0.3:
                                pt1 = (int(keypoints[p_idx][idx1][0]), int(keypoints[p_idx][idx1][1]))
                                pt2 = (int(keypoints[p_idx][idx2][0]), int(keypoints[p_idx][idx2][1]))
                                cv2.line(frame, pt1, pt2, color, 2)

                        # 3. DRAW SKELETON LINES (HANDS)
                        for offset in [91, 112]:
                            for (idx1, idx2) in self.HAND_LINKS:
                                i1, i2 = idx1 + offset, idx2 + offset
                                if scores[p_idx][i1] > 0.15 and scores[p_idx][i2] > 0.15: 
                                    pt1 = (int(keypoints[p_idx][i1][0]), int(keypoints[p_idx][i1][1]))
                                    pt2 = (int(keypoints[p_idx][i2][0]), int(keypoints[p_idx][i2][1]))
                                    cv2.line(frame, pt1, pt2, color, 1)

                        # 4. DRAW ALL 133 DOTS & LOG CSV
                        for kp_idx in range(133):
                            x, y = keypoints[p_idx][kp_idx]
                            conf = scores[p_idx][kp_idx]
                            row.extend([x, y, conf])
                            
                            if conf > 0.3:
                                radius = 2 if 23 <= kp_idx <= 90 else 4
                                cv2.circle(frame, (int(x), int(y)), radius, color, -1)
                                
                        csv_writer.writerow(row)

                    # Save the drawn frame to the new video (this must be indented inside the IF block)
                    vid_writer.write(frame)

                # ========================================================
                # GUI UPDATE: Now guaranteed to run on every single loop!
                # ========================================================
                current_frame += 1
                if progress_callback and current_frame % 30 == 0:
                    percent = int((current_frame / total_frames) * 100)
                    progress_callback(percent, f"Processed frame {current_frame}/{total_frames}...")

        cap.release()
        vid_writer.release()
        return output_csv