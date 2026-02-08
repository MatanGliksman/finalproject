import cv2
import numpy as np
from pyzbar.pyzbar import decode, ZBarSymbol
import qr_protocol  # Import our new protocol


def main():
    cap = cv2.VideoCapture(0)
    cap.set(3, 1280)  # Width
    cap.set(4, 720)  # Height

    received_chunks = {}
    total_expected = 0
    active = False

    print("=== QR Receiver (Protocol V1) ===")
    print("Waiting for signal...")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # Computer Vision
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        decoded_objs = decode(gray, symbols=[ZBarSymbol.QRCODE])

        for obj in decoded_objs:
            text = obj.data.decode("utf-8")

            # --- USE PROTOCOL TO PARSE ---
            result = qr_protocol.parse_qr_payload(text)

            if result:
                idx, total, data = result

                # First valid chunk initializes the session
                if not active:
                    total_expected = total
                    active = True
                    print(f"📡 Incoming Data Detected: {total} chunks expected.")

                # Store if new
                if idx not in received_chunks:
                    received_chunks[idx] = data
                    print(f"   [+] Received Chunk {idx}/{total}")

                # Visual Feedback (Green Box)
                pts = np.array(obj.polygon, dtype=np.int32)
                cv2.polylines(frame, [pts], True, (0, 255, 0), 3)

        # --- UI & Logic ---
        if active:
            # Draw Progress Bar
            h, w, _ = frame.shape
            pct = len(received_chunks) / total_expected
            cv2.rectangle(frame, (0, h - 30), (int(w * pct), h), (0, 255, 0), -1)
            cv2.putText(frame, f"{len(received_chunks)}/{total_expected}", (10, h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Completion Check
            if len(received_chunks) == total_expected:
                print("🎉 Transfer Complete!")

                # --- USE PROTOCOL TO REBUILD ---
                filepath = qr_protocol.rebuild_file(received_chunks, total_expected)

                if filepath:
                    print(f"💾 Saved: {filepath}")
                    cap.release()
                    cv2.destroyAllWindows()
                    qr_protocol.open_file_native(filepath)
                    return

        cv2.imshow("Receiver", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
