import cv2
import imagezmq

image_hub = imagezmq.ImageHub(open_port='tcp://localhost:5555', REQ_REP=False)

# image_hub.send_reply(b'OK')

while True:  # show streamed images until Ctrl-C
    rpi_name, image = image_hub.recv_image()
    cv2.imshow(rpi_name, image)  # 1 window for each RPi
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    # image_hub.send_reply(b'OK')
