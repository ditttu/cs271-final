import time
import threading
import constants
import dictionary
import helpers
import random
import socket
import rsa
import pickle
from enum import Enum

class RaftState(Enum):
    LEADER = 1
    FOLLOWER = 2
    CANDIDATE = 3


class RaftNode:
    def __init__(self, node_id, peers, soc_list):
        # initialize node_id and peer nodes
        self.node_id = node_id
        self.peers = peers
        self.state = RaftState.FOLLOWER
        self.election_timer = None
        
        # initialize persistent state
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.dicts = dictionary.Dictionaries(self.node_id)

        # initialize rsa keys
        self.pk = {x : None for x in range(constants.NUM_CLIENT)}
        (self.pk[self.node_id], self.sk) = rsa.newkeys(constants.KEY_LENGTH)

        # initialize volatile state
        self.commit_index = -1
        self.last_applied = -1
        
        # initialize leader state
        self.next_index = {peer: 0 for peer in self.peers}
        self.match_index = {peer: 0 for peer in self.peers}
        self.commit_maj = []
        self.leader_id = None
        
        # start election timer
        self.votes_received = set()
        self.last_heartbeat_timestamp = time.time()

        # sockets
        self.soc_send = soc_list.copy()
        self.connected = [False]*len(soc_list)

    def instantiate_sockets(self, firstConnection=True):
        for node_id in self.peers:
            try:
                self.fix_link(node_id, firstConnection=firstConnection)
            except:
                helpers.enter_error("Couldn't connect to {}".format(node_id))
        self.dicts.pk = self.pk

    def become_leader(self):
        if self.state != RaftState.CANDIDATE:
            return
        print("Became Leader")
        print("Term = {}".format(self.current_term))
        self.state = RaftState.LEADER
        self.leader_id = self.node_id
        self.votes_received = set()
        self.commit_maj = [set() for log in self.log]
        self.stop_election_timer()
        
        self.next_index = {peer: len(self.log) for peer in self.peers}
        self.match_index = {peer: 0 for peer in self.peers}
        
        self.send_heartbeat()

    def become_follower(self):
        if self.state != RaftState.FOLLOWER:
            print("Became follower")
            self.state = RaftState.FOLLOWER
        self.votes_received = set()
        
    def send_heartbeat(self):
        self.last_heartbeat_timestamp = time.time()
        for node_id in self.peers:
            if node_id == self.node_id:
                continue
            self.send_append_entries(node_id)
        
    def start_leader_election(self):
        self.current_term += 1
        self.voted_for = self.node_id
        self.state = RaftState.CANDIDATE
        print("Started new election. Term = {}".format(self.current_term))
        self.reset_election_timer()
        
        self.votes_received = set()
        self.votes_received.add(self.node_id)
        for node_id in self.peers:
            if node_id == self.node_id:
                continue
            self.send_request_vote(node_id)
        
    def request_vote(self, candidate_id, candidate_term, last_log_index, last_log_term):
        if candidate_term > self.current_term:
            self.current_term = candidate_term
            self.voted_for = None
            self.become_follower()
            
        if candidate_term < self.current_term:
            return candidate_id, False, self.current_term
        
        if self.voted_for is not None and self.voted_for != candidate_id:
            return candidate_id, False, self.current_term
        
        last_index = len(self.log) - 1
        last_term = self.log[last_index]['term'] if last_index >= 0 else 0
        
        if last_log_term < last_term or (last_log_term == last_term and last_log_index < last_index):
            return candidate_id, False, self.current_term
        
        self.voted_for = candidate_id
        self.reset_election_timer()
        print("Returned Vote To {}".format(candidate_id))
        return candidate_id, True, candidate_term
        
    def append_entries(self, leader_term, leader_id, prev_log_index, prev_log_term, entries, leader_commit):
        if leader_term < self.current_term:
            return False, self.current_term, prev_log_index
        if leader_term > self.current_term or (leader_term == self.current_term and (prev_log_index+1) >= len(self.log)):
            self.current_term = leader_term
            if self.leader_id != leader_id:
                print("Updated leader to {}".format(leader_id))
                self.leader_id = leader_id
            self.voted_for = None
            self.become_follower()

        self.reset_election_timer()
        if len(self.log) != 0 and prev_log_index >=0 and (prev_log_index > len(self.log) or self.log[prev_log_index]['term'] != prev_log_term):
            return False, self.current_term, prev_log_index

        index = prev_log_index
        for entry in entries:
            index += 1
            if index < len(self.log) and self.log[index]['term'] != entry['term']:
                del self.log[index:]
            if index >= len(self.log):
                self.log.append(entry)
        
        if leader_commit > self.commit_index:
            self.commit_index = min(leader_commit, len(self.log) - 1)
        
        return True, leader_term, index
        
    def vote_response(self, voter_id, term, vote_granted):
        if self.state != RaftState.CANDIDATE or term != self.current_term:
            return
        
        if vote_granted:
            self.votes_received.add(voter_id)
        
        if len(self.votes_received) > len(self.peers) // 2:
            self.become_leader()
        
    def append_response(self, follower_id, term, success, match_index):
        if self.state != RaftState.LEADER or term != self.current_term:
            return
        if success:
            self.next_index[follower_id] = match_index + 1
            self.match_index[follower_id] = match_index
            
            if match_index > self.commit_index and self.log[match_index]['term'] == self.current_term:
                for i in range(self.commit_index,match_index+1):
                    self.commit_maj[i].add(follower_id)
                    if len(self.commit_maj[i]) > len(self.peers) // 2:
                        self.commit_index = i
                self.apply_log_entries()
        else:
            self.next_index[follower_id] = (self.next_index[follower_id] - 1) if (self.next_index[follower_id] > 0) else 0
            if self.next_index[follower_id] > self.match_index[follower_id]:
                self.send_append_entries(self, follower_id)

    def ack(self, leader_id, term, apply_index):
        if leader_id == self.leader_id and term == self.current_term:
            if apply_index <= len(self.log):
                self.commit_index = apply_index
                self.apply_log_entries()

    def leader_add(self, log_entry):
        if self.state != RaftState.LEADER:
            return False
        else:
            self.commit_maj.append(set())
            self.log.append(log_entry)
            return True

    def apply_log_entries(self):
        for i in range(self.last_applied + 1, self.commit_index + 1):
            cmd = self.log[i]['command']
            self.last_applied = i

            self.apply_log_entry(cmd)
            
            
            if self.leader_id == self.node_id:
                for node_id in self.peers:
                    if node_id == self.node_id:
                        continue
                    self.send_ack(node_id)

    def apply_log_entry(self, command):
        cmd_type = helpers.get_command_type(command['type'])
        dict_id = tuple(map(int,command['dict_id'][1:-1].split(',')))
        print(dict_id)
        issuer_id = command['issuer_id']
        if cmd_type == helpers.CommandType.CREATE:
            if self.node_id not in command['client_ids']:
                print('Cannot create dictionary the client is not a part of.')
                return
            if issuer_id not in command['client_ids']:
                print('Cannot create dictionary. Invalid issuer ID.')
                return
            dict_key = ('encrypted_key', self.node_id)
            print(dict_key)
            print(command)
            if dict_key not in command:
                raise Exception('incorrectly formatted log entry')
            dict_pk = command['dict_pk']
            dict_sk = pickle.loads(helpers.decrypt(command[dict_key], self.sk))
            self.dicts.create(dict_id, command['client_ids'], dict_pk, dict_sk)

        elif cmd_type == helpers.CommandType.PUT:
            if dict_id not in self.dicts.dicts:
                print('Dictionary does not exist. Cannot apply put operation.')
                return
            if issuer_id not in self.dicts.dicts[dict_id].client_ids:
                print('Cannot apply put operation. Invalid issuer ID.')
                return
            if self.node_id not in self.dicts.dicts[dict_id].client_ids:
                print('Cannot apply put operation. Access denied.')
                return
            self.check_dict_sk(dict_id)
            dict_sk = self.dicts.dict_sk[dict_id]
            key = helpers.decrypt(command['encrypted_key'], dict_sk).decode()
            value = helpers.decrypt(command['encrypted_value'], dict_sk).decode()
            self.dicts.put(dict_id, key, value)

        elif cmd_type == helpers.CommandType.GET:
            if dict_id not in self.dicts.dicts:
                print('Dictionary does not exist. Cannot apply get operation.')
                return
            if issuer_id not in self.dicts.dicts[dict_id].client_ids:
                print('Cannot apply get operation. Invalid issuer ID.')
                return
            if self.node_id not in self.dicts.dicts[dict_id].client_ids:
                print('Cannot apply get operation. Access denied.')
                return
            self.check_dict_sk(dict_id)
            dict_sk = self.dicts.dict_sk[dict_id]
            key = helpers.decrypt(command['encrypted_key'], dict_sk).decode()
            self.dicts.get(dict_id, key)

        # print(f"Applying command: {command.type}")
        # if command.type == helpers.CommandType.CREATE:
        #     if str(self.node_id) in command.client_ids:
        #         self.dicts.create(command.client_ids, command.dict_id)
        # elif command.type == helpers.CommandType.PUT:
        #     if self.dicts.check_dict_id(command.dict_id):
        #         self.dicts.put(command.dict_id, command.key, command.value)
        # elif command.type == helpers.CommandType.GET:
        #     if self.dicts.check_dict_id(command.dict_id):
        #         self.dicts.get(command.dict_id, command.key)
        
    def check_timeout(self):
        now = time.time()
        if (self.state == RaftState.FOLLOWER or self.state == RaftState.CANDIDATE) and (self.election_timer is None):
            self.run_election_timer()
        
        elif self.state == RaftState.LEADER and now - self.last_heartbeat_timestamp > constants.HEARTBEAT:
            self.send_heartbeat()
        
    def send_append_entries(self, destination):
        prev_log_index = self.next_index[destination] - 1
        prev_log_term = self.log[prev_log_index]['term'] if prev_log_index >= 0 else 0
        if len(self.log) > prev_log_index:
            entries = self.log[prev_log_index+1:]
        else:
            entries = []
        
        message = {
            "type": "append_entries",
            "term": self.current_term,
            "leader_id": self.node_id,
            "prev_log_index": prev_log_index,
            "prev_log_term": prev_log_term,
            "entries": entries,
            "leader_commit": self.commit_index
        }
        self.send_rpc(destination, message)

    def forward_to_leader(self, log_entry):
        destination = self.leader_id

        message = {
            "type": "leader_add",
            "sender_id": self.node_id,
            "entry": log_entry
        }
        self.send_rpc(destination, message)


    def send_request_vote(self, destination):
        prev_log_index = self.next_index[destination] - 1
        prev_log_term = self.log[prev_log_index]['term'] if prev_log_index >= 0 else 0
        message = {
            'type': "request_vote",
            'candidateId': self.node_id,
            'term':  self.current_term,  
            'lastLogIndex': prev_log_index,
            'lastLogTerm': prev_log_term
        }
        
        self.send_rpc(destination, message)

    def send_vote_response(self, candidate_id, term, vote_granted):
        message = {
            'type': "vote_response",
            'sender_id': self.node_id,
            'term': term,
            'vote_granted': vote_granted
        }
        self.send_rpc(candidate_id, message)
    
    def send_append_response(self, receiver, success, current_term, match_index):
        message = {
            "type": "append_response",
            'sender_id': self.node_id,
            "success": success,
            "term": current_term,
            "match_index": match_index
        }
        self.send_rpc(receiver, message)

    def send_ack(self, destination):
        message = {
            'type': 'ack',
            'term': self.current_term,
            'candidate_id': self.node_id,
            'last_log_index': self.last_applied
        }
        self.send_rpc(destination, message)

    def send_fail(self, destination):
        message = {
            'type': 'fail',
            'node_id': self.node_id
        }
        self.send_rpc(destination, message)

    def send_rpc(self, node_id, data):
        sender = str(self.node_id)
        obj = helpers.to_string(data)
        if self.connected[node_id]:
            helpers.send_padded_msg_encoded(self.soc_send[node_id], sender, obj, self.pk[node_id])
            # try:
            #     helpers.send_padded_msg_encoded(self.soc_send[node_id], sender, obj, self.pk[node_id])
            # except:
            #     helpers.enter_error("Couldn't send message to {}".format(node_id))
            #     self.connected[node_id] = False
            #     self.soc_send[node_id] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
    def run_election_timer(self):
        self.stop_election_timer()
        random.seed(time.time())
        timeout = random.uniform(constants.TIMEOUT, 2*constants.TIMEOUT)
        self.election_timer = threading.Timer(timeout, self.start_leader_election)
        self.election_timer.start()
        
    def reset_election_timer(self):
        self.stop_election_timer()
        
        self.run_election_timer()
        
    def stop_election_timer(self):
        if self.election_timer is not None:
            self.election_timer.cancel()
            self.election_timer = None

    def handle_vote_request(self, obj):
        canditate_id, successs, term = self.request_vote(candidate_id=obj['candidateId'], candidate_term=obj['term'], last_log_index=obj['lastLogIndex'], last_log_term=obj['lastLogTerm'])
        self.send_vote_response(canditate_id,term, successs)

    def handle_append_entries(self, sender, obj):
        success, term, index = self.append_entries(obj['term'], obj['leader_id'], obj['prev_log_index'], obj['prev_log_term'], obj['entries'], obj['leader_commit'])
        self.send_append_response(sender, success, term, index)

    def handle_vote_response(self, obj):
        self.vote_response(obj['sender_id'], obj['term'], obj['vote_granted'])

    def handle_append_response(self, obj):
        self.append_response(obj['sender_id'], obj['term'], obj['success'], obj['match_index'])

    def handle_ack(self, obj):
        self.ack(obj['candidate_id'],obj['term'], obj['last_log_index'])

    def handle_leader_add(self, obj):
        self.leader_add(obj['entry'])

    def handle_command(self, command : helpers.Command):
        index = len(self.log)
        dict_pk, dict_sk, dict_id = None, None, (-1,-1)
        if command.type == helpers.CommandType.CREATE:
            dict_id = command.dict_id
            (dict_pk, dict_sk) = rsa.newkeys(constants.KEY_LENGTH) # create dictionary keys and store them
            self.dicts.dict_pk[dict_id] = dict_pk
            self.dicts.dict_sk[dict_id] = dict_sk
        else:
            dict_id = command.dict_id
            dict_pk = self.dicts.dict_pk[dict_id]
            # dict_sk = self.dicts.dict_sk[dict_id]


        # create log entry
        log_entry = {}
        if command.type in [helpers.CommandType.CREATE, helpers.CommandType.GET, helpers.CommandType.PUT]:
            log_entry = {'command': command.get_log_entry(self.pk, dict_pk, dict_sk), 'index' : index, 'term' : self.current_term}
        else:
            helpers.enter_error("handle_command() called with incorrect command type.")
            raise Exception()

        if self.state == RaftState.LEADER or self.state == RaftState.CANDIDATE:
            self.commit_maj.append(set())
            self.log.append(log_entry)
        elif self.state == RaftState.FOLLOWER:
            self.forward_to_leader(log_entry)

    def handle_send_fail(self,obj):
        node_id = obj['node_id']
        self.soc_send[node_id] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected[node_id] = False

    def save_state(self):
        filename = "log_" + str(self.node_id) + ".pickle"
        helpers.commit(self,filename)

    def fix_link(self, node_id, firstConnection=False):
        if node_id != self.node_id and self.connected[node_id] == False:
            self.connected[node_id] = True
            self.soc_send[node_id].connect((constants.HOST, constants.CLIENT_PORT_PREFIX+node_id))
            if firstConnection:
                helpers.send_padded_msg(self.soc_send[node_id],"Connection (First) request from {}\nPublic Key = {}".format(self.node_id, str_format(self.pk[self.node_id])))
                received = self.soc_send[node_id].recv(constants.MESSAGE_SIZE)
                print(received)
            else:
                helpers.send_padded_msg(self.soc_send[node_id],"Connection request from {}".format(self.node_id))
                received = self.soc_send[node_id].recv(constants.MESSAGE_SIZE)
                print(received)

    def fail_link(self, node_id):
        self.send_fail(node_id)
        self.soc_send[node_id] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected[node_id] = False
        print("Deleted link between self and {}".format(node_id))

    def fail(self):
        for peer in self.peers:
            if peer != self.node_id:
                self.fail_link(peer)
        self.save_state()

def str_format(pk):
    return '{} {}'.format(pk.n, pk.e)