from multiprocessing import Queue
from typing import List, Callable, Any
import queue
import json


class Config:
    """
    Config object

    This is fluid and contains all configurations of the application

    """

    def __init__(self,
                 in_q: Queue = None,
                 start_version: int = 0,
                 name: str = "noname") -> None:
        self._in_q: Queue = in_q
        self._version: int = start_version
        self._name: str = name
        self._unique_names: List[str] = list(self.__dict__.keys())
        self._unique_names.append("_unique_names")
        self.__setattr__ = self.__setattr_overwrite

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
                    self.__dict__[data[0]] = data[1]
                    updated = True
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"Unknown exception in Config.update : {e}")
                    return False

        return updated

    def __setattr_overwrite(self, name: str, value: Any) -> None:

        if name not in self._unique_names:
            raise PermissionError(f"You can only set unique_names "
                                  f"attributes of child "
                                  f"Config {self._name}, "
                                  f"the rest is read only")
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
            self.update()
            if name in self.__dict__.keys():
                return self.__dict__[name]
            else:
                raise AttributeError(f"The config {self._name} has "
                                     f"no attribute {name}, not even "
                                     f"after updating.")

    def __str__(self, pretty: bool = False) -> str:
        if pretty:
            out = json.dumps(self.__dict__, sort_keys=True, indent=4)
        else:
            out = json.dumps(self.__dict__, sort_keys=True)

        return out


class ConfigMaster:
    """
    Master Config object

    This is the ground truth, and is write-only

    """

    def __init__(self, update_callback: Callable) -> None:
        self._version: int = 0
        self._callback: Callable = update_callback
        self._name: str = "c-master"
        self._unique_names: List[str] = list(self.__dict__.keys())
        self._unique_names.append("_unique_names")

    def __setattr__(self, name, value) -> None:
        self.__dict__[name] = value

        if name not in self._unique_names:
            self._callback(name, value)

    def __getattr__(self, name) -> None:
        """
        Just don't
        """
        raise PermissionError(f"You cannot read from the "
                              f"master config, use this as setup")

    def get_clean_dict(self) -> dict:
        out_dict = self.__dict__
        for name in self._unique_names:
            out_dict.pop(name)

        return out_dict

    def __str__(self, pretty: bool = False) -> str:
        # Copy the self dict, so that we can pop the unique names
        out_dict = self.__dict__
        out_dict.pop('_unique_names')

        if pretty:
            out = json.dumps(out_dict, sort_keys=True, indent=4)
        else:
            out = json.dumps(out_dict, sort_keys=True)

        return out


class ConfigServer:
    """
    This will hold the ground truth config and
    send updates to the external copies
    """
    def __init__(self, filepath: str):
        self._filepath = filepath
        self.config = ConfigMaster(self.update_children)
        self._child_qs: List[Queue] = []

    def get_config_copy(self) -> Config:
        # Create a new queue
        new_q = Queue()

        # Create a new config
        new_config = Config()

        # Copy all values into the new config copy
        for k, v in self.config.get_clean_dict().items():
            new_config.__dict__[k] = v

        # Change the new config's unique's
        new_config._in_q = new_q
        new_config.name = f"C-{len(self._child_qs)+1}"

        # Add Q to the list
        self._child_qs.append(new_q)

        return new_config

    def update_children(self, name, value):
        for q in self._child_qs:
            q.put_nowait([name, value])
