from multiprocessing import Queue, Process
from abc import ABC, abstractmethod
from datetime import datetime
from edgine.src.config import ConfigServer, Config
import time


class EdgineBase(Process, ABC):

    def __init__(self, name: str, config: Config, logging_q: Queue, **kwargs):
        Process.__init__(self, name=name)
        self._cfg: Config = config
        self._name: str = name
        self._logging_q: Queue = logging_q
        self._loop_time: int = 5

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def run(self) -> None:
        """Do stuff"""
        s = time.time()
        self.blogic()
        e = time.time()
        # filter it a bit
        self._loop_time = 0.8*self._loop_time + 0.2*(e-s)*1000

    @abstractmethod
    def blogic(self) -> None:
        """Business logic"""
        a = 5 + 6

    def log(self, level: int, msg: str):
        try:
            self._logging_q.put_nowait({level: [self._name, msg]})
        except Exception as e:
            timestr: str = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            print(f"({timestr}) [LOG_QUEUE_ERROR] {e} while "
                  f"sending msg : {msg}")

    def error(self, msg: str):
        self.log(self._cfg.logging_error, msg)

    def info(self, msg: str):
        self.log(self._cfg.logging_info, msg)

    def debug(self, msg: str):
        self.log(self._cfg.logging_debug, msg)
