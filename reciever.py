import cv2
import numpy as np
import qr_protocol
import time
import sys

# --- DYNAMIC IMPORT ---
# This fixes the "Unresolved Reference" error automatically.
try:
    from pyzbar.pyzbar import decode, ZBarSymbol
    USING_PYZBAR = True
    print("✅ Logic: Using Pyzbar (High Performance)")
except ImportError:
    USING_PYZBAR = False
    print("⚠️ Logic: Pyzbar not found. Using Standard OpenCV (Slower).")
    print("   (Tip: Run 'pip install pyzbar' for better speed)")

WINDOW_NAME = "Receiver"

def show_ack_qr(text, title, duration=2):
    img = qr_protocol.generate_qr_image(text, 0, 0, title=title)
    cv2.imshow("Response_QR", img)
    cv2.waitKey(int(duration * 1000))
    cv2.destroyWindow("Response_QR")

def scan_frame(frame, detector):
    """
    Tries to detect QR codes using whatever library is available.
    Returns: list of (data_string, polygon_points)
    """
    results = []
    
    # 1. PRE-PROCESSING (Crucial for reading screens)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    if USING_PYZBAR:
        # --- PYZBAR METHOD ---
        decoded_objs = decode(gray, symbols=[ZBarSymbol.QRCODE])
        for obj in decoded_objs:
            data = obj.data.decode("utf-8")
            pts = np.array(obj.polygon, dtype=np.int32)
            results.append((data, pts))
            
    else:
        # --- OPENCV FALLBACK METHOD ---
        # We apply high contrast to help OpenCV see the screen
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        
        data, points, _ = detector.detectAndDecode(binary)
        if data and points is not None:
            pts = points.astype(int)
            results.append((data, pts))
            
    return results

def main():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) 
    if not cap.isOpened(): cap = cv2.VideoCapture(0)
    
    # High Resolution for better scanning
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Create detector only if needed
    detector = None
    if not USING_PYZBAR:
        detector = cv2.QRCodeDetector()

    print("=== RECEIVER LISTENING ===")
    
    received_chunks = {}
    total_expected = 0
    state = "WAITING_HANDSHAKE"
    filename = "unknown"
    current_batch = 0

    while True:
        ret, frame = cap.read()
        if not ret: continue

        # SCAN
        found_qrs = scan_frame(frame, detector)

        for data, pts in found_qrs:
            # Draw Green Box
            if USING_PYZBAR:
                cv2.polylines(frame, [pts], True, (0, 255, 0), 3)
            else:
                # OpenCV points shape is different
                for i in range(len(pts)):
                    pt1 = tuple(pts[i][0])
                    pt2 = tuple(pts[(i+1) % len(pts)][0])
                    cv2.line(frame, pt1, pt2, (0, 255, 0), 3)

            # PARSE LOGIC
            mtype, content = qr_protocol.parse_control_msg(data)

            # --- LOGIC FLOW ---
            if state == "WAITING_HANDSHAKE":
                if mtype == "SYN":
                    total_expected = content['total']
                    filename = content['filename']
                    print(f"✅ Handshake! File: {filename} ({total_expected} chunks)")
                    show_ack_qr(f"ACK:{total_expected}", "HANDSHAKE ACCEPTED")
                    state = "RECEIVING"

            elif state == "RECEIVING":
                if mtype == "DATA":
                    res = qr_protocol.parse_qr_payload(data)
                    if res:
                        idx, tot, chunk_data = res
                        if idx not in received_chunks:
                            received_chunks[idx] = chunk_data
                            print(f"   📥 Chunk {idx}/{tot}")

                elif mtype == "SYNC_CHECK":
                    batch_id = content
                    if batch_id == current_batch:
                        start = batch_id * qr_protocol.BATCH_SIZE
                        end = min(start + qr_protocol.BATCH_SIZE, total_expected)
                        needed = range(start + 1, end + 1)
                        missing = [i for i in needed if i not in received_chunks]

                        if not missing:
                            print(f"✅ Batch {batch_id} Done.")
                            show_ack_qr(f"ACK:{batch_id}", "BATCH RECEIVED")
                            current_batch += 1
                        else:
                            print(f"⚠️ Batch {batch_id} Missing: {missing}")
                            missing_str = ",".join(map(str, missing))
                            show_ack_qr(f"NACK:{batch_id}:{missing_str}", "RETRY REQUEST")

        # GUI
        cv2.putText(frame, f"State: {state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        if total_expected > 0:
            count = len(received_chunks)
            cv2.putText(frame, f"Progress: {count}/{total_expected}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

        cv2.imshow(WINDOW_NAME, frame)

        # FINISH
        if total_expected > 0 and len(received_chunks) == total_expected:
            print("🎉 TRANSFER COMPLETE!")
            path = qr_protocol.rebuild_file(received_chunks, total_expected, filename)
            if path: qr_protocol.open_file_native(path)
            break

        if cv2.waitKey(1) & 0xFF == 27: break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
