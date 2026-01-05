import cv2
import base64
import time
import os
from pyzbar.pyzbar import decode

SAVE_DIR = "received_files"
os.makedirs(SAVE_DIR, exist_ok=True)


def decode_qr_from_frame(frame):
    """Decode QR (Dual mode logic reads normal or chunked packets).
       Includes grayscale save for debugging."""

    # Save raw frame
    cv2.imwrite("frame.jpg", frame)

    # Step 1: Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cv2.imwrite("01_gray.jpg", gray)

    # Step 2: Try reading QR directly from grayscale
    from pyzbar.pyzbar import decode, ZBarSymbol
    qrs = decode(gray, symbols=[ZBarSymbol.QRCODE])
    if qrs:
        return qrs[0].data.decode("utf-8")

    # Step 3: Try adaptive threshold (fallback)
    thresh = cv2.adaptiveThreshold(gray, 255,
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
    cv2.imwrite("02_threshold.jpg", thresh)

    qrs = decode(thresh, symbols=[ZBarSymbol.QRCODE])
    if qrs:
        return qrs[0].data.decode("utf-8")

    return None


def receive_qr_stream():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    received_chunks = {}
    total_chunks = None

    print("\n📷 QR Receiver ONLINE — Dual Mode Enabled")
    print("• Text QR → will be printed")
    print("• Chunk QR (1/40:...) → reconstructs file\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Camera read failed.")
            break

        text = decode_qr_from_frame(frame)

        if text:

            # ---------------- SIMPLE TEXT MODE ----------------
            if ":" not in text or "/" not in text:
                print(f"🔹 Text QR Detected → {text}")
                continue  # remove if you want to save text instead

            # ---------------- FILE CHUNK MODE ----------------
            try:
                header, data = text.split(":", 1)
                part, total = map(int, header.split("/"))

                if total_chunks is None:
                    total_chunks = total
                    print(f"\n📦 Incoming file: {total} chunks expected")

                if part not in received_chunks:
                    received_chunks[part] = data
                    print(f"🟩 Chunk {part}/{total} received "
                          f"({len(received_chunks)}/{total})")

                # File complete?
                if len(received_chunks) == total_chunks:
                    print("\n🎉 Transfer complete — rebuilding...")

                    combined = "".join(received_chunks[i] for i in range(1, total + 1))
                    file_bytes = base64.b64decode(combined)

                    filename = time.strftime("%Y-%m-%d_%H-%M-%S") + "_received.bin"
                    path = os.path.join(SAVE_DIR, filename)
                    with open(path, "wb") as f:
                        f.write(file_bytes)

                    print(f"💾 File saved → {path}")
                    try: os.startfile(path)
                    except: pass

                    # Reset for next file
                    received_chunks = {}
                    total_chunks = None
                    print("\n🔄 Ready for next transfer.\n")

            except Exception as e:
                print(f"⚠ Format error → {e}")

        # Live feed on screen
        cv2.imshow("QR RECEIVER", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC exits
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    receive_qr_stream()
