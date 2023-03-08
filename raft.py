import constants

roles = ['leader', 'candidate', 'follower']

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


    def __init__(self, role):
        # Set the correct role
        if role == 'leader':
            self.role = self.leader
        elif role == 'candidate':
            self.role = self.candidate
        elif role == 'follower':
            self.role = self.follower
        else:
            incorrect_role_exception()

        self.current_term = 0
        self.voted_for = None
        self.log = RaftLog()
        self.commit_index = 0
        self.last_applied = 0
        self.run = True
        