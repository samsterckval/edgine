from multiprocessing import Queue
import queue
from typing import List, Any
import json
from datetime import datetime
from edgine.src.logger.cte import INFO, LOG, DEBUG, ERROR


class Config:
    """
    Config object

    This is fluid and contains all configurations of the application

    """

    def __init__(self,
                 logging_q: Queue = None,
                 in_q: Queue = None,
                 start_version: int = 0,
                 name: str = "None",
                 master: bool = False) -> None:
        self._logging_q: Queue = logging_q
        self.changelist: List = []
        self._initialized: bool = False
        self._master: bool = master
        self._name: str = name
        self._in_q: Queue = in_q
        self._version: int = start_version
        self._unique_names: List[str] = list(self.__dict__.keys())
        self._unique_names.append("_unique_names")
        self.changelist: List = []
        self._initialized = True

    def create_if_unknown(self, key, value) -> bool:
        """
        Checks if a key already exists, if not creates it with the value
        :param key: key
        :param value: value
        :return: True if created
        """
        if not self.has_key(key) and self._master:
            self.__setattr__(key, value)
            return True
        else:
            return False

    def has_key(self, key: str) -> bool:
        """
        Check if this config has a key
        :param key: Key to check
        :return: True/False
        """
        if key in self.__dict__.keys():
            return True
        else:
            return False

    def update(self) -> bool:
        """
        This will check if there is an update in the pipe
        :return: bool
        """
        updated = False

        if self._in_q is not None:

            c = 0
            while c < 1000:
                try:
                    data: List[str, Any] = self._in_q.get_nowait()
                    key = data[0]
                    value = data[1]
                    if key not in self._unique_names:
                        self.__dict__[key] = value
                        self.info(f"updated : {key}: {value}")
                        updated = True
                    else:
                        self.debug(f"Trying to update unique value {key}. Skipping.")
                        continue
                except queue.Empty:
                    break
                except Exception as e:
                    self.error(f"Unknown exception in Config.update : {e}")
                    return False

        return updated

    def __setattr__(self, name: str, value: Any) -> None:
        if "_master" not in self.__dict__.keys():
            self.__dict__[name] = value
            return
        elif self._master:
            self.__dict__[name] = value
            self.changelist.append([name, value])
            return

        if "_initialized" in self.__dict__.keys():
            if not self._initialized:
                self.__dict__[name] = value
                # self.changelist.append([name, value])
            else:
                raise PermissionError(f"Config {self._name} is read only, "
                                      f"set attributes in master config.")
        else:
            self.__dict__[name] = value

    def __getattr__(self, name) -> Any:
        """
        This may look stupid, but it works, so shut up.

        :param name: name of the wanted attribute
        :return: value of the attribute
        """
        if name in self.__dict__.keys():
            return self.__dict__[name]
        else:
            raise AttributeError(f"This config has "
                                 f"no attribute {name}")

    def __str__(self, pretty: bool = False) -> str:
        if pretty:
            out = json.dumps(self.__dict__, sort_keys=True, indent=4)
        else:
            out = json.dumps(self.__dict__, sort_keys=True)

        return out

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
