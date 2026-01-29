import cv2
import base64
import time
import os
import numpy as np
import subprocess
import platform
from pyzbar.pyzbar import decode, ZBarSymbol

# Create the folder where files will be saved
SAVE_DIR = "received_files"
os.makedirs(SAVE_DIR, exist_ok=True)

def open_file_automatically(path):
    """Opens the saved file using the computer's default program."""
    try:
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.call(('open', path))
        else:  # Linux
            subprocess.call(('xdg-open', path))
        print("📂 File opened successfully.")
    except Exception as e:
        print(f"⚠️ Could not auto-open file: {e}")

def reconstruct_and_save(received_chunks, total_chunks):
    """
    1. Sorts the chunks in order (1, 2, 3...).
    2. Combines them into one long string.
    3. Decodes the Base64 back into the original file.
    4. Saves it to the computer.
    """
    print("\n🔨 Reconstructing file package...")
    
    # 1. Join all chunks in the correct order
    combined_data = "".join(received_chunks[i] for i in range(1, total_chunks + 1))
    
    # 2. Decode Base64 back to original bytes
    try:
        file_bytes = base64.b64decode(combined_data)
    except Exception as e:
        print(f"❌ Error decoding data: {e}")
        return None

    # 3. Guess the file extension (Text or Binary)
    try:
        file_bytes.decode('utf-8')
        ext = ".txt"  # It's a text message
    except UnicodeDecodeError:
        ext = ".bin"  # It's a file (image, zip, etc.)

    # 4. Generate a filename with a timestamp
    filename = f"received_{int(time.time())}{ext}"
    filepath = os.path.join(SAVE_DIR, filename)

    # 5. Save to disk
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    
    print(f"💾 SUCCESS! File saved at: {filepath}")
    return filepath

def receive_qr_stream():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    received_chunks = {}
    total_chunks = 0
    is_receiving = False

    print(f"\n📡 RECEIVER READY. Files will be saved in: {os.path.abspath(SAVE_DIR)}\n")

    while True:
        ret, frame = cap.read()
        if not ret: break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        decoded_objects = decode(gray, symbols=[ZBarSymbol.QRCODE])

        for obj in decoded_objects:
            try:
                text = obj.data.decode("utf-8")
                
                # Check for our specific format: "Index/Total:Data"
                if ":" in text and "/" in text:
                    header, data = text.split(":", 1)
                    part_str, total_str = header.split("/")
                    
                    part = int(part_str)
                    total_chunks = int(total_str)
                    is_receiving = True

                    # Only save if we haven't seen this chunk before
                    if part not in received_chunks:
                        received_chunks[part] = data
                        print(f" >> ✅ Received Chunk {part} / {total_chunks}")

                # Draw green box for feedback
                pts = np.array(obj.polygon, dtype=np.int32)
                cv2.polylines(frame, [pts], True, (0, 255, 0), 3)

            except Exception:
                pass

        # --- Screen Interface ---
        if is_receiving:
            h, w, _ = frame.shape
            
            # Draw Progress Bar
            percent = len(received_chunks) / total_chunks
            cv2.rectangle(frame, (0, h-40), (w, h), (50, 50, 50), -1)
            cv2.rectangle(frame, (0, h-40), (int(w * percent), h), (0, 255, 0), -1)

            # Show Status Text
            msg = f"Progress: {len(received_chunks)}/{total_chunks} Chunks"
            cv2.putText(frame, msg, (20, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # --- COMPLETION TRIGGER ---
            if len(received_chunks) == total_chunks:
                print("🎉 All chunks collected!")
                
                # Call our helper function to build and save
                saved_path = reconstruct_and_save(received_chunks, total_chunks)
                
                if saved_path:
                    # Close camera and open file
                    cap.release()
                    cv2.destroyAllWindows()
                    open_file_automatically(saved_path)
                    return  # Stop the program

        cv2.imshow("QR Receiver", frame)
        if cv2.waitKey(1) & 0xFF == 27: # ESC to quit
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    receive_qr_stream()
