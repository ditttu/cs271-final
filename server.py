import socket
import select
import sys
import threading
import time
import random
import pickle

import constants

#Global variables
self_id = int(sys.argv[1])
port = constants.CLIENT_PORT_PREFIX + self_id
peers = constants.CONNECTION_GRAPH[self_id]
current_term = 0
voted_for = None
log = []
commit_index = 0
last_applied = 0
state = 'follower'
run = True

#Create and bind sockets
soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
soc.setblocking(False)
soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
soc_send = []
for i in range(constants.NUM_CLIENT):
    temp_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc_send.append(temp_soc)
soc.bind((constants.HOST,port))
soc.listen(constants.NUM_CLIENT)


# print errors
def enter_error(string):
    print(f'Warning: {string}')

# return padding of specific length
def padding(length):
    singlebyte = b'\xff'
    return b''.join([singlebyte for i in range(length)])

# calculate header size
def header_s(x, t):
    s = str(x) + t
    if len(s) > constants.HEADER_SIZE:
        enter_error('Header too big!')
    while(len(s) < constants.HEADER_SIZE):
        s = '0' + s
    return s.encode()

# send a string over socket via padding
def send_padded_msg(sock, msg):
    encoded_msg = msg.encode()
    num_bytes = len(encoded_msg)
    header = header_s(num_bytes, "u")
    if num_bytes > constants.MESSAGE_SIZE - len(header):
        enter_error('Message too big!')
    padding_length = constants.MESSAGE_SIZE - num_bytes - len(header)
    padded_msg = b''.join([header, encoded_msg, padding(padding_length)])
    sock.sendall(padded_msg)

# send a string and a byte object over socket via padding
def send_padded_msg_encoded(sock, msg, msg_enc):
    encoded_msg = msg.encode()
    num_bytes = len(encoded_msg)
    num_bytes_enc = len(msg_enc)
    header = header_s(num_bytes, "e")
    header_enc = header_s(num_bytes_enc, "")
    if num_bytes + num_bytes_enc > constants.MESSAGE_SIZE - len(header) - len(header_enc):
        enter_error('Message too big!')
    padding_length = constants.MESSAGE_SIZE - num_bytes - num_bytes_enc - len(header) - len(header_enc)
    padded_msg = b''.join([header, encoded_msg, header_enc, msg_enc, padding(padding_length)])
    sock.sendall(padded_msg)

#connect to all clients
def initiate():
    for i in range(constants.NUM_CLIENT):
        if i != self_id:
            soc_send[i].connect((constants.HOST, constants.CLIENT_PORT_PREFIX+i))
            send_padded_msg(soc_send[i],"Connection request from {}".format(self_id))
            received = soc_send[i].recv(constants.MESSAGE_SIZE)
            print(received)

def request_vote(candidate_term, candidate_id, last_log_index, last_log_term):
    # implement request vote RPC here
    pass

def append_entries(leader_term, leader_id, prev_log_index, prev_log_term, entries, leader_commit):
    # implement append entries RPC here
    pass

def send_request_vote(peer_id):
    # implement sending request vote to a peer here
    pass

def send_append_entries(peer_id):
    # implement sending append entries to a peer here
    pass

# handle unencoded network inputs
def unencoded_input(sock, msg):
    t = msg[constants.HEADER_SIZE-1]
    if t != 117:
        enter_error("wrong function called on: unencoded_input")
    num_bytes = int(msg[:constants.HEADER_SIZE-1].decode())
    msg_string = msg[constants.HEADER_SIZE:constants.HEADER_SIZE + num_bytes].decode()
    data = msg_string.split()
    if data[0] == "Connection": # socket connection
        print(' '.join(data))
        sock.send("Successfully connected to {}".format(self_id).encode())
    else:
        enter_error('Received message that is incorrectly formatted.')

# handle encoded network inputs
def encoded_input(sock, msg):
    t = msg[constants.HEADER_SIZE-1]
    if t != 65:
        enter_error("wrong function called on: encoded_input")
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
        enter_error('Received message that is incorrectly formatted.')

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
while run:
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
