import threading
import random

import constants

roles = ['leader', 'candidate', 'follower']

def generate_timeout_duration():
    return random.uniform(constants.TIMEOUT, 2 * constants.TIMEOUT)

# exceptions
def incorrect_role_exception():
    raise Exception('Error: Invalid role in Raft. Valid roles are [leader, candidate, follower]')

class Role:
    def __init__(self, role):
        if (role not in roles):
            incorrect_role_exception()
        self.name = role

class RaftLog:
    def __init__(self, contents=[]):
        self.contents = contents
    # implement this

class RaftServer:
    leader = Role('leader')
    candidate = Role('candidate')
    follower = Role('follower')


    def __init__(self, role='follower'):
        # Set the correct role
        if role == 'leader':
            self.become_leader()
        elif role == 'candidate':
            self.become_candidate()
        elif role == 'follower':
            self.become_follower()
        else:
            incorrect_role_exception()

        self.current_term = 0
        self.voted_for = None
        self.log = RaftLog()
        self.commit_index = 0
        self.last_applied = 0
        self.run = True

        # timeout threads
        timeoutDuration = generate_timeout_duration()
        self.electionTimeout = threading.Timer(timeoutDuration, self.timeout) # need to cancel and recreate this object when we reset the timer

    # timeouts
    
    def timeout():
        pass # implement election timeout
    def reset_timeout(self):
        self.electionTimeout.cancel()
        timeoutDuration = generate_timeout_duration()
        self.electionTimeout = threading.Timer(timeoutDuration, self.timeout)

    # role changes
    def become_leader(self):
        self.role = self.leader
    def become_candidate(self):
        self.role = self.candidate
    def become_follower(self):
        self.role = self.follower

    # UI
    def print_role(self):
        print(self.role.name)
        