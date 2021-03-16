from multiprocessing import Process, Queue, Event
from typing import Dict
from datetime import datetime
import queue
import time
from edgine.src.config import Config as cfg
import json


class EdgineLogger(Process):
    """
    A asynchroneous logger with rate limiting
    """

    def __init__(self,
                 stop_event: Event,
                 incoming_q: Queue,
                 outgoing_q: Queue = None,
                 outgoing_method: str = "json",
                 print_to_screen: bool = True,):

        super(EdgineLogger, self).__init__()
        self._incoming_q: Queue = incoming_q
        self._outgoing_q: Queue = outgoing_q
        self._outgoing_method: str = outgoing_method
        self._print_to_screen: bool = print_to_screen
        self._stop_event: Event = stop_event
        self._screen_rate_limit: int = cfg.screen_log_rate_limiter

        self._allowance_screen: float = self._screen_rate_limit
        self._last_screen_msg: float = time.time()
        self._dropped_screen_msg_count: int = 0

        self._last_screen_rate_limiter_print: float = time.time()
        self._last_mqtt_rate_limiter_print: float = time.time()

    @property
    def dropped_msg_count(self):
        return self._dropped_screen_msg_count

    @property
    def incoming_q(self) -> Queue:
        return self._incoming_q

    @incoming_q.setter
    def incoming_q(self, value: Queue):
        self._incoming_q = value

    @property
    def outgoing_q(self) -> Queue:
        return self._outgoing_q

    @outgoing_q.setter
    def outgoing_q(self, value: Queue):
        self._outgoing_q = value

    @property
    def outgoing_method(self) -> str:
        return self.outgoing_method

    @outgoing_method.setter
    def outgoing_method(self, value: str):
        self._outgoing_method = value

    @property
    def print_to_screen(self) -> bool:
        return self._print_to_screen

    @print_to_screen.setter
    def print_to_screen(self, value: bool):
        self._print_to_screen = value

    @property
    def stop_event(self) -> Event:
        return self._stop_event

    def get_dropped_msg_count(self) -> int:
        return self.dropped_msg_count

    def create_output_line(self, level: int, sender: str, msg: str) -> str:
        try:
            timestr: str = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            out = f"{cfg.logging_levels[level]}:({timestr}) [{sender}] {msg}"
        except Exception as e:
            self.display(self.create_output_line(cfg.logging_error,
                                                 'LOG',
                                                 f"Error in create_output_line with (lvl, sender, message):({level}, {sender}, {msg}) : {str(e)}"))
            out = ""
        return out

    def print_screen_rate_limiter(self):
        """
        Prints the rate limiting messages
        :return: None
        """
        if self._dropped_screen_msg_count > 0:
            self.output(cfg.logging_info,
                        'LOG',
                        f"Screen rate limiter dropped {self._dropped_screen_msg_count} messages in the last second")

        self._dropped_screen_msg_count = 0
        self._last_screen_rate_limiter_print = time.time()

    def display(self, msg: str):
        """
        Prints the messages to screen
        :param msg: the message to print
        :return: none
        """
        if self.print_to_screen:
            # Check how long it has been since last message
            now = time.time()
            time_passed = now - self._last_screen_msg

            # Update the time of the last message
            self._last_screen_msg = now

            # Update the allowance of messages to the screen, and cap it
            self._allowance_screen += time_passed * float(self._screen_rate_limit)
            if self._allowance_screen >= self._screen_rate_limit:
                self._allowance_screen = self._screen_rate_limit

            # Check if we can still print a message, if so, print it, else, drop it
            if self._allowance_screen >= 1.0:
                print(msg)
                self._allowance_screen -= 1.0
            else:
                self._dropped_screen_msg_count += 1

    def output(self, level: int, sender: str, msg: str):
        if sender not in cfg.screen_logging_rejection_list and cfg.screen_logging_level > level:
            self.display(self.create_output_line(level, sender, msg))

    def run(self) -> None:
        self.output(cfg.logging_info, "LOG", "Logger is live!")

        while not self._stop_event.is_set():

            try:
                incoming_data: Dict = self.incoming_q.get_nowait()

                for level, [sender, msg] in incoming_data.items():
                    self.output(level, sender, msg)
            except queue.Empty:
                self._stop_event.wait(timeout=0.01)
            except Exception as e:
                self.output(cfg.logging_error, "LOG", f"Error in run : {str(e)}")

            if time.time() - self._last_screen_rate_limiter_print > 1.0:
                self.print_screen_rate_limiter()

        while not self._incoming_q.empty():
            try:
                tmp = self._incoming_q.get_nowait()
            except queue.Empty:
                pass

        while not self._incoming_q.empty():
            try:
                tmp = self._outgoing_q.get_nowait()
            except queue.Empty:
                pass

        self._incoming_q.close()
        if (self._outgoing_q is not None):
            self._outgoing_q.close()

        self.output(cfg.logging_info,
                    'LOG',
                    "Quitting.")
