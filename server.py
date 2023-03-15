import socket
import select
import sys
import threading
import time
import pickle

# custom classes and constants
import raft
import constants
import helpers

# Global variables
self_id = int(sys.argv[1])
port = constants.CLIENT_PORT_PREFIX + self_id
peers = constants.CONNECTION_GRAPH[self_id]
initiated = False

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

# Create RaftNode
raftServer = raft.RaftNode(self_id, peers, soc_send)

# handle unencoded network inputs
def unencoded_input(sock, msg, self_id):
    t = msg[constants.HEADER_SIZE-1]
    if t != 117:
        helpers.enter_error("wrong function called on: unencoded_input")
    num_bytes = int(msg[:constants.HEADER_SIZE-1].decode())
    msg_string = msg[constants.HEADER_SIZE:constants.HEADER_SIZE + num_bytes].decode()
    data = msg_string.split()
    if data[0] == "Connection": # socket connection
        print(' '.join(data))
        sock.send("Successfully connected to {}".format(self_id).encode())
    else:
        helpers.enter_error('Received message that is incorrectly formatted.')

# handle encoded network inputs

def encoded_input(sock, msg, self_id):
    t = msg[constants.HEADER_SIZE-1]
    if t != 101:
        helpers.enter_error("wrong function called on: encoded_input")
    num_bytes = int(msg[:constants.HEADER_SIZE-1].decode())
    msg_string = msg[constants.HEADER_SIZE:constants.HEADER_SIZE + num_bytes].decode()
    num_bytes_enc = int(msg[constants.HEADER_SIZE + num_bytes:2*constants.HEADER_SIZE + num_bytes].decode())
    enc_obj = msg[2*constants.HEADER_SIZE + num_bytes:2*constants.HEADER_SIZE + num_bytes + num_bytes_enc]
    data = msg_string.split()
    data.append(enc_obj)
    if data[0] == "Connection": # socket connection
        print(' '.join(data))
        sock.send("Successfully connected to {}".format(self_id).encode())
    else:
        obj = pickle.loads(enc_obj)
        if obj['type'] == 'request_vote':
            raftServer.handle_vote_request(obj)
        elif obj['type'] == 'append_entries':
            sender = int(msg_string)
            raftServer.handle_append_entries(sender, obj)
        elif obj['type'] == 'vote_response':
            raftServer.handle_vote_response(obj)
        elif obj['type'] == 'append_response':
            raftServer.handle_append_response(obj)
        elif obj['type'] == 'ack':
            raftServer.handle_ack(obj)
        else:
            helpers.enter_error('Received message that is incorrectly formatted.')

# handle keyboard inputs
def keyboard_input(request):
    global run, initiated
    if len(request) == 0:
        pass
    elif request[0] == "exit":
        run = 0
    elif request[0] == "i":
        initiated = True
        raftServer.instantiate_sockets()
    else:
        helpers.enter_error("Invalid keyboard command") 

# handle network inputs
def network_input(sock, msg):
    t = msg[constants.HEADER_SIZE-1]
    if t == 117:
        thread = threading.Thread(target=unencoded_input, args=(sock,msg,self_id,))
    else:
        thread = threading.Thread(target=encoded_input, args=(sock,msg,self_id))
    thread.start()

inputSockets = [soc.fileno(), sys.stdin.fileno()]
while True:
    if initiated:
        thread = threading.Thread(raftServer.check_timeout(), daemon=True)
        thread.start()
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
                helpers.enter_error('Incorrectly padded message received.')
                inputSockets.remove(x)
            else:
                thread = threading.Thread(target=network_input, args=(x, msg_received,), daemon=True)
                thread.start()
