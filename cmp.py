import asyncio
import errors
import time
import random
import string
from opcodes import OPCODES

class Server:
    def __init__(self, host: str = '127.0.0.1', port: int = 16760, maximum_address_length: int = 24, allowed_address_characters: str = 'qwertyuiopasdfghjklzxcvbnm123456789') -> None:
        """
            Sets server settings.
            Arguments:
                - host: The host to bind (str, default: 127.0.0.1)
                - port: The port to bind (int, default: 16760)
        """
        self.host = host
        self.port = port
        self.addresses = {}
        self.maximum_address_length = maximum_address_length
        self.allowed_address_characters = allowed_address_characters
        
    async def start(self) -> None:
        """
            Binds the server.
        """
        self.server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """
            Handles connections.
            Arguments:
                - reader: asyncio.StreamReader
                - writer: asyncio.StreamWriter
        """
        client_address = writer.get_extra_info('peername')

        while True:
            data = await reader.read(1024)
            #print(f'Data: {data}')

            opcode, message = data[:1], data[1:]
            if opcode == OPCODES['CLIENT_DISCONNECT']: 
                writer.write(OPCODES['CONNECTION_CLOSED'])
                writer.close()
                await writer.wait_closed()
                return

            if opcode not in OPCODES.values():
                writer.write(OPCODES['UNKNOWN_OPCODE'])
                continue
            
            if opcode == OPCODES['CLIENT_INITIALIZE'] or opcode == OPCODES['PING']:
                writer.write(OPCODES['CONNECTION_INITIALIZED'])
                continue

            if opcode == OPCODES['IS_AVAILABLE']:
                available = await self.is_available(message.decode())
                writer.write(OPCODES['IS_AVAILABLE'] + b't' if available else b'f')
                continue

            if opcode == OPCODES['REGISTER']:
                string = message.decode()
                if string.count('@') != 1:
                    writer.write(OPCODES['REGISTER'] + b'f')
                    continue

                address, password = string.split('@')
                result = await self.register_address(address, password)
                writer.write(OPCODES['REGISTER'] + b't' if result else b'f')
                continue

    async def is_available(self, address: str) -> bool:
        """
            Checks if address is available
            Arguments:
                - address: Address (str)
            Returns: bool
        """
        if address.lower() in self.addresses.keys() or len(address) > self.maximum_address_length:
            return False

        for k in address:
            if k not in self.allowed_address_characters:
                return False
                
        return True

    async def register_address(self, address: str, password: str) -> bool | str:
        """
            Registers the address.
            Arguments:
                - address: Address (str, for example: someemail)
                - password: Password (str, for example: verysecurepassword)
            Returns: bool
        """
        available = await self.is_available(address)
        if not available:
            return False

        self.addresses[address] = {
            'password': password,
            'mails': [],
            'register_date': time.time(),
            'admin': False
        }
        return True

class Client:
    def __init__(self, host: str, port: int) -> None:
        """
            Sets connection settings.
            Arguments:
                - host: The host to connect (str, for example: 127.0.0.1)
                - port: The port to connect (int, for example: 16760)
        """
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
    
    async def connect(self, timeout: float = 5) -> None:
        """
            Connects to the server.
            Arguments:
                - timeout: Timeout (float, default: 5)
        """
        reader, writer = await asyncio.wait_for(asyncio.open_connection(
            self.host, self.port
        ), timeout=timeout)
        writer.write(OPCODES['CLIENT_INITIALIZE'])
        await writer.drain()

        result = await reader.read(1)
        if result != OPCODES['CONNECTION_INITIALIZED']:
            raise errors.InitializingError(f"Client was not initialized, got {result} instead of {OPCODES['CONNECTION_INITIALIZED']}.")

        self.reader = reader
        self.writer = writer

    async def close(self) -> None:
        """
            Closes the connection.
        """
        if not self.writer:
            return
            
        self.writer.write(OPCODES['CLIENT_DISCONNECT'])
        await self.writer.drain()

        self.writer.close()
        await self.writer.wait_closed()

    async def send_raw_message(self, message: bytes, timeout: float = 5) -> None:
        """
            Sends the raw message without any response
            Arguments:
                - message: Message (bytes, for example: b'0x03')
                - timeout: Timeout (float, default: 5)
        """
        if not self.writer:
            raise errors.InitializingError('Client was not initialized.')

        self.writer.write(message)
        await asyncio.wait_for(self.writer.drain(), timeout=timeout)
        #print(f'Sent {message} to the server')

    async def wait_for_raw_message(self, bytes_: int = 1024, timeout: float = 5) -> bytes:
        """
            Waits for the raw message.
            Arguments:
                - bytes_: Maximum number of bytes to get (int, default: 1024)
                - timeout: Timeout in seconds (float, default: 5)

            Returns: bytes (b'' if got nothing)
        """
        if not self.reader:
            raise errors.InitializingError('Client was not initialized.')
    
        start_time = time.time()
        while True:
            result = await asyncio.wait_for(self.reader.read(bytes_), timeout=timeout)
            if result:
                break
            if time.time() - start_time > timeout:
                return b''
            
        return result

    async def is_address_available(self, address: str, timeout: float = 5) -> bool:
        """
            Checks if address is available
            Arguments:
                - address: Address (str)
                - timeout: Timeout (float)
            Returns: bool
        """
        await self.send_raw_message(OPCODES['IS_AVAILABLE'] + address.encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        opcode, message = result[:1], result[1:]
        return message == b't'

    async def register_address(self, address: str, password: str, timeout: float = 5) -> bool:
        """
            Checks if address is available
            Arguments:
                - address: Address (str)
                - timeout: Timeout (float)
                - password: Password (str, for example: verysecurepassword)
            Returns: bool
        """
        await self.send_raw_message(OPCODES['REGISTER'] + address.encode() + '@'.encode() + password.encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        opcode, message = result[:1], result[1:]
        return message == b't'