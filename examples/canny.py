from edgine.src.config.config_server import ConfigServer
from edgine.src.config.config import Config
from edgine.src.base import EdgineBase
from multiprocessing import Event, Queue
from typing import List, Any
import os
import cv2


class Step1(EdgineBase):

    def __init__(self,
                 stop_event: Event,
                 logging_q: Queue,
                 in_q: Queue,
                 out_qs: List[Queue],
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            stop_event=stop_event,
                            name="Step1",
                            logging_q=logging_q,
                            in_q=in_q,
                            out_qs=out_qs,
                            config_server=config_server)

        self._images_list: List = os.listdir(os.path.join(os.getcwd(), "images"))
        self._img_pointer: int = 0

    def blogic(self, data_in: Any = None) -> Any:
        out = cv2.imread(self._images_list[self._img_pointer])
        return out


if __name__ == "__main__":
    print("Canny edge detection example")
    global_stop = Event()
    cs = ConfigServer(stop_event=global_stop, config_file="canny_config.json")

