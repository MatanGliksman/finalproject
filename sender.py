import qrcode
import base64
import os
import cv2
import numpy as np
import time

# --- KEY CHANGE: REDUCED DATA DENSITY ---
# Lowering this makes the QR blocks larger and easier to scan.
# Previously 800 -> Now 400.
MAX_QR_BYTES = 400  

def generate_qr_from_text(text):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def prepare_chunks(data_bytes):
    b64_data = base64.b64encode(data_bytes).decode('utf-8')
    chunks = [b64_data[i:i + MAX_QR_BYTES] for i in range(0, len(b64_data), MAX_QR_BYTES)]
    
    qr_images = []
    print(f"📦 Data split into {len(chunks)} chunks (Low Density Mode).")

    for i, chunk in enumerate(chunks):
        payload = f"{i+1}/{len(chunks)}:{chunk}"
        img = generate_qr_from_text(payload)
        
        # Thicker border for better contrast
        img = cv2.copyMakeBorder(img, 50, 50, 50, 50, cv2.BORDER_CONSTANT, value=(0, 255, 0))
        cv2.putText(img, f"Chunk {i+1}/{len(chunks)}", (30, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        
        qr_images.append(img)
    
    return qr_images

def stream_qr_sequence(qr_images, fps):
    if not qr_images: return

    delay_ms = int(1000 / fps)
    window_name = "QR Streamer"
    
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

    print(f"🚀 Streaming {len(qr_images)} frames at {fps} FPS.")
    
    current_idx = 0
    while True:
        img = qr_images[current_idx]
        cv2.imshow(window_name, img)
        
        key = cv2.waitKey(delay_ms) & 0xFF
        if key == ord('q'): break
        
        current_idx = (current_idx + 1) % len(qr_images)

    cv2.destroyAllWindows()

def main():
    print("=== QR Data Transmitter (Low Density) ===")
    mode = input("Send (t)ext or (f)ile? ").strip().lower()
    data_bytes = None

    if mode == 't':
        text = input("Enter message: ")
        data_bytes = text.encode('utf-8')
    elif mode == 'f':
        file_path = input("Enter file path: ").strip().strip('"')
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                data_bytes = f.read()
    
    if data_bytes:
        try: fps = float(input("Enter FPS (Try 4 or 5): "))
        except: fps = 5.0
        
        qr_images = prepare_chunks(data_bytes)
        stream_qr_sequence(qr_images, fps)

if __name__ == "__main__":
    main()
