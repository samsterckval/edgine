from multiprocessing import Queue
from datetime import datetime
from edgine.src.config import ConfigServer, Config


class EdgineBase:

    def __init__(self, name: str, config: Config, logging_q: Queue, **kwargs):
        self._cfg: Config = config
        self._name: str = name
        self._logging_q: Queue = logging_q

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    def log(self, level: int, msg: str):
        try:
            self._logging_q.put_nowait({level: [self._name, msg]})
        except Exception as e:
            timestr: str = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            print(f"({timestr}) [LOG_QUEUE_ERROR] {e} while sending msg : {msg}")

    def error(self, msg: str):
        self.log(self._cfg.logging_error, msg)

    def info(self, msg: str):
        self.log(self._cfg.logging_info, msg)

    def debug(self, msg: str):
        self.log(self._cfg.logging_debug, msg)
