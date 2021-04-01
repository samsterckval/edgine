from edgine.src.config.config_server import ConfigServer
from edgine.src.config.config import Config
from edgine.src.base import EdgineBase
from edgine.src.logger import EdgineLogger
from multiprocessing import Event, Queue
from typing import List, Any
import os
import cv2
import numpy as np
import time


class Step1(EdgineBase):

    def __init__(self,
                 stop_event: Event,
                 logging_q: Queue,
                 out_qs: List[Queue],
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            stop_event=stop_event,
                            name="STP1",
                            logging_q=logging_q,
                            in_q=None,
                            out_qs=out_qs,
                            config_server=config_server,
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


class Step2(EdgineBase):

    def __init__(self,
                 stop_event: Event,
                 logging_q: Queue,
                 in_q: Queue,
                 out_qs: List[Queue],
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            stop_event=stop_event,
                            name="STP2",
                            logging_q=logging_q,
                            in_q=in_q,
                            out_qs=out_qs,
                            config_server=config_server,
                            **kwargs)

    def blogic(self, data_in: Any = None) -> Any:
        edges = cv2.Canny(data_in, 100, 200)
        return edges


if __name__ == "__main__":
    print("Canny edge detection example")
    global_stop = Event()
    log_q = Queue()
    q1 = Queue()
    q2 = Queue()
    cs = ConfigServer(stop_event=global_stop, config_file="canny_config.json", name="CS")
    logger = EdgineLogger(stop_event=global_stop, config_server=cs, in_q=log_q, out_qs=[])
    step1 = Step1(stop_event=global_stop, logging_q=log_q, config_server=cs, out_qs=[q1], min_runtime=1)
    step2 = Step2(stop_event=global_stop, logging_q=log_q, config_server=cs, in_q=q1, out_qs=[q2], min_runtime=1)

    services = [cs, step1, step2, logger]

    print(f"Starting {len(services)} services:")

    for service in services:
        print(f" | {service.name}")
        service.start()

    img = np.random.randint(255, size=(200, 200, 3), dtype=np.uint8)

    while True:
        try:
            img = q2.get(timeout=0.5)
        except Exception:
            pass

        cv2.imshow('frame', img)
        if cv2.waitKey(1000) & 0xFF == ord('q'):
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

