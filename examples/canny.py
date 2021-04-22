from edgine.src.config.config_server import ConfigServer
from edgine.src.base import EdgineBase
from edgine.src.starter import EdgineStarter
from typing import List, Any
import os
import cv2
import numpy as np
import random
import string


class Getter(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="GET",
                            **kwargs)

        self._images_list: List = os.listdir(os.path.join(os.getcwd(), "images"))
        self.info(f"Found {len(self._images_list)} images")
        self._img_pointer: int = 0

    def blogic(self, data_in: Any = None) -> Any:
        path = os.path.join(os.getcwd(), "images", self._images_list[self._img_pointer])
        self.debug(f"got img {self._img_pointer}")
        out = cv2.imread(path)
        self._img_pointer += 1
        if self._img_pointer >= len(self._images_list):
            self._img_pointer = 0
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
    starter = EdgineStarter(config_file="canny_config.json")
    starter.reg_service(Getter, min_runtime=1)
    starter.reg_service(Resizer)
    starter.reg_service(Canny)
    starter.reg_service(PrintRandom, min_runtime=10)
    starter.reg_connection(0, 1)
    starter.reg_connection(1, 2)
    q3 = starter.reg_sink(2)
    starter.init_services()
    starter.start()

    img = np.random.randint(255, size=(300, 300, 3), dtype=np.uint8)

    while True:
        try:
            img = q3.get(timeout=0.5)
        except Exception:
            pass

        cv2.imshow('frame', img)
        if cv2.waitKey(66) & 0xFF == ord('q'):
            starter.stop()
            break

    cv2.destroyAllWindows()

    print("All done!")
