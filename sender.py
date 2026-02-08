print("✅ Script is launching...")  # DEBUG LINE: If you don't see this, the file isn't running.

import cv2
import os
import sys
import time

# --- IMPORT CHECK ---
try:
    import qr_protocol

    print("✅ Protocol loaded successfully.")
except ImportError:
    print("\n❌ ERROR: Could not find 'qr_protocol.py'")
    print("Make sure both sender.py and qr_protocol.py are in the SAME folder.")
    input("Press Enter to exit...")
    sys.exit(1)


def main():
    print("\n=== QR Sender (Protocol V1) ===")

    # 1. Get Input
    try:
        mode = input("Send (t)ext or (f)ile? ").strip().lower()
    except EOFError:
        print("❌ Error: Input stream closed. Are you running this in a console?")
        return

    data_bytes = None

    if mode == 't':
        text = input("Enter message: ")
        data_bytes = text.encode('utf-8')
    elif mode == 'f':
        path = input("Enter file path: ").strip().strip('"')
        if os.path.exists(path):
            with open(path, "rb") as f:
                data_bytes = f.read()
        else:
            print(f"❌ File not found at: {path}")
            time.sleep(2)
            return
    else:
        print("❌ Invalid option. Exiting.")
        return

    # 2. Use Protocol to Encode
    print(f"⚙️ Encoding {len(data_bytes)} bytes...")
    payloads = qr_protocol.encode_data_to_payloads(data_bytes)

    # 3. Generate Images
    print(f"🖼️ Generating {len(payloads)} QR frames...")
    images = []
    for i, p in enumerate(payloads):
        img = qr_protocol.generate_qr_image(p, i + 1, len(payloads))
        images.append(img)

    # 4. Stream Loop
    fps = 5.0
    delay = int(1000 / fps)
    window_name = "QR Sender"

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

    print(f"🚀 Streaming started! Press 'q' to stop.")

    idx = 0
    while True:
        cv2.imshow(window_name, images[idx])

        # Press 'q' to quit
        if cv2.waitKey(delay) & 0xFF == ord('q'):
            break

        idx = (idx + 1) % len(images)

    cv2.destroyAllWindows()
    print("👋 Sender closed.")


# --- THIS IS THE CRITICAL PART ---
if __name__ == "__main__":
    main()
