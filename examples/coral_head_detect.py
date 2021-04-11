from edgine.src.config.config_server import ConfigServer
from edgine.src.base import EdgineBase
from edgine.src.starter import EdgineStarter
from typing import Any
import cv2
import numpy as np
import random
import string
import time
import platform
import collections
import tflite_runtime.interpreter as tflite

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
        config_server.config.create_if_unknown("resize_target", (320, 320))
        config_server.save_config()

    def blogic(self, data_in: Any = None) -> Any:
        res_img = None if data_in is None else cv2.resize(data_in, tuple(self._cfg.resize_target))
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
        config_server.config.create_if_unknown("detect_model_file",
                                               "models/head_detector_v2_320x320_ssd_mobilenet_v2_quant_edgetpu.tflite")
        config_server.config.create_if_unknown("top_k", 10)
        config_server.config.create_if_unknown("min_score", 0.8)
        config_server.save_config()

        self._interpreter = None
        self._input_details = None
        self._output_details = None

    def prerun(self) -> None:
        self._interpreter = tflite.Interpreter(
            model_path=self._cfg.detect_model_file,
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

        count = min(int(self._interpreter.get_tensor(self._output_details[3]['index'])), self._cfg.top_k)
        boxes = self._interpreter.get_tensor(self._output_details[0]['index'])[0][:count + 1]
        # class_ids = self._interpreter.get_tensor(self._output_details[1]['index'])[0][:count+1]
        scores = self._interpreter.get_tensor(self._output_details[2]['index'])[0][:count + 1]

        # ymin, xmin, ymax, xmax

        result = [BBox(xmin=np.maximum(0.0, boxes[i][1]),
                       ymin=np.maximum(0.0, boxes[i][0]),
                       xmax=np.minimum(1.0, boxes[i][3]),
                       ymax=np.minimum(1.0, boxes[i][2]))
                  for i in range(count) if scores[i] >= self._cfg.min_score]

        return result


class PrintRandom(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="RAND",
                            **kwargs)

    def blogic(self, data_in: Any = None) -> Any:
        letters = string.ascii_letters
        out = ''.join(random.choice(letters) for i in range(10))
        self.info(out)
        return None


def append_bboxs_to_img(cv2_im, bboxs):
    height, width, channels = cv2_im.shape
    for bbox in bboxs:
        x0, y0, x1, y1 = list(bbox)
        x0, y0, x1, y1 = int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height)
        cv2_im = cv2.rectangle(cv2_im, (x0, y0), (x1, y1), (0, 255, 0), 2)

    return cv2_im


if __name__ == "__main__":
    print("Canny edge detection example")
    starter = EdgineStarter(config_file="coral_head_detect_config.json")
    starter.reg_service(Getter)
    starter.reg_service(Resizer)
    starter.reg_service(Detect)
    starter.reg_service(PrintRandom, min_runtime=10)
    starter.reg_connection(0, 1)
    starter.reg_connection(1, 2)
    q3 = starter.reg_sink(0)
    q4 = starter.reg_sink(2)
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

        try:
            last_bboxs = q4.get_nowait()
        except Exception:
            pass

        append_bboxs_to_img(img, last_bboxs)

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
