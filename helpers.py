import constants
import pickle
import random
import rsa
from enum import Enum
import aes as AES
import os


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
def send_padded_msg_encoded(sock, msg, msg_enc, pk):
    encoded_msg = msg.encode()
    num_bytes = len(encoded_msg)
    msg_enc = encrypt(msg_enc, pk) # encryption
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
id = 0
def process_input(request, self_id):
    global id
    type, client_ids, dict_id, key, value = None, [], -1, None, None
    type = request[0]
    if type in constants.valid_commands:
        if type == 'create':
            id += 1
            dict_id = '({},{})'.format(id, self_id)
            client_ids=get_client_ids(request)
        elif type in ['get', 'put']:
            dict_id = request[1]
            key  = request[2]
            if type == 'put':
                value = request[3]
    return type, client_ids, dict_id, key, value

def get_client_ids(request):
    ans = [int(i) for i in request[1:]]
    return ans

# writing to / reading from disc
def commit(obj, file_name):
    obj.soc_send = []
    obj.election_timer = None
    obj.connected = [False]*constants.NUM_CLIENT
    with open(file_name, "wb") as point:
        pickle.dump(obj,point)
    
# read from disc
def read(filename):
    with open(filename, "rb") as point:
        disk_log = pickle.load(point)
    return disk_log
    

# commands
class Command:
    def __init__(self, type, client_ids=[], dict_id=None, key=None, value=None, issuer_id = -1):
        self.type = type
        self.client_ids = client_ids
        self.issuer_id = issuer_id
        self.dict_id = dict_id
        self.key = key
        self.value = value

    def get_log_entry(self, pk, dict_pk, dict_sk):
        log_entry = {}
        log_entry['type'] = get_command_name(self.type)
        log_entry['dict_id'] = self.dict_id
        log_entry['issuer_id'] = self.issuer_id
        if self.type == CommandType.CREATE:
            log_entry['client_ids'] = self.client_ids
            log_entry['dict_pk'] = dict_pk
            for client_id in self.client_ids:
                log_entry[('encrypted_key', client_id)] = encrypt(pickle.dumps(dict_sk), pk[int(client_id)])
        elif self.type in [CommandType.PUT, CommandType.GET]:
            log_entry['encrypted_key'] = encrypt(self.key.encode(), dict_pk)
            if self.type == CommandType.PUT:
                log_entry['encrypted_value'] = encrypt(self.value.encode(), dict_pk)
        return log_entry

class CommandType(Enum):
    CREATE = 0
    PUT = 1
    GET = 2

def get_command_type(type):
    if type == 'create':
        return CommandType.CREATE
    elif type == 'put':
        return CommandType.PUT
    elif type == 'get':
        return CommandType.GET
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
    
def encrypt(msg, pk):
    aes_key = os.urandom(16)
    nonce = os.urandom(16)
    ciphertext = AES.AES(aes_key).encrypt_ctr(msg, nonce)
    enc_aes_key = rsa.encrypt(aes_key, pk)
    enc_obj = {"nonce":nonce, "ciphertext":ciphertext, "enc_key":enc_aes_key}
    enc = pickle.dumps(enc_obj)
    return enc

def decrypt(ct, sk):
    enc_obj = pickle.loads(ct)
    aes_nonce = enc_obj["nonce"]
    ciphertext = enc_obj["ciphertext"]
    enc_aes_key = enc_obj["enc_key"]
    aes_key = rsa.decrypt(enc_aes_key, sk)
    msg = AES.AES(aes_key).decrypt_ctr(ciphertext, aes_nonce)
    return msg