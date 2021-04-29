from edgine.src.config.config_server import ConfigServer
from edgine.src.base import EdgineBase
from edgine.src.starter import EdgineStarter
from typing import Any
import cv2
import numpy as np
import time
import platform
import collections
import tflite_runtime.interpreter as tflite
import socket
import imagezmq

EDGETPU_SHARED_LIB = {
    'Linux': 'libedgetpu.so.1',
    'Darwin': 'libedgetpu.1.dylib',
    'Windows': 'edgetpu.dll'
}[platform.system()]


class Getter(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="GET",
                            **kwargs)

        self._cam_id: int = 0
        self._cap = None

    def prerun(self) -> None:
        self._cap = cv2.VideoCapture(self._cam_id)

    def blogic(self, data_in: Any = None) -> Any:
        ret, out = self._cap.read()
        return out


class Resizer(EdgineBase):

    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="RES",
                            config_server=config_server,
                            **kwargs)
        config_server.create_if_unknown("resize_target", (320, 320))
        config_server.save_config()

    def blogic(self, data_in: Any = None) -> Any:
        res_img = None if data_in is None else cv2.resize(data_in, tuple(self.cfg.resize_target))
        return res_img


class BBox(collections.namedtuple('BBox', ['xmin', 'ymin', 'xmax', 'ymax'])):
    """Bounding box.
    Represents a rectangle which sides are either vertical or horizontal, parallel
    to the x or y axis.
    """
    __slots__ = ()


class Detect(EdgineBase):

    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="DET",
                            config_server=config_server,
                            **kwargs)
        config_server.create_if_unknown("detect_model_file",
                                        "models/head_detector_v2_320x320_ssd_mobilenet_v2_quant_edgetpu.tflite")
        config_server.create_if_unknown("top_k", 10)
        config_server.create_if_unknown("min_score", 0.8)
        config_server.save_config()

        self._interpreterq = None
        self._input_details = None
        self._output_details = None

    def prerun(self) -> None:
        self._interpreter = tflite.Interpreter(
            model_path=self.cfg.detect_model_file,
            experimental_delegates=[tflite.load_delegate(EDGETPU_SHARED_LIB,
                                                         {})])
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

    def blogic(self, data_in: Any = None) -> Any:
        # make it a [1, h, w, c] array
        input_data = np.expand_dims(data_in, axis=0)

        # load data into the tensor
        self._interpreter.set_tensor(self._input_details[0]['index'], input_data)

        # run the inference
        self._interpreter.invoke()

        count = min(int(self._interpreter.get_tensor(self._output_details[3]['index'])), self.cfg.top_k)
        boxes = self._interpreter.get_tensor(self._output_details[0]['index'])[0][:count + 1]
        # class_ids = self._interpreter.get_tensor(self._output_details[1]['index'])[0][:count+1]
        scores = self._interpreter.get_tensor(self._output_details[2]['index'])[0][:count + 1]

        # ymin, xmin, ymax, xmax

        result = [BBox(xmin=np.maximum(0.0, boxes[i][1]),
                       ymin=np.maximum(0.0, boxes[i][0]),
                       xmax=np.minimum(1.0, boxes[i][3]),
                       ymax=np.minimum(1.0, boxes[i][2]))
                  for i in range(count) if scores[i] >= self.cfg.min_score]

        return result

    def postrun(self) -> None:
        del self._interpreter


class Drawer(EdgineBase):

    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="DRAW",
                            config_server=config_server,
                            **kwargs)
        config_server.create_if_unknown("bbox_color", (0, 255, 0))
        config_server.save_config()
        time.sleep(1)

    def blogic(self, data_in: Any = None) -> Any:
        if self.secondary_data[0] is not None:
            out = append_bboxs_to_img(data_in, self.secondary_data[0], color=self.cfg.bbox_color)
        else:
            out = None

        return out


class ExposeVideo(EdgineBase):

    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="EXPOSER",
                            config_server=config_server,
                            **kwargs)
        config_server.create_if_unknown("video_port", 3456)
        config_server.save_config()
        self.sender = None
        self.device_name = socket.gethostname()
        time.sleep(1)

    def prerun(self) -> None:
        connect_to = f"tcp://*:{self.cfg.video_port}"
        self.sender = imagezmq.ImageSender(connect_to=connect_to, REQ_REP=False)

    def blogic(self, data_in: Any = None) -> Any:
        self.sender.send_image(self.device_name, data_in)
        return None


def append_bboxs_to_img(cv2_im, bboxs, color=(0, 255, 0)):
    height, width, channels = cv2_im.shape
    for bbox in bboxs:
        x0, y0, x1, y1 = list(bbox)
        x0, y0, x1, y1 = int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height)
        cv2_im = cv2.rectangle(cv2_im, (x0, y0), (x1, y1), color, 2)

    return cv2_im


if __name__ == "__main__":
    print("Video generator with edge detection example")
    starter = EdgineStarter(config_file="coral_video_generator_config.json")

    getter_id = starter.reg_service(Getter)  # {"type": "Getter", "file": "getter.py", "min_runtime": none}
    resizer_id = starter.reg_service(Resizer)
    detect_id = starter.reg_service(Detect)
    drawer_id = starter.reg_service(Drawer)
    exposer_id = starter.reg_service(ExposeVideo)

    starter.reg_connection(getter_id, resizer_id)
    starter.reg_connection(resizer_id, detect_id)
    starter.reg_connection(getter_id, drawer_id)
    starter.reg_connection(drawer_id, exposer_id)

    starter.reg_secondary_connection(detect_id, drawer_id)

    q3 = starter.reg_sink(drawer_id)

    starter.init_services()
    starter.start()

    img = np.random.randint(255, size=(300, 300, 3), dtype=np.uint8)

    s = time.time()
    fps = 30.0

    last_bboxs = []

    while True:
        try:
            img = q3.get(timeout=0.5)
        except Exception:
            continue

        cv2.putText(img,
                    text=f"{fps:.1f}FPS",
                    fontFace=cv2.FONT_HERSHEY_DUPLEX,
                    color=(255, 255, 255),
                    thickness=1,
                    fontScale=0.5,
                    org=(10, 20))

        cv2.putText(img,
                    text="Press q to quit",
                    fontFace=cv2.FONT_HERSHEY_DUPLEX,
                    color=(255, 255, 255),
                    thickness=1,
                    fontScale=0.5,
                    org=(10, 40))

        cv2.imshow('frame', img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            starter.stop()
            break

        e = time.time()
        el = e - s
        s = time.time()
        fps = 0.8 * fps + 0.2 * (1.0 / el)

    cv2.destroyAllWindows()

    print("All done!")

