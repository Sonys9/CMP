OPCODES = {
    'CLIENT_INITIALIZE': bytes([0x00]),
    'CONNECTION_INITIALIZED': bytes([0x01]),
    'CONNECTION_CLOSED': bytes([0x02]),
    'CONNECTION_ERROR': bytes([0x03]),
    'CLIENT_DISCONNECT': bytes([0x04]),
    'PING': bytes([0x05]),  # for tests
    'IS_AVAILABLE': bytes([0x06]),
    'REGISTER': bytes([0x07]),

    'UNKNOWN_OPCODE': bytes([0xFF])
}
