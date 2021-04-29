from typing import List, Tuple
from edgine.src.config.config_server import ConfigServer
from edgine.src.logger.edgine_logger import EdgineLogger
from multiprocessing import Queue, Event


class EdgineStarter:

    def __init__(self, config_file: str = "cfg.json"):
        print(ART)
        self.user_service_types: List = []
        self._user_services: List = []
        self._connections: List[tuple] = []
        self._qs: List[Queue] = []
        self._sink_qs: List[Queue] = []
        self._sink_prod_ids: List[int] = []
        self.min_runtimes: List[float] = []
        self.secondary_connections: List[Tuple] = []
        self.secondary_qs: List[Queue] = []
        self.logging_q: Queue = Queue()
        self.global_stop: Event = Event()
        self._log_stop: Event = Event()
        self.config_server = ConfigServer(stop_event=self.global_stop,
                                          config_file=config_file,
                                          name="CS",
                                          logging_q=self.logging_q)
        self.logger = EdgineLogger(stop_event=self._log_stop,
                                   config_server=self.config_server,
                                   in_q=self.logging_q,
                                   out_qs=[])

    def _has_connection(self, cons_id: int):
        out = False
        for conn in self._connections:
            if conn[1] == cons_id:
                out = True

        return out

    def reg_service(self, service_type, min_runtime: float = 0.001) -> int:
        """ Registers a new service """
        new_q = Queue(maxsize=2)
        self._qs.append(new_q)
        self.min_runtimes.append(min_runtime)
        self.user_service_types.append(service_type)
        return len(self.user_service_types) - 1

    def reg_connection(self, prod_id: int, cons_id: int):
        if self._has_connection(cons_id):
            raise ValueError(f"Consumer with ID {cons_id} [{type(self.user_service_types[cons_id])}] already has a primary connection")

        self._connections.append((prod_id, cons_id))

    def reg_secondary_connection(self, prod_id: int, cons_id: int):
        """ Creates a secondary data connection """
        self.secondary_connections.append((prod_id, cons_id))
        new_q = Queue(maxsize=2)
        self.secondary_qs.append(new_q)

    def reg_sink(self, prod_id: int) -> Queue:
        new_q = Queue(maxsize=2)
        self._sink_qs.append(new_q)
        self._sink_prod_ids.append(prod_id)
        return new_q

    def init_services(self):

        self.logger.start()
        self.config_server.start()

        for i in range(len(self.user_service_types)):
            in_q = self._qs[i] if self._has_connection(i) else None
            out_qs = []
            for conn in self._connections:
                if conn[0] == i:
                    out_qs.append(self._qs[conn[1]])

            for j in range(len(self._sink_prod_ids)):
                if self._sink_prod_ids[j] == i:
                    out_qs.append(self._sink_qs[j])

            tmp_second_q = []
            for j in range(len(self.secondary_connections)):
                if self.secondary_connections[j][1] == i:
                    tmp_second_q.append(self.secondary_qs[j])
                elif self.secondary_connections[j][0] == i:
                    out_qs.append(self.secondary_qs[j])

            service = self.user_service_types[i](stop_event=self.global_stop,
                                                 logging_q=self.logging_q,
                                                 config_server=self.config_server,
                                                 data_in=in_q,
                                                 data_out_list=out_qs,
                                                 secondary_data_in_list=tmp_second_q,
                                                 min_runtime=self.min_runtimes[i])

            self._user_services.append(service)

    def start(self):
        print(f"Starting {len(self._user_services)} services:")

        for service in self._user_services:
            print(f" | - {service.name}")
            service.start()

    def stop(self):
        self.global_stop.set()
        for service in reversed(self._user_services):
            service.join(timeout=2)
            if service.exitcode is None:
                print(f"Service {service.name} did not exit properly. Terminating...")
                service.terminate()

        self._log_stop.set()
        self.logger.join(timeout=2)
        if self.logger.exitcode is None:
            print(f"Logger {self.logger.name} did not exit properly. Terminating...")
            self.logger.terminate()


ART = """      &%%%%%%%%%%%%%%&                    /%&*                     &%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
      &%%%&                               /%%%&                  %%%%%.
      &%%%@                      ,#@@@/   /%%%&        ,&@@@@( %%%%%.             .#@@@@%,           .#@@@@&,
      &%%%@                  .%%%%%%%%%%%%%%%%&     &%%%%%%%%%%%%%,            &%%%%%&&%%%%&.     &%%%%%%%%%%%%&
      &%%%%%%%%%%%%%%%%%/   #%%%%/      /%%%%%&   #%%%%.      %%%%&   *%&,    *%%%#             #%%%&.       &%%%*
      &%%%&.............   .%%%&          &%%%&   %%%&         #%%%/  *%%%%    @%%%%%%&@@/     .%%%%%%%%%%%%%%%%%&
      &%%%@                .%%%&          &%%%&   %%%%.        &%%%*  *%%%%       *#&&&%%%%%&  .%%%%&@@@@@@@@@@@@@
      &%%%@                 %%%%%,      .%%%%%&   *%%%%&     /%%%%#   *%%%%    .*        #%%%(  &%%%&
      &%%%%%%%%%%%%%%%%%@    .%%%%%%%%%%%%&%%%&     %%%%%%%%%%%&      *%%%%   @%%%%%%@@%%%%%&    .%%%%%%%%%%%%%%/
      ###################        (&&&&&(  .###(          ...(&%%%%%   ,###(      (&&%%%%&%,          (%&&&&&%*
                                                               &%%%*
       .%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%*        &%%%,
                                                   &%%%%&%%%&%%%%%*
                                                     ,&%%%%%%%%#"""
