from multiprocessing import Queue, Process, Event, Array
from multiprocessing.queues import Queue as Q
from ctypes import c_int8
from typing import Any, List
from abc import ABC, abstractmethod
from datetime import datetime
from edgine.src.config.config_server import ConfigServer
from edgine.src.config.config import Config
from edgine.src.logger.cte import ERROR, INFO, DEBUG, LOG
import time
import queue


class EdgineBase(Process, ABC):

    def __init__(self,
                 name: str,
                 stop_event: Event,
                 config_server: ConfigServer,
                 logging_q: Queue,
                 data_in: Queue = None,
                 secondary_data_in_list: List[Queue] = None,
                 data_out_list: List[Queue] = None,
                 min_runtime: float = 0.001,
                 **kwargs):
        Process.__init__(self, name=name)
        self._stop_event: Event = stop_event

        if data_out_list is None:
            data_out_list = []

        self.cfg: Config = config_server.get_config_copy()
        self._name: str = name
        self._logging_q: Queue = logging_q
        self._data_in: Queue = data_in
        self._secondary_data_in: List[Queue] = secondary_data_in_list
        self.secondary_data: List[Any] = [None] * len(self._secondary_data_in)
        self._data_out_list: List[Queue] = data_out_list
        self._min_runtime: float = min_runtime
        self._blogic_time: float = 0.005
        self._get_time: float = 0.005
        self._second_get_time: float = 0.005
        self._post_time: float = 0.005

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def update_secondary_data(self) -> None:
        """Update the secondary input data"""
        for i in range(len(self._secondary_data_in)):
            if not self._secondary_data_in[i].empty():
                self.secondary_data[i] = self._secondary_data_in[i].get_nowait()

    def get_from_q(self) -> Any:
        """
        Get data from input Q
        :return: The data from the input Q
        """
        if self._data_in is None:
            return None

        try:
            data = self._data_in.get(timeout=self._min_runtime / 2.0)
            self.debug(f"Data found of type {type(data)}")
            return data
        except queue.Empty:
            return None
        except Exception as e:
            self.error(f"Unknown exception in in_q.get_nowait : {e}")

    def post_to_qs(self, data: Any) -> bool:
        """
        Post data to each output Q
        :param data: data to post
        :return: True if no exception
        """
        if data is None:
            return True

        try:
            self.debug(f"Posting output to {len(self._data_out_list)} queue{'s' if len(self._data_out_list) > 1 else ''}")
            posted = False
            for q in self._data_out_list:
                if not q.full():
                    q.put_nowait(data)
                    posted = True

            # if not posted:
            #     self._stop_event.wait(timeout=0.01)
        except Exception as e:
            self.error(f"Unknown exception in post_to_qs : {e}")
            return False
        finally:
            return True

    def run(self) -> None:
        """Do stuff"""
        self.info("Hello")

        self.cfg.update()

        self.prerun()

        while not self._stop_event.is_set():
            self.cfg.update()
            s = time.time()
            data = self.get_from_q() if self._data_in is not None else None
            e = time.time()
            el1 = e-s
            self._get_time = 0.8*self._get_time + 0.2*el1

            s = time.time()
            self.update_secondary_data()
            e = time.time()
            el2 = e-s
            self._second_get_time = 0.8*self._second_get_time + 0.2*el2

            s = time.time()
            out = self.blogic(data_in=data) if data is not None or self._data_in is None else None
            e = time.time()
            el3 = e-s
            self._blogic_time = 0.8*self._blogic_time + 0.2*el3

            s = time.time()
            if out is not None:
                self.post_to_qs(out)
            e = time.time()
            el4 = e-s
            self._post_time = 0.8*self._post_time + 0.2*el4

            # Do we need to sleep?
            sleep_time = self._min_runtime - (el1+el2+el3+el4)

            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)

        for q in self._data_out_list:
            q.close()

        if self._data_in is not None:
            while not self._data_in.empty():
                tmp = self._data_in.get_nowait()
            self._data_in.close()

        self.postrun()

        self.info(f"Quitting")

    def prerun(self) -> None:
        """This will be run before the main loop of the process, overwrite it to implement your own."""
        return

    def postrun(self) -> None:
        """This will be run right before we exit the Process"""
        return

    @abstractmethod
    def blogic(self, data_in: Any = None) -> Any:
        """Business logic, overwrite this method to implement your own logic"""
        return data_in+6 if type(data_in) == int else data_in

    def print(self, level: int, msg: str):
        try:
            self._logging_q.put_nowait({level: [self._name, msg]})
        except Exception as e:
            timestr: str = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            print(f"!!!({timestr}) [LOG_QUEUE_ERROR@{self.name}] {e} while "
                  f"sending msg : {msg}")

    def error(self, msg: str):
        self.print(ERROR, msg)

    def info(self, msg: str):
        self.print(INFO, msg)

    def debug(self, msg: str):
        self.print(DEBUG, msg)

    def log(self, msg: str):
        self.print(LOG, msg)
