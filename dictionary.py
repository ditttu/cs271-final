import helpers
import constants
import rsa

class Dictionary:
    def __init__(self, client_ids):
        self.client_ids = client_ids
        self.dict = {}

    def put(self, key, value):
        self.dict[key] = value

    def get(self, key):
        if key not in self.dict:
            return None
        return self.dict[key]
    
    def print_dict(self):
        print(self.dict)
        print('---')

class Dictionaries:
    dict_id = 0
    def __init__(self, client_id):
        self.dicts = {}
        self.client_id = client_id
        self.dict_pk = {}
        self.dict_sk = {}
        self.pk = {} # client public keys

    def create(self, client_ids):
        dict_id = self.generate_dict_id()
        self.dicts[dict_id] = Dictionary(client_ids)
        print(f"Dictionary Created. ID : {dict_id}. Public Key: {self.dict_pk[dict_id]}. Clients : {client_ids}\n---")


        return dict_id
    
    def put(self, dict_id, key, value):
        if self.check_dict_id(dict_id):
            self.dicts[dict_id].put(key, value)
    
    def get(self, dict_id, key):
        if self.check_dict_id(dict_id):
            value = self.dicts[dict_id].get(key)
            if value != None:
                print(f'Dictionary_{dict_id}[{key}] = {value}')

    def printDict(self, dict_id):
        if self.check_dict_id(dict_id):
            print(f'Dictionary ID : {dict_id}')
            self.dicts[dict_id].print_dict()

    def printAll(self):
        print('---\nPrinting all dictionaries:\n---')
        for dict_id in self.dicts:
            if self.client_id in self.dicts[dict_id]:
                self.printDict(dict_id)

    # helper functions
    def generate_dict_id(self):
        self.dict_id += 1
        return (self.client_id, self.dict_id)
    
    def check_dict_id(self, dict_id):
        if dict_id not in self.dicts:
            helpers.enter_error(f"Dictionary {dict_id} is not recognized by this server")
            return False
        return True