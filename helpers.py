import constants
import pickle
from enum import Enum
import rsa

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

# send a string and a byte object over socket via padding and encryption
def send_padded_msg_encoded(sock, msg, msg_enc, pk):
    encoded_msg = msg.encode()
    num_bytes = len(encoded_msg)
    msg_enc = rsa.decrypt(msg_enc, pk) # encryption
    num_bytes_enc = len(msg_enc)
    header = header_s(num_bytes, "e")
    header_enc = header_s(num_bytes_enc, "")
    if num_bytes + num_bytes_enc > constants.MESSAGE_SIZE - len(header) - len(header_enc):
        enter_error('Message too big!')
    padding_length = constants.MESSAGE_SIZE - num_bytes - num_bytes_enc - len(header) - len(header_enc)
    padded_msg = b''.join([header, encoded_msg, header_enc, msg_enc, padding(padding_length)])
    sock.sendall(padded_msg)

def to_string(obj):
    json_obj = pickle.dumps(obj)
    return json_obj

# format keyboard input
def process_input(request):
    type, client_ids, dict_id, key, value = None, [], -1, None, None
    type = request[0]
    if type in constants.valid_commands:
        if type == 'create':
            client_ids=get_client_ids(request)
        elif type in ['get', 'put']:
            dict_id = request[1]
            key  = request[2]
            if type == 'put':
                value = request[3]
    return type, client_ids, dict_id, key, value

def get_client_ids(request):
    return request[1:]

# writing to / reading from disc
class DiscLog:
    def __init__(self, self_id):
        self.file_name = 'log' + str(self_id) + '.pickle'
        self.file_name_keys = 'keys' + str(self_id) + '.pickle'
        self.size = 0 # number of entries written to disc
    
    # commit a new log
    def commit(self, new_log_entry):
        file = open(self.file_name, 'ab')
        pickle.dump(new_log_entry, file)
        self.size += 1
        file.close()

    # write rsa keys to disc
    def save_keys(self, keys):
        file = open(self.file_name_keys, 'wb')
        pickle.dump(keys, file)
        file.close()
    
    # read from disc
    def read(self):
        file = open(self.file_name, 'rb')
        disc_log = []
        for _ in range(self.size):
            disc_log.append(pickle.load(file))
        file.close()
        return disc_log
    def read_keys(self): # read dictionary containing rsa keys
        file = open(self.file_name_keys, 'rb')
        keys = pickle.load(file)
        file.close()
        return keys
    

# dictionary commands
class Command:
    def __init__(self, type, issuer_id=-1, client_ids=[], dict_id=None, key=None, value=None):
        self.type = type
        self.issuer_id = issuer_id
        self.client_ids = client_ids
        self.dict_id = dict_id
        self.key = key
        self.value = value

    def get_log_entry(self, pk, dict_pk, dict_sk):
        log_entry = {}
        log_entry['type'] = get_command_name(self.type)
        log_entry['dict_id'] = self.dict_id
        if self.type == CommandType.CREATE:
            log_entry['client_ids'] = self.client_ids
            log_entry['dict_pk'] = dict_pk
            for client_id in self.client_ids:
                log_entry[('encrypted_key', client_id)] = rsa.encrypt(dict_sk, pk[client_id])
        elif self.type in [CommandType.PUT, CommandType.GET]:
            log_entry['issuer_id'] = self.issuer_id
            log_entry['encrypted_key'] = rsa.encrypt(self.key, dict_pk)
            if self.type == CommandType.PUT:
                log_entry['encrypted_value'] = rsa.encrypt(self.value, dict_pk)
        return log_entry

class CommandType(Enum):
    CREATE = 0
    PUT = 1
    GET = 2

def get_command_type(type):
    if type == 'create':
        return CommandType.CREATE
    elif type == 'put':
        return CommandType.CREATE
    elif type == 'get':
        return CommandType.CREATE
    else:
        enter_error('invalid command type in get_command_type()')
        raise Exception()
def get_command_name(type):
    if type == CommandType.CREATE:
        return 'create'
    elif type == CommandType.PUT:
        return 'put'
    elif type == CommandType.GET:
        return 'get'
    else:
        enter_error('invalid command type in get_command_name()')
        raise Exception()