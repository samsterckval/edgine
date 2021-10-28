import cv2
from multiprocessing import Process, Queue
import time
import queue

VIDEO = "../examples/videos/short.mp4"
WINDOW_NAME = "testing"


def get_frames(out_q: Queue, file: str):
    cap = cv2.VideoCapture(file)
    ret = True

    print(f"Playing video {file} to queue.")

    while ret:
        ret, img = cap.read()   # Read a new frame, or get ret == False if the video has ended

        out_q.put(img, timeout=1)          # Post the image to the output queue

    out_q.put("DONE", timeout=0.5)

    print(f"Video done, bye!")


def resize_frame(in_q: Queue, out_q: Queue):
    while True:
        try:
            img = in_q.get(timeout=1)
            if type(img) == str:
                out_q.put("DONE", timeout=0.5)
                break
            out = cv2.Canny(img, 100, 200)
            out_q.put(out, timeout=1)
        except Exception:
            break


def show_frames(in_q: Queue, window_name: str):
    while True:
        try:
            frame = in_q.get(timeout=1)
            if type(frame) == str:
                break

            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        # Somehow queue.Empty has changed in python3.8, but I don't know yet to what
        except Exception:
            print(f"Video seems done, bye!")
            break


def gen_frames(file: str):
    cap = cv2.VideoCapture(file)

    print(f"Playing video {file} as generator.")

    while True:
        ret, img = cap.read()
        if ret:
            yield img
        else:
            break


def processes():
    q1 = Queue(maxsize=4)  # This will prevent the ram usage to rise too much
    q2 = Queue(maxsize=4)
    get_t = Process(target=get_frames, args=(q1, VIDEO), name="GET")
    res_t = Process(target=resize_frame, args=(q1, q2), name="RES")
    do_t = Process(target=show_frames, args=(q2, WINDOW_NAME), name="DO")

    print(f"Let's go Q's!!")

    s = time.time()

    get_t.start()
    res_t.start()
    do_t.start()

    get_t.join()
    res_t.join()
    do_t.join()

    e = time.time()

    print(f"Q took {e-s}s.")

    print("All done!")


def generators():
    print(f"Let's go Generator!!")

    s = time.time()

    for frame in gen_frames(VIDEO):
        img = cv2.Canny(frame, 100, 200)
        cv2.imshow(WINDOW_NAME, img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    e = time.time()

    print(f"generator took {e-s}s.")

    print("All done!")


if __name__ == "__main__":
    processes()
    generators()


