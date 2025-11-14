import asyncio
import errors
import time
import random
import string
import json
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
        self.pool = {}
        
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
                try:
                    parsed = json.loads(string)
                    address, password = parsed['address'], parsed['password']
                    result = await self.register_address(address, password)
                    writer.write(OPCODES['REGISTER'] + b't' if result else b'f')
                except:
                    writer.write(OPCODES['REGISTER'] + b'f')
                continue

            if opcode == OPCODES['SEND_MAIL']:
                string = message.decode()
                try:
                    parsed = json.loads(string)
                    address, password, to_address, text, files = parsed['address'], parsed['password'], parsed['to_address'], parsed['text'], parsed['files']
                    result = await self.send_mail(address, password, to_address, text, files)
                    writer.write(OPCODES['SEND_MAIL'] + b't' if result else b'f')
                except Exception as e:
                    print(e)
                    writer.write(OPCODES['SEND_MAIL'] + b'f')
                continue
            
            if opcode == OPCODES['GET_MAILS']:
                string = message.decode()
                try:
                    parsed = json.loads(string)
                    address, password = parsed['address'], parsed['password']
                    result = await self.get_mails(address, password)
                    writer.write(OPCODES['SEND_MAIL'] + result.encode() if result else b'f')
                except:
                    writer.write(OPCODES['GET_MAILS'] + b'f')
                continue

            if opcode == OPCODES['UPLOAD_FILE']:
                ...
                #ill do it tomorrow im tired
                
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

    async def register_address(self, address: str, password: str) -> bool:
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

        self.addresses[address.lower()] = {
            'password': password,
            'mails': [],
            'register_date': time.time(),
            'admin': False
        }
        return True

    async def check_credentials(self, address: str, password: str) -> bool:
        """
            Checks the credentials
            Arguments:
                - address: Address (str, for example: someemail)
                - password: Password (str, for example: verysecurepassword)
            Returns: bool
        """
        if not address in self.addresses.keys():
            return False
        if self.addresses[address]['password'] != password:
            return False
        return True

    async def send_mail(self, address: str, password: str, to_address: str, text: str, files: list[dict]) -> bool:
        """
            Sends the mail
            Arguments:
                - address: Address (str, for example: someemail)
                - password: Password (str, for example: verysecurepassword)
                - to_address: Address to send (str, for example: friendemail)
                - text: Text to send (str, for example: Hey!)
                - files: Files to send (list[dict], for example: [{"file_id": some_id}, ...] or [] if no files)
            Returns: bool
        """
        is_valid = await self.check_credentials(address.lower(), password)
        if not is_valid:
            return False
        
        if to_address not in self.addresses.keys():
            return False

        if len(files) > 15:
            return False

        for file in files:
            if not file:
                continue
            if 'file_id' not in file.keys() or len(file.keys()) > 1:
                return False

        self.addresses[to_address.lower()]['mails'].append({
            'out': False,
            'to_address': None,
            'from_address': address,
            'text': text,
            'files': files,
            'sent_at': time.time()
        })
        self.addresses[address.lower()]['mails'].append({
            'out': True,
            'to_address': to_address,
            'from_address': None,
            'text': text,
            'files': files,
            'sent_at': time.time()
        })
        return True

    async def get_mails(self, address: str, password: str) -> list[dict] | bool:
        """
            Gets the mails
            Arguments:
                - address: Address (str, for example: someemail)
                - password: Password (str, for example: verysecurepassword)
            Returns: list[dict] | bool (on error)
        """
        is_valid = await self.check_credentials(address.lower(), password)
        if not is_valid:
            return False
        
        return json.dumps(self.addresses[address.lower()]['mails'])

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
        await self.send_raw_message(OPCODES['REGISTER'] + json.dumps({'address': address, 'password': password}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        opcode, message = result[:1], result[1:]
        return message == b't'

    async def send_mail(self, address: str, password: str, to_address: str, text: str, files: list[dict] = [], timeout: float = 5) -> bool:
        """
            Sends the mail
            Arguments:
                - address: Address (str, for example: someemail)
                - password: Password (str, for example: verysecurepassword)
                - to_address: Address to send (str, for example: friendemail)
                - text: Text to send (str, for example: Hey!)
                - files: Files to send (list[dict], for example: [{"file_id": some_id}, ...] or [] if no files)
            Returns: bool
        """
        await self.send_raw_message(OPCODES['SEND_MAIL'] + json.dumps({'address': address, 'password': password, 'to_address': to_address, 'text': text, 'files': files}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        opcode, message = result[:1], result[1:]
        return message == b't'

    async def get_mails(self, address: str, password: str, timeout: float = 5) -> list[dict] | bool: # list or None because on older py versions list[dict] | None gives error
        """
            Gets the mails
            Arguments:
                - address: Address (str, for example: someemail)
                - password: Password (str, for example: verysecurepassword)
            Returns: list[dict] | bool (on error)
        """
        await self.send_raw_message(OPCODES['GET_MAILS'] + json.dumps({'address': address, 'password': password}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        opcode, message = result[:1], result[1:]
        return json.loads(message.decode()) if message != b'f' else None