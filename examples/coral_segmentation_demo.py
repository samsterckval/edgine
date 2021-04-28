from edgine.src.config.config_server import ConfigServer
from edgine.src.base import EdgineBase
from edgine.src.starter import EdgineStarter
from typing import Any
import cv2
import numpy as np
import random
import string
import time
import tflite_runtime.interpreter as tflite
import platform


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
        self.alpha = 1.1  # Contrast [1.0 - 3.0]
        self.beta = -30  # Brightness [-100 - 100]

    # def prerun(self) -> None:
    #     self._cap = cv2.VideoCapture(self._cam_id)

    def blogic(self, data_in: Any = None) -> Any:
        # ret, out = self._cap.read()
        out = cv2.imread("images/maps_screenshot4.png")
        # out[:, :, 0] = out[:, :, 0]*1.0
        # out[:, :, 1] = out[:, :, 1]*1.0
        # out[:, :, 2] = out[:, :, 2]*1.0
        out = cv2.convertScaleAbs(out, alpha=self.alpha, beta=self.beta)
        return out


class Resizer(EdgineBase):
    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="RES",
                            config_server=config_server,
                            **kwargs)
        config_server.create_if_unknown("resize_target", (128, 128))
        config_server.save_config()

    def blogic(self, data_in: Any = None) -> Any:
        res_img = None if data_in is None else cv2.resize(data_in, tuple(self.cfg.resize_target))
        return res_img


class Segmenter(EdgineBase):
    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="SEG",
                            config_server=config_server,
                            **kwargs)
        config_server.create_if_unknown("segmentation_model_file",
                                        "models/satellite_building_segment_128_quant_edgetpu.tflite")
        config_server.save_config()
        self._interpreter = None
        self._input_details = None
        self._output_details = None

    def prerun(self) -> None:
        self._interpreter = tflite.Interpreter(
            model_path=self.cfg.segmentation_model_file,
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
        output_details = self._interpreter.get_output_details()[0]
        prediction = np.squeeze(self._interpreter.get_tensor(output_details['index']))

        predic_mask = create_mask(prediction)
        predic_mask = np.array(predic_mask, dtype=np.uint8)
        predic_mask = predic_mask * 255
        return predic_mask


def create_mask(predic_mask):
    predic_mask = np.argmax(predic_mask, axis=-1)
    predic_mask = predic_mask[..., np.newaxis]
    return predic_mask


if __name__ == "__main__":

    print("Segmentation edge detection example")
    starter = EdgineStarter(config_file="coral_earth_demo_config.json")
    getter_id = starter.reg_service(Getter)  # {"type": "Getter", "file": "getter.py", "min_runtime": none}
    resizer_id = starter.reg_service(Resizer)
    segmenter_id = starter.reg_service(Segmenter)
    starter.reg_connection(getter_id, resizer_id)
    starter.reg_connection(resizer_id, segmenter_id)
    q3 = starter.reg_sink(getter_id)
    q4 = starter.reg_sink(segmenter_id)
    starter.init_services()
    starter.start()

    img = np.random.randint(255, size=(300, 300, 3), dtype=np.uint8)
    prediction_mask = np.random.randint(255, size=(128, 128), dtype=np.uint8)
    s = time.time()
    fps = 30.0
    while True:
        try:
            img = q3.get(timeout=0.5)
        except Exception:
            continue
        try:
            prediction_mask = q4.get_nowait()
        except Exception:
            pass

        pred_mask_color = cv2.cvtColor(prediction_mask, cv2.COLOR_GRAY2RGB)

        pred_mask_color = cv2.resize(pred_mask_color, img.shape[:2][::-1])

        # dst = cv2.addWeighted(img, 0.5, pred_mask_color, 0.5, 0)
        dst = cv2.bitwise_or(img, pred_mask_color)

        cv2.putText(dst,
                    text=f"{fps:.1f}FPS",
                    fontFace=cv2.FONT_HERSHEY_DUPLEX,
                    color=(255, 255, 255),
                    thickness=1,
                    fontScale=0.5,
                    org=(10, 20))
        cv2.putText(dst,
                    text="Press q to quit",
                    fontFace=cv2.FONT_HERSHEY_DUPLEX,
                    color=(255, 255, 255),
                    thickness=1,
                    fontScale=0.5,
                    org=(10, 40))
        cv2.imshow('frame', dst)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            starter.stop()
            break
        e = time.time()
        el = e - s
        s = time.time()
        if el != 0:
            fps = 0.8 * fps + 0.2 * (1.0 / el)

    cv2.destroyAllWindows()
    print("All done!")
