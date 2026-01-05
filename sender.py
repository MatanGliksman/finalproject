import qrcode
import base64
import os
import cv2
import numpy as np
from PIL import Image

MAX_QR_BYTES = 1000  # Safe chunk size to fit into QR version 40


def generate_qr_from_text(text):
    """Create a QR code from text and return it as an OpenCV image."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def generate_qrs_from_file(file_path):
    """Read a file, split it into base64 chunks, and generate multiple QR codes."""
    with open(file_path, "rb") as f:
        data = f.read()

    b64_data = base64.b64encode(data).decode('utf-8')

    # Split into safe-size chunks
    chunk_size = MAX_QR_BYTES
    chunks = [b64_data[i:i + chunk_size] for i in range(0, len(b64_data), chunk_size)]
    print(f"📦 File split into {len(chunks)} QR chunks.")

    qrs = []
    for i, chunk in enumerate(chunks):
        payload = f"{i + 1}/{len(chunks)}:{chunk}"
        qrs.append(generate_qr_from_text(payload))
    return qrs


def show_qr_images(qr_images):
    """Display each QR code full-screen and on top."""
    for i, img in enumerate(qr_images):
        window_name = f"QR Code Viewer ({i + 1}/{len(qr_images)})"

        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

        # Detect screen size
        rect = cv2.getWindowImageRect(window_name)
        screen_width, screen_height = rect[2], rect[3]

        h, w, _ = img.shape
        scale = min(screen_width / w, screen_height / h)
        resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_NEAREST)

        cv2.imshow(window_name, resized)
        cv2.waitKey(1)

        print(f"🖼️ Showing QR code {i + 1}/{len(qr_images)} (press any key for next)")
        cv2.waitKey(0)
        cv2.destroyWindow(window_name)

    cv2.destroyAllWindows()


def main():
    print("=== QR Code Generator ===")

    while True:
        choice = input("\nEnter 't' for text, 'f' for file, or 'q' to quit: ").strip().lower()

        if choice == 'q':
            print("👋 Goodbye!")
            break

        elif choice == 't':
            text = input("Enter text to convert to QR: ")
            qr_img = generate_qr_from_text(text)
            show_qr_images([qr_img])

        elif choice == 'f':
            file_path = input("Enter file path: ").strip().strip('"').strip("'")
            file_path = file_path.replace("\\", "/")

            if not os.path.exists(file_path):
                print("❌ File not found! Please check the path.")
                continue

            qr_images = generate_qrs_from_file(file_path)
            show_qr_images(qr_images)

        else:
            print("❌ Invalid choice. Please enter 't', 'f', or 'q'.")


if __name__ == "__main__":
    main()