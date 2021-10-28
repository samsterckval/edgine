import zmq
import time

context = zmq.Context()
socket = context.socket(zmq.SUB)
# We can connect to several endpoints if we desire, and receive from all.
socket.connect('tcp://127.0.0.1:1234')

# We must declare the socket as of type SUBSCRIBER, and pass a prefix filter.
# Here, the filter is the empty string, wich means we receive all messages.
# We may subscribe to several filters, thus receiving from all.
socket.setsockopt_string(zmq.SUBSCRIBE, "")

while True:
    message = socket.recv_pyobj()
    print(message)
    time.sleep(0.1)
