import socket
import select
import sys
import threading
import time

# custom classes and constants
import raft
import constants

# Global variables
self_id = int(sys.argv[1])
port = constants.CLIENT_PORT_PREFIX + self_id
peers = constants.CONNECTION_GRAPH[self_id]
raftServer = raft.RaftServer()

# Create and bind sockets
soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
soc.setblocking(False)
soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
soc_send = []
for i in range(constants.NUM_CLIENT):
    temp_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc_send.append(temp_soc)
soc.bind((constants.HOST,port))
soc.listen(constants.NUM_CLIENT)

# handle keyboard inputs
def keyboard_input(request):
    global run
    if len(request) == 0:
        pass
    elif request[0] == "exit":
        run = 0
    elif request[0] == "i":
        initiate()
    else:
        enter_error("Invalid keyboard command") 

# handle network inputs
def network_input(sock, msg):
    print(msg[constants.HEADER_SIZE-1])
    t = msg[constants.HEADER_SIZE-1]
    if t == 117:
        thread = threading.Thread(target=unencoded_input, args=(sock,msg,))
    else:
        thread = threading.Thread(target=encoded_input, args=(sock,msg,))
    thread.start()

inputSockets = [soc.fileno(), sys.stdin.fileno()]
while raftServer.run:
    inputready, outputready, exceptready = select.select(inputSockets, [], [])

    for x in inputready:
        if x == soc.fileno(): # new client joins
            client, address = soc.accept()
            inputSockets.append(client)
        elif x == sys.stdin.fileno(): # input received via keyboard
            request = sys.stdin.readline().split()
            thread = threading.Thread(target=keyboard_input, args=(request,), daemon=True)
            thread.start()
        else:   # data received from socket
            msg_received = x.recv(constants.MESSAGE_SIZE)
            if len(msg_received) != constants.MESSAGE_SIZE:
                enter_error('Incorrectly padded message received.')
                inputSockets.remove(x)
            else:
                thread = threading.Thread(target=network_input, args=(x, msg_received,), daemon=True)
                thread.start()
