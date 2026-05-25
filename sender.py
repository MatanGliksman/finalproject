print("✅ Script is launching...")

import cv2
import os
import sys
import time
import numpy as np
from pyzbar.pyzbar import decode, ZBarSymbol

try:
    import qr_protocol

    print("✅ Protocol loaded successfully.")
except ImportError:
    print("\n❌ ERROR: Could not find 'qr_protocol.py'")
    sys.exit(1)

WINDOW_NAME = "QR Sender"
FPS = 3


def scan_for_ack(cap, timeout=8):
    start_time = time.time()

    while (time.time() - start_time) < timeout:
        ret, frame = cap.read()
        if not ret:
            continue

        if cv2.waitKey(1) & 0xFF == ord('q'):
            sys.exit()

        decoded_objs = decode(frame, symbols=[ZBarSymbol.QRCODE])

        for obj in decoded_objs:
            text = obj.data.decode("utf-8")
            mtype, content = qr_protocol.parse_control_msg(text)

            if mtype in ["ACK", "NACK"]:
                return mtype, content

    return "TIMEOUT", None


def send_once():
    """
    Runs exactly one transfer — identical to the original working code.
    Returns True if we should send again, False to quit.
    """
    # 1. GET INPUT
    try:
        mode = input("\nSend (t)ext or (f)ile, or (q)uit? ").strip().lower()
    except EOFError:
        return False

    if mode == 'q':
        print("👋 Bye!")
        return False

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
            return True
    else:
        print("❌ Invalid option.")
        return True

    # 2. GENERATE A FRESH AES KEY FOR THIS SESSION
    aes_key = qr_protocol.generate_aes_key()
    key_str = qr_protocol.key_to_str(aes_key)
    print(f"🔑 Session encryption key generated.")

    # 3. ENCODE + ENCRYPT
    print(f"⚙️ Encrypting and encoding {len(data_bytes)} bytes...")
    payloads = qr_protocol.encode_data_to_payloads(data_bytes, aes_key)
    total_payloads = len(payloads)

    # 4. PRE-GENERATE IMAGES
    print(f"🖼️ Generating {total_payloads} QR frames...")
    qr_images = []
    for i, p in enumerate(payloads):
        img = qr_protocol.generate_qr_image(p, i + 1, total_payloads)
        qr_images.append(img)

    # 5. SETUP CAMERA — fresh every transfer, same as original
    print("🎥 Opening Camera for ACKs...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    # 6. SETUP WINDOW — fresh every transfer, same as original
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_TOPMOST, 1)

    # --- PHASE 1: HANDSHAKE ---
    print("🤝 Waiting for Receiver to connect...")
    syn_payload = f"SYN:{total_payloads}:{filename}:{key_str}"
    syn_qr = qr_protocol.generate_qr_image(syn_payload, 0, 0, title="START REQUEST (KEY INSIDE)")

    while True:
        cv2.imshow(WINDOW_NAME, syn_qr)
        mtype, mdata = scan_for_ack(cap, timeout=0.1)

        if mtype == "ACK" and mdata == "READY":
            print("✅ Receiver connected and key received!")
            break

        if cv2.waitKey(1) & 0xFF == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
            return False

    # --- PHASE 2: BATCH TRANSFER ---
    current_batch_id = 0
    DELAY = int(1000 / FPS)

    while current_batch_id * qr_protocol.BATCH_SIZE < total_payloads:
        start = current_batch_id * qr_protocol.BATCH_SIZE
        end = min(start + qr_protocol.BATCH_SIZE, total_payloads)
        indices = list(range(start, end))

        print(f"📤 Sending Batch {current_batch_id} (Chunks {start + 1}-{end})...")

        confirmed = False
        while not confirmed:
            for i in indices:
                cv2.imshow(WINDOW_NAME, qr_images[i])
                if cv2.waitKey(DELAY) & 0xFF == ord('q'):
                    cap.release()
                    cv2.destroyAllWindows()
                    return False

            sync_qr = qr_protocol.generate_qr_image(
                f"SYNC_CHECK:{current_batch_id}", 0, 0, title="CHECKING..."
            )
            cv2.imshow(WINDOW_NAME, sync_qr)

            print("   ⏳ Waiting for confirmation...")
            mtype, mdata = scan_for_ack(cap, timeout=5)

            if mtype == "ACK" and mdata == current_batch_id:
                print(f"   ✅ Batch {current_batch_id} confirmed.")
                confirmed = True
                current_batch_id += 1

            elif mtype == "NACK":
                missing_raw = mdata['missing']
                print(f"   ⚠️ Receiver missed chunks: {missing_raw}")
                new_indices = [
                    x - 1
                    for x in missing_raw
                    if 0 <= x - 1 < total_payloads
                ]
                if new_indices:
                    indices = new_indices
                else:
                    confirmed = True
                    current_batch_id += 1

            else:
                print("   ❓ No response / timeout. Replaying full batch.")
                start = current_batch_id * qr_protocol.BATCH_SIZE
                end = min(start + qr_protocol.BATCH_SIZE, total_payloads)
                indices = list(range(start, end))

    # --- PHASE 3: FINISH ---
    print("🎉 Transfer complete!")
    done_qr = qr_protocol.generate_qr_image("DONE", 0, 0, title="TRANSFER COMPLETE")
    cv2.imshow(WINDOW_NAME, done_qr)
    cv2.waitKey(5000)

    # Clean up exactly like the original — then we ask again
    cap.release()
    cv2.destroyAllWindows()

    return True  # ask for next transfer


def main():
    print("\n=== QR Sender (Encrypted Smart Protocol) ===")
    while send_once():
        pass


if __name__ == "__main__":
    main()
