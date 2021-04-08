from multiprocessing import Queue, Process, Event
from edgine.src.config.config import Config
from edgine.src.logger.cte import ERROR, LOG, DEBUG, INFO
import json
from datetime import datetime
from typing import List, Dict


class ConfigServer(Process):
    """
    This will hold the ground truth config and
    send updates to the external copies
    """
    def __init__(self,
                 stop_event: Event = None,
                 config_file: str = None,
                 logging_q: Queue = None,
                 name: str = "newConfigServer"):
        Process.__init__(self, name=name)
        if stop_event is not None:
            self._stop_event = stop_event
        else:
            self._stop_event = Event()

        self._logging_q: Queue = logging_q
        self._filepath: str = config_file
        self._name: str = name
        self.config: Config = Config(in_q=None, name="master-config", master=True)
        self.config._initialized = False
        self._child_qs: List[Queue] = []
        self.load_config()
        self.save_config()

    def get_clean_config_dict(self):
        config_dict = self.config.__dict__
        unique_names = config_dict['_unique_names']
        out_dict = {}
        for k, v in config_dict.items():
            if k not in unique_names:
                out_dict[k] = v

        return out_dict

    def run(self) -> None:
        self.info("starting ConfigServer")
        while not self._stop_event.is_set():
            while len(self.config.changelist) > 0:
                # print(f"Changelist found with len {len(self.config.changelist)}")
                self.update_children(self.config.changelist.pop(0))

            self._stop_event.wait(timeout=1)

        self.info("Quitting")

    def save_config(self) -> bool:
        """
        Save current config to file
        :return: False if no file or exception, True else
        """
        self.info("Saving config")
        if self._filepath is not None:
            try:
                config = self.get_clean_config_dict()
                with open(self._filepath, 'w+') as f:
                    json.dump(config, f, sort_keys=True, indent=4)
            except Exception as e:
                self.error(f"Exception during save_config method : {e}")
                return False
            finally:
                return True
        else:
            return False

    def load_config(self) -> bool:
        """
        Load a config from the config file
        :return: False if file not found, True else
        """
        try:
            with open(self._filepath, 'r') as f:
                config_dict: Dict = json.load(f)

                for k, v in config_dict.items():
                    self.config.__dict__[k] = v

                return True
        except IOError as e:
            self.error(f"File not accessible : {e}")
            return False
        except Exception as e:
            self.error(f"Unknown exception : {e}")
            return False

    def get_config_copy(self) -> Config:

        # Create a new queue
        new_q = Queue()

        # Create a new config
        new_config = Config(master=True, logging_q=self._logging_q)

        new_config._initialized = False

        # Copy all values into the new config copy
        for k, v in self.get_clean_config_dict().items():
            new_config.__dict__[k] = v

        # Change the new config's unique's
        new_config._in_q = new_q
        new_config._name = f"C-{len(self._child_qs)+1}"

        new_config._initialized = True
        new_config._master = False

        # Add Q to the list
        self._child_qs.append(new_q)

        return new_config

    def update_children(self, kv: List):
        for q in self._child_qs:
            q.put_nowait(kv)

    def __str__(self):
        return f"- {self._name} - "

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
