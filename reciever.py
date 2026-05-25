import cv2
import numpy as np
import qr_protocol
import time
import sys

try:
    from pyzbar.pyzbar import decode, ZBarSymbol
    USING_PYZBAR = True
    print("✅ Logic: Using Pyzbar (High Performance)")
except ImportError:
    USING_PYZBAR = False
    print("⚠️ Logic: Pyzbar not found. Using Standard OpenCV (Slower).")

WINDOW_NAME = "Receiver"


def show_ack_on_frame(frame, text, title):
    """
    Shows the ACK QR in a small non-blocking window.
    Uses waitKey(1) so the main loop keeps running and scanning.
    """
    img = qr_protocol.generate_qr_image(text, 0, 0, title=title)
    cv2.namedWindow("ACK", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ACK", 400, 400)
    cv2.imshow("ACK", img)
    cv2.waitKey(1)
    return frame


def scan_frame(frame, detector):
    results = []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if USING_PYZBAR:
        decoded_objs = decode(gray, symbols=[ZBarSymbol.QRCODE])
        for obj in decoded_objs:
            data = obj.data.decode("utf-8")
            pts = np.array(obj.polygon, dtype=np.int32)
            results.append((data, pts))
    else:
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        data, points, _ = detector.detectAndDecode(binary)
        if data and points is not None:
            pts = points.astype(int)
            results.append((data, pts))

    return results


def main():
    # Open camera once — stays open for all transfers
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    detector = None
    if not USING_PYZBAR:
        detector = cv2.QRCodeDetector()

    print("=== RECEIVER LISTENING (Encrypted) ===")

    # ── CONTINUOUS LOOP ──────────────────────────────────────────────────────
    while True:
        # Reset all state for each new transfer
        received_chunks = {}
        total_expected  = 0
        state           = "WAITING_HANDSHAKE"
        filename        = "unknown"
        current_batch   = 0
        aes_key         = None
        ack_clear_time  = 0
        transfer_done   = False

        print("\n👂 Waiting for next transfer... (Press Esc to quit)")

        # ── INNER SCAN LOOP — runs for one full transfer ─────────────────────
        while not transfer_done:
            ret, frame = cap.read()
            if not ret:
                continue

            found_qrs = scan_frame(frame, detector)

            for data, pts in found_qrs:
                # Draw green detection box
                if USING_PYZBAR:
                    cv2.polylines(frame, [pts], True, (0, 255, 0), 3)
                else:
                    for i in range(len(pts)):
                        pt1 = tuple(pts[i][0])
                        pt2 = tuple(pts[(i + 1) % len(pts)][0])
                        cv2.line(frame, pt1, pt2, (0, 255, 0), 3)

                mtype, content = qr_protocol.parse_control_msg(data)

                # --- STATE MACHINE ---

                if state == "WAITING_HANDSHAKE":
                    if mtype == "SYN":
                        total_expected = content['total']
                        filename       = content['filename']
                        aes_key        = qr_protocol.str_to_key(content['key'])
                        print(f"✅ Handshake! File: {filename} ({total_expected} chunks)")
                        print(f"🔑 Encryption key received and stored.")
                        frame = show_ack_on_frame(frame, "ACK:READY", "HANDSHAKE ACCEPTED")
                        ack_clear_time = time.time() + 1.0
                        state = "RECEIVING"

                elif state == "RECEIVING":
                    if mtype == "DATA":
                        res = qr_protocol.parse_qr_payload(data)
                        if res:
                            idx, tot, encrypted_chunk = res
                            if idx not in received_chunks:
                                received_chunks[idx] = encrypted_chunk
                                print(f"   📥 Chunk {idx}/{tot}")

                    elif mtype == "SYNC_CHECK":
                        batch_id = content
                        if batch_id == current_batch:
                            start   = batch_id * qr_protocol.BATCH_SIZE
                            end     = min(start + qr_protocol.BATCH_SIZE, total_expected)
                            needed  = range(start + 1, end + 1)
                            missing = [i for i in needed if i not in received_chunks]

                            if not missing:
                                print(f"✅ Batch {batch_id} complete.")
                                frame = show_ack_on_frame(
                                    frame, f"ACK:{batch_id}", "BATCH RECEIVED"
                                )
                                ack_clear_time = time.time() + 1.0
                                current_batch += 1
                            else:
                                print(f"⚠️ Batch {batch_id} missing: {missing}")
                                missing_str = ",".join(map(str, missing))
                                frame = show_ack_on_frame(
                                    frame,
                                    f"NACK:{batch_id}:{missing_str}",
                                    "RETRY REQUEST"
                                )
                                ack_clear_time = time.time() + 1.0

                    elif mtype == "DONE":
                        print("📡 DONE signal received. Rebuilding file...")
                        if aes_key and len(received_chunks) == total_expected:
                            path = qr_protocol.rebuild_file(
                                received_chunks, total_expected, aes_key, filename
                            )
                            if path:
                                qr_protocol.open_file_native(path)
                        else:
                            missing_count = total_expected - len(received_chunks)
                            print(f"⚠️ Still missing {missing_count} chunks.")

                        print("✅ Ready for next transfer.")
                        transfer_done = True  # break inner loop, reset state

            # Close ACK window after timer expires
            try:
                if time.time() > ack_clear_time and \
                        cv2.getWindowProperty("ACK", cv2.WND_PROP_VISIBLE) >= 1:
                    cv2.destroyWindow("ACK")
            except Exception:
                pass

            # GUI overlay
            cv2.putText(frame, f"State: {state}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            if aes_key:
                cv2.putText(frame, "ENCRYPTED", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            if total_expected > 0:
                count = len(received_chunks)
                cv2.putText(frame, f"Progress: {count}/{total_expected}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow(WINDOW_NAME, frame)

            # Esc to quit completely
            if cv2.waitKey(1) & 0xFF == 27:
                cap.release()
                cv2.destroyAllWindows()
                return

        # Inner loop ended (transfer_done) — outer loop will reset and listen again

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
