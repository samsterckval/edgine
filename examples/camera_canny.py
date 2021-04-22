from edgine.src.config.config_server import ConfigServer
from edgine.src.base import EdgineBase
from edgine.src.starter import EdgineStarter
from typing import Any
import cv2
import numpy as np
import random
import string
import time


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
        config_server.config.create_if_unknown("resize_target", (300, 300))
        config_server.save_config()

    def blogic(self, data_in: Any = None) -> Any:
        res_img = None if data_in is None else cv2.resize(data_in, tuple(self.cfg.resize_target))
        return res_img


class Canny(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="CANN",
                            **kwargs)

    def blogic(self, data_in: Any = None) -> Any:
        edges = cv2.Canny(data_in, 100, 200)
        return edges


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


if __name__ == "__main__":
    print("Canny edge detection example")
    starter = EdgineStarter(config_file="camera_canny_config.json")
    starter.reg_service(Getter)
    starter.reg_service(Resizer)
    starter.reg_service(Canny)
    starter.reg_service(PrintRandom, min_runtime=10)
    starter.reg_connection(0, 1)
    starter.reg_connection(1, 2)
    q3 = starter.reg_sink(2)
    starter.init_services()
    starter.start()

    img = np.random.randint(255, size=(300, 300, 3), dtype=np.uint8)

    s = time.time()
    fps = 30.0

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
