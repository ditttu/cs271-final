CLIENT_PORT_PREFIX = 6540
HOST = "localhost"
NUM_CLIENT = 5
CONNECTION_GRAPH = [[1, 2, 3, 4], [0, 2, 3, 4], [0, 1, 3, 4], [0, 1, 2, 4], [0, 1, 2, 3]]
MESSAGE_DELAY = 3   # seconds of delay when receiving a message
MESSAGE_SIZE = 2048 # message size in bytes
HEADER_SIZE = 5
TIMEOUT = 7 # election timeout period in seconds