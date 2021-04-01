from multiprocessing import Process, Queue, Event
from typing import Dict, List
from datetime import datetime
import queue
import time
from edgine.src.config.config import Config
from edgine.src.config.config_server import ConfigServer
import json

LOGGING_LEVELS = ['ERR', 'LOG', 'INF', 'DEB']
ERROR = 0
LOG = 1
INFO = 2
DEBUG = 3


class EdgineLogger(Process):
    """
    A asynchroneous logger with rate limiting
    """

    def __init__(self,
                 stop_event: Event,
                 config_server: ConfigServer,
                 in_q: Queue,
                 out_qs: List[Queue] = None):

        Process.__init__(self, name="LOG")

        if out_qs is None:
            self._out_qs: List = [None]
        else:
            self._out_qs: List[Queue] = [None, *out_qs]

        # Check if the right config fields already exist, if not, create them
        if not config_server.config.has_key("log_rate_limiting_list"):
            config_server.config.log_rate_limiting_list = []
            for i in range(len(self._out_qs)):
                config_server.config.log_rate_limiting_list.append(1000)
        elif len(config_server.config.log_rate_limiting_list) < len(self._out_qs):
            for i in range(len(self._out_qs) - len(config_server.config.log_rate_limiting_list)):
                config_server.config.log_rate_limiting_list.append(1000)

        if not config_server.config.has_key("log_rejection_list"):
            config_server.config.log_rejection_list = []
            for i in range(len(self._out_qs)):
                config_server.config.log_rejection_list.append([])
        elif len(config_server.config.log_rejection_list) < len(self._out_qs):
            for i in range(len(self._out_qs) - len(config_server.config.log_rejection_list)):
                config_server.config.log_rejection_list.append([])

        if not config_server.config.has_key("log_logging_lvl"):
            config_server.config.log_logging_lvl = []
            for i in range(len(self._out_qs)):
                config_server.config.log_logging_lvl.append(INFO)
        elif len(config_server.config.log_logging_lvl) < len(self._out_qs):
            for i in range(len(self._out_qs) - len(config_server.config.log_logging_lvl)):
                config_server.config.log_logging_lvl.append(INFO)

        if not config_server.config.has_key("log_print_to_screen"):
            config_server.config.log_print_to_screen = True

        config_server.save_config()

        self._cfg = config_server.get_config_copy()
        self._in_q: Queue = in_q

        self._stop_event: Event = stop_event

        # All other rate limiters
        self._log_allowance: List[float] = []
        self._log_last_msg: List[float] = []
        self._log_dropped_msg_count: List[int] = []
        self._log_last_limit_print: List[float] = []

        for i in range(len(self._out_qs)):
            self.init_rate_limiter(i)

    def init_rate_limiter(self, index: int):
        """
        Initialises the rate limiter for output at index
        :param index: index of the rate limiter to init
        :return: None
        """
        try:
            self._log_allowance[index] = self._cfg.log_rate_limiting_list[index]
            self._log_last_msg[index] = time.time()
            self._log_dropped_msg_count[index] = 0
            self._log_last_limit_print[index] = time.time()
        except IndexError as e:
            if len(self._log_allowance) == index:
                self._log_allowance.append(self._cfg.log_rate_limiting_list[index])
                self._log_last_msg.append(time.time())
                self._log_dropped_msg_count.append(0)
                self._log_last_limit_print.append(time.time())
            else:
                self.output(ERROR,
                            self.name,
                            f"Trying to init a rate_limiter further than 1 "
                            f"ahead of current index :"
                            f"len(list) = {len(self._log_allowance)}; index : {index}")

                raise IndexError(e)

    def create_output_line(self, level: int, sender: str, msg: str) -> str:
        """
        Create an output line
        :param level: Logging level of msg
        :param sender: Sender of msg
        :param msg: Message
        :return: Output line as str
        """
        try:
            timestr: str = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            out = f"{LOGGING_LEVELS[level]}:({timestr}) [{sender}] {msg}"
        except Exception as e:
            print(f"[ERR] %m/%d/%Y %H:%M:%S : "
                  f"Error in create_output_line with "
                  f"(lvl, sender, message):({level}, {sender}, {msg}) : {str(e)}")
            out = ""
        return out

    def print_rate_limiter(self, index: int):
        """
        Print rate limiting message
        :param index: index of output rate limiter
        :return: Nothing
        """

        if self._log_dropped_msg_count[index] > 0:
            self.output(INFO,
                        self.name,
                        f"Rate limiter dropped "
                        f"{self._log_dropped_msg_count[index]} messages to"
                        f"output {index} in the last second")

        self._log_dropped_msg_count[index] = 0
        self._log_last_limit_print[index] = time.time()

    def sent_out(self, index: int, msg: str):
        """
        This actually sends a message over a Q
        :param index: Index of the outgoing Q, index of 0 will use built-in print function
        :param msg: Message to send
        :return: Nothing
        """

        now = time.time()
        time_passed = now - self._log_last_msg[index]

        time_passed_since_rate_print = now - self._log_last_limit_print[index]

        if time_passed_since_rate_print > 1.0:
            self.print_rate_limiter(index)

        self._log_last_msg[index] = now

        self._log_allowance[index] += time_passed * float(self._cfg.log_rate_limiting_list[index])
        if self._log_allowance[index] >= self._cfg.log_rate_limiting_list[index]:
            self._log_allowance[index] = self._cfg.log_rate_limiting_list[index]

        if self._log_allowance[index] >= 1.0:
            if index == 0:
                print(msg)
            else:
                self._out_qs[index].put_nowait(msg)
            self._log_allowance[index] -= 1.0
        else:
            self._log_dropped_msg_count[index] += 1

    def output(self, lvl: int, sender: str, msg: str):
        out_str = self.create_output_line(lvl, sender, msg)

        for i in range(len(self._out_qs)):
            if sender not in self._cfg.log_rejection_list[i] and self._cfg.log_logging_lvl[i] >= lvl:
                self.sent_out(i, out_str)

    def run(self) -> None:
        self.output(INFO, self.name, f"Hello")

        stop_loop: bool = False

        while not stop_loop or not self._in_q.empty():

            self._cfg.update()

            try:
                incoming_data: Dict = self._in_q.get(timeout=0.005)

                for level, [sender, msg] in incoming_data.items():
                    self.output(level, sender, msg)
            except queue.Empty:
                self._stop_event.wait(timeout=0.01)
                if self._stop_event.is_set():
                    stop_loop = True
            except Exception as e:
                self.output(ERROR, self.name, f"Error in run : {str(e)}")

        self.output(INFO,
                    self.name,
                    "Quitting")
