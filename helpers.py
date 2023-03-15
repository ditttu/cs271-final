import constants
import pickle

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

# handle unencoded network inputs
def unencoded_input(sock, msg, self_id):
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

def to_string(obj):
    json_obj = pickle.dumps(obj)
    return json_obj
def encoded_input(sock, msg, self_id):
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

# writing to / reading from disc
class DiscLog:
    def __init__(self, self_id):
        self.file_name = 'log' + str(self_id) + '.pickle'
        self.size = 0 # number of entries written to disc
    
    # commit a new log
    def commit(self, new_log_entry):
        file = open(self.file_name, 'ab')
        pickle.dump(new_log_entry, file)
        self.size += 1
        file.close()
    
    # read from disc
    def read(self):
        file = open(self.file_name, 'rb')
        disc_log = []
        for _ in range(self.size):
            disc_log.append(pickle.load(file))
        file.close()
        return disc_log