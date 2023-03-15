import time
import threading
import constants
import dictionary
import helpers
# import socket
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
        
        # initialize persistent state
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.dicts = dictionary.Dictionaries(self.node_id)

        # initialize volatile state
        self.commit_index = 0
        self.last_applied = 0
        
        # initialize leader state
        self.next_index = {peer: 0 for peer in self.peers}
        self.match_index = {peer: 0 for peer in self.peers}
        self.leader_id = None
        
        # start election timer
        self.run_election_timer()
        self.votes_received = set()

        # sockets
        self.soc_send = soc_list.copy()

        # initialize solid disc files
        self.disc = helpers.DiscLog(self.node_id)

    def instantiate_sockets(self):
        for node_id in self.peers:
            if node_id != self.node_id:
                self.soc_send[node_id].connect((constants.HOST, constants.CLIENT_PORT_PREFIX+node_id))
                helpers.send_padded_msg(self.soc_send[node_id],"Connection request from {}".format(self.node_id))
                received = self.soc_send[node_id].recv(constants.MESSAGE_SIZE)
                print(received)

    def become_leader(self):
        if self.state != RaftState.CANDIDATE:
            return
        
        self.state = RaftState.LEADER
        self.leader_id = self.node_id
        self.votes_received = set()
        
        self.next_index = {peer: len(self.log) for peer in self.peers}
        self.match_index = {peer: 0 for peer in self.peers}
        
        self.send_heartbeat()

    def become_follower(self):
        self.state = RaftState.FOLLOWER
        self.votes_received = set()
        
    # receive rpc
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
        return candidate_id, True, candidate_term
        
    def append_entries(self, leader_term, leader_id, prev_log_index, prev_log_term, entries, leader_commit):
        if leader_term < self.current_term:
            return False, self.current_term
        
        if leader_term > self.current_term:
            self.current_term = leader_term
            self.leader_id = leader_id
            self.voted_for = None
            self.become_follower()

        self.reset_election_timer()
        
        if prev_log_index >= len(self.log) or self.log[prev_log_index]['term'] != prev_log_term:
            return False, self.current_term, prev_log_index

        index = prev_log_index + 1
        for entry in entries:
            if index < len(self.log) and self.log[index]['term'] != entry['term']:
                del self.log[index:]
            if index >= len(self.log):
                self.log.append(entry)
            index += 1
        
        if leader_commit > self.commit_index:
            #TODO:Commit entries
            self.commit_index = min(leader_commit, len(self.log) - 1)
        
        return True, leader_term, index
        
    def send_heartbeat(self):
        for node_id in self.peers:
            if node_id == self.node_id:
                continue
            self.send_append_entries(node_id)
        
    def start_leader_election(self):
        self.current_term += 1
        self.voted_for = self.node_id
        self.state = RaftState.CANDIDATE
        
        self.reset_election_timer()
        
        self.votes_received = set()
        self.votes_received.add(self.node_id)
        for node_id in self.peers:
            if node_id == self.node_id:
                continue
            self.send_request_vote(node_id)
        
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
                #TODO: check majority
                self.commit_index = match_index
        
        else:
            self.next_index[follower_id] -= 1
            #TODO:retry?
        
    def apply_log_entries(self):
        for i in range(self.last_applied + 1, self.commit_index + 1):
            cmd = self.log[i]['command']
            self.last_applied = i
            
            if self.node_id not in cmd:
                continue

            self.apply_log_entry(cmd)
            
            
            if self.leader_id == self.node_id:
                for node_id in self.peers:
                    if node_id == self.node_id:
                        continue
                    self.send_ack(node_id)

    def apply_log_entry(self, command : helpers.Command):
        if self.node_id not in command.client_ids:
            helpers.enter_error('Cannot apply entry for dictionary the client is not a part of.')
            return
        print(f"Applying command: {command}")
        if command.type == helpers.CommandType.CREATE:
            self.dicts.create(command.client_ids)
        elif command.type == helpers.CommandType.PUT:
            self.dicts.put(command.dict_id, command.key, command.value)
        elif command.type == helpers.CommandType.GET:
            self.dicts.get(command.dict_id, command.key)

    def run(self):
        #TODO: implement
        return
    
    # commit log entry at current index
    def commit(self):
        self.disc.commit(self.log[self.commit_index])
        self.commit_index += 1
        
    def check_timeout(self):
        now = time.time()
        
        if self.state == RaftState.CANDIDATE and now - self.last_election_timestamp > self.election_timeout:
            self.start_leader_election()
        
        elif (self.state == RaftState.FOLLOWER or self.state == RaftState.LEADER) and now - self.last_heartbeat_timestamp > self.heartbeat_timeout:
            self.send_heartbeat()
        
    def send_append_entries(self, destination):
        prev_log_index = self.next_index[destination] - 1
        prev_log_term = self.log[prev_log_index]['term'] if prev_log_index >= 0 else 0
        
        entries = self.log[self.match_index[destination]:self.next_index[destination]]
        
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

    def send_rpc(self, node_id, data):
        sender = str(self.node_id)
        obj = helpers.to_string(data)
        helpers.send_padded_msg_encoded(self.soc_send[node_id], sender, obj)
        
    def run_election_timer(self):
        self.stop_election_timer()
        self.election_timer = threading.Timer(constants.TIMEOUT, self.start_leader_election)
        self.election_timer.start()
        
    def reset_election_timer(self):
        self.stop_election_timer()
        
        self.run_election_timer()
        
    def stop_election_timer(self):
        if self.election_timer is not None:
            self.election_timer.cancel()
            self.election_timer = None

