print("✅ Script is launching...")

import cv2
import os
import sys
import time
import numpy as np
from pyzbar.pyzbar import decode, ZBarSymbol

# --- IMPORT CHECK ---
try:
    import qr_protocol

    print("✅ Protocol loaded successfully.")
except ImportError:
    print("\n❌ ERROR: Could not find 'qr_protocol.py'")
    sys.exit(1)

WINDOW_NAME = "QR Sender"
FPS = 5


def scan_for_ack(cap, timeout=5):
    """
    Scans for an ACK/NACK response from the Receiver.
    Returns: The message type (ACK/NACK) and content, or None if timed out.
    """
    start_time = time.time()

    while (time.time() - start_time) < timeout:
        ret, frame = cap.read()
        if not ret: continue

        # We don't need to show the camera feed to the user, just process it.
        # But we must keep the cv2 window responsive.
        if cv2.waitKey(1) & 0xFF == ord('q'):
            sys.exit()

        # Fast decode using pyzbar
        decoded_objs = decode(frame, symbols=[ZBarSymbol.QRCODE])

        for obj in decoded_objs:
            text = obj.data.decode("utf-8")
            mtype, content = qr_protocol.parse_control_msg(text)

            if mtype in ["ACK", "NACK"]:
                return mtype, content

    return "TIMEOUT", None


def main():
    print("\n=== QR Sender (Smart Protocol) ===")

    # 1. GET INPUT (Your original method)
    try:
        mode = input("Send (t)ext or (f)ile? ").strip().lower()
    except EOFError:
        return

    data_bytes = None
    filename = "message.txt"

    if mode == 't':
        text = input("Enter message: ")
        data_bytes = text.encode('utf-8')
    elif mode == 'f':
        path = input("Enter file path: ").strip().strip('"')
        if os.path.exists(path):
            filename = os.path.basename(path)
            with open(path, "rb") as f:
                data_bytes = f.read()
        else:
            print(f"❌ File not found.")
            return
    else:
        print("❌ Invalid option.")
        return

    # 2. ENCODE
    print(f"⚙️ Encoding {len(data_bytes)} bytes...")
    payloads = qr_protocol.encode_data_to_payloads(data_bytes)
    total_payloads = len(payloads)

    # 3. PRE-GENERATE IMAGES (Prevents lag)
    print(f"🖼️ Generating {total_payloads} QR frames...")
    qr_images = []
    for i, p in enumerate(payloads):
        img = qr_protocol.generate_qr_image(p, i + 1, total_payloads)
        qr_images.append(img)

    # 4. SETUP CAMERA (For receiving ACKs)
    print("🎥 Opening Camera for ACKs...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened(): cap = cv2.VideoCapture(0)

    # 5. SETUP WINDOW
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_TOPMOST, 1)

    # --- PHASE 1: HANDSHAKE ---
    print("🤝 Waiting for Receiver...")
    syn_qr = qr_protocol.generate_qr_image(f"SYN:{total_payloads}:{filename}", 0, 0, title="START REQUEST")

    while True:
        cv2.imshow(WINDOW_NAME, syn_qr)
        mtype, mdata = scan_for_ack(cap, timeout=0.1)  # Fast check

        if mtype == "ACK":
            print("✅ Receiver Connected!")
            break

        if cv2.waitKey(1) & 0xFF == ord('q'):
            return

    # --- PHASE 2: BATCH TRANSFER ---
    current_batch_id = 0
    DELAY = int(1000 / FPS)

    while current_batch_id * qr_protocol.BATCH_SIZE < total_payloads:
        # Calculate Batch Range
        start = current_batch_id * qr_protocol.BATCH_SIZE
        end = min(start + qr_protocol.BATCH_SIZE, total_payloads)
        indices = list(range(start, end))

        print(f"📤 Sending Batch {current_batch_id} (Chunks {start + 1}-{end})...")

        confirmed = False
        while not confirmed:
            # A. Play the Batch
            for i in indices:
                cv2.imshow(WINDOW_NAME, qr_images[i])
                if cv2.waitKey(DELAY) & 0xFF == ord('q'): return

            # B. Show "Sync Check" QR
            sync_qr = qr_protocol.generate_qr_image(f"SYNC_CHECK:{current_batch_id}", 0, 0, title="CHECKING...")
            cv2.imshow(WINDOW_NAME, sync_qr)

            # C. Wait for ACK (Max 5 seconds)
            print("   ⏳ Waiting for confirmation...")
            mtype, mdata = scan_for_ack(cap, timeout=5)

            if mtype == "ACK" and mdata == current_batch_id:
                print(f"   ✅ Batch {current_batch_id} Confirmed.")
                confirmed = True
                current_batch_id += 1
            elif mtype == "NACK":
                print(f"   ⚠️ Receiver missed chunks: {mdata['missing']}")
                # Only replay the missing ones
                indices = [x - 1 for x in mdata['missing']]  # Convert 1-based back to 0-based
            else:
                print("   ❓ No response. Replaying full batch.")
                # Loop restarts, replaying all images in batch

    # --- FINISH ---
    print("🎉 File Sent Successfully!")
    done_qr = qr_protocol.generate_qr_image("DONE", 0, 0, title="TRANSFER COMPLETE")
    cv2.imshow(WINDOW_NAME, done_qr)
    cv2.waitKey(5000)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
    
