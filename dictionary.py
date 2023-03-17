import helpers

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
    def __init__(self, client_id):
        self.dicts = {}
        self.client_id = client_id

    def create(self, client_ids, dict_id):
        self.dicts[dict_id] = Dictionary(client_ids)
        print(f"Dictionary Created. ID : {dict_id}. Clients : {client_ids}\n---")
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
            self.printDict(dict_id)

    # helper functions    
    def check_dict_id(self, dict_id):
        if dict_id not in self.dicts:
            helpers.enter_error(f"Dictionary {dict_id} is not recognized by this server")
            return False
        return True