from multiprocessing import Queue, Process, Event
from typing import Any, List
from abc import ABC, abstractmethod
from datetime import datetime
from edgine.src.config.config_server import ConfigServer
from edgine.src.config.config import Config
from edgine.src.logger import ERROR, INFO, DEBUG, LOG
import time
import queue


class EdgineBase(Process, ABC):

    def __init__(self,
                 name: str,
                 stop_event: Event,
                 config_server: ConfigServer,
                 logging_q: Queue,
                 in_q: Queue = None,
                 out_qs: List[Queue] = None,
                 min_runtime: float = 0.01,
                 **kwargs):
        Process.__init__(self, name=name)
        self._stop_event: Event = stop_event

        if out_qs is None:
            out_qs = []

        self._cfg: Config = config_server.get_config_copy()
        self._name: str = name
        self._logging_q: Queue = logging_q
        self._in_q: Queue = in_q
        self._out_qs: List[Queue] = out_qs
        self._min_runtime: float = min_runtime
        self._blogic_time: float = 0.005
        self._get_time: float = 0.005
        self._post_time: float = 0.005

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def get_from_q(self) -> Any:
        """
        Get data from input Q
        :return: The data from the input Q
        """
        if self._in_q is None:
            return None

        try:
            data = self._in_q.get(timeout=self._min_runtime/2.0)
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
            self.debug(f"Posting output to {len(self._out_qs)} queue{'s' if len(self._out_qs) > 1 else ''}")
            for q in self._out_qs:
                q.put_nowait(data)
        except Exception as e:
            self.error(f"Unknown exception in post_to_qs : {e}")
            return False
        finally:
            return True

    def run(self) -> None:
        """Do stuff"""
        self.info("Hello")
        while not self._stop_event.is_set():
            self._cfg.update()
            s = time.time()
            if self._in_q is not None:
                data = self.get_from_q()
            else:
                data = None

            e = time.time()
            el1 = e-s
            self._get_time = 0.8*self._get_time + 0.2*el1

            s = time.time()
            out = self.blogic(data_in=data)
            e = time.time()
            el2 = e-s
            self._blogic_time = 0.8*self._blogic_time + 0.2*el2

            s = time.time()
            self.post_to_qs(out)
            e = time.time()
            el3 = e-s
            self._post_time = 0.8*self._post_time + 0.2*el3

            # Do we need to sleep?
            sleep_time = self._min_runtime - (el1+el2+el3)
            if sleep_time > 0:
                self.debug(f"Sleeping for {sleep_time:.2f} additional seconds")
                self._stop_event.wait(timeout=sleep_time)

            self.debug(f"Stop event : {self._stop_event.is_set()}")

        if self._in_q is not None:
            self._in_q.close()

        if len(self._out_qs) > 0:
            for out_q in self._out_qs:
                out_q.close()

        self.info(f"Quitting")
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
            print(f"!!!({timestr}) [LOG_QUEUE_ERROR] {e} while "
                  f"sending msg : {msg}")

    def error(self, msg: str):
        self.print(ERROR, msg)

    def info(self, msg: str):
        self.print(INFO, msg)

    def debug(self, msg: str):
        self.print(DEBUG, msg)

    def log(self, msg: str):
        self.print(LOG, msg)
