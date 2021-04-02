from edgine.src.config.config_server import ConfigServer
from edgine.src.base import EdgineBase
from edgine.src.logger.edgine_logger import EdgineLogger
from multiprocessing import Event, Queue
from typing import List, Any
import os
import cv2
import numpy as np
import random
import string


class Step1(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="STP1",
                            **kwargs)

        self._images_list: List = os.listdir(os.path.join(os.getcwd(), "images"))
        self._img_pointer: int = 0

    def blogic(self, data_in: Any = None) -> Any:
        path = os.path.join(os.getcwd(), "images", self._images_list[self._img_pointer])
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
        config_server.config.resize_target = (300, 300)
        config_server.save_config()

    def blogic(self, data_in: Any = None) -> Any:
        res_img = None if data_in is None else cv2.resize(data_in, self._cfg.resize_target)
        return res_img


class Step2(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="STP2",
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
    global_stop = Event()
    log_q = Queue()
    q1 = Queue()
    q2 = Queue()
    q3 = Queue()
    cs = ConfigServer(stop_event=global_stop, config_file="canny_config.json", name="CS", logging_q=log_q)
    logger = EdgineLogger(stop_event=global_stop, config_server=cs, in_q=log_q, out_qs=[])
    step1 = Step1(stop_event=global_stop, logging_q=log_q, config_server=cs, out_qs=[q1], min_runtime=1)
    resizer = Resizer(stop_event=global_stop, logging_q=log_q, config_server=cs, in_q=q1, out_qs=[q2], min_runtime=0.1)
    step2 = Step2(stop_event=global_stop, logging_q=log_q, config_server=cs, in_q=q2, out_qs=[q3], min_runtime=1)
    randomPrint = PrintRandom(stop_event=global_stop, logging_q=log_q, config_server=cs, min_runtime=10)

    services = [cs, step1, resizer, step2, randomPrint, logger]

    print(f"Starting {len(services)} services:")

    for service in services:
        print(f" | - {service.name}")
        service.start()

    img = np.random.randint(255, size=(200, 200, 3), dtype=np.uint8)

    while True:
        try:
            img = q3.get(timeout=0.5)
        except Exception:
            pass

        cv2.imshow('frame', img)
        if cv2.waitKey(33) & 0xFF == ord('q'):
            global_stop.set()
            break

    cv2.destroyAllWindows()
    for service in services:
        service.join(timeout=2)

    for service in services:
        if service.is_alive():
            service.terminate()
            print(f"Service {service.name} has been terminated")

    print("All done!")
