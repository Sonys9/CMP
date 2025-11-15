import asyncio
import errors
import time
import random
import string
import json
from opcodes import OPCODES
from strings import STRINGS

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
            try:
                data = await reader.read(1024)
                if not data:
                    continue
                parsed = json.loads(data.decode())
                opcode = parsed['opcode']

                if opcode not in OPCODES.values():
                    writer.write(json.dumps({'opcode': OPCODES['UNKNOWN_OPCODE']}).encode())
                    continue

                if opcode == OPCODES['CLIENT_DISCONNECT']:
                    writer.write(json.dumps({'opcode': OPCODES['CONNECTION_CLOSED']}).encode())
                    writer.close()
                    await writer.wait_closed()
                    return
                
                if opcode == OPCODES['CLIENT_INITIALIZE'] or opcode == OPCODES['PING']:
                    writer.write(json.dumps({'opcode': OPCODES['CONNECTION_INITIALIZED']}).encode())
                    continue

                if opcode == OPCODES['IS_AVAILABLE']:
                    available = await self.is_available(parsed['address'])
                    writer.write(json.dumps({'opcode': OPCODES['IS_AVAILABLE'], 'result': available}).encode())
                    continue

                if opcode == OPCODES['REGISTER']:
                    result = await self.register_address(parsed['address'], parsed['password'])
                    writer.write(json.dumps({'opcode': OPCODES['REGISTER'], 'result': result}).encode())
                    continue

                if opcode == OPCODES['SEND_MAIL']:
                    result = await self.send_mail(parsed['address'], parsed['password'], parsed['to_address'], parsed['text'], parsed.get('files', []))
                    writer.write(json.dumps({'opcode': OPCODES['SEND_MAIL'], 'result': result}).encode())
                    continue
                
                if opcode == OPCODES['GET_MAILS']:
                    result = await self.get_mails(parsed['address'], parsed['password'])
                    if result:
                        writer.write(json.dumps({'opcode': OPCODES['GET_MAILS'], 'result': True, 'data': result}).encode())
                        continue
                    writer.write(json.dumps({'opcode': OPCODES['GET_MAILS'], 'result': False}).encode())
                    continue

                if opcode == OPCODES['UPLOAD_FILE']:
                    ...
            except Exception:
                try:
                    writer.write(json.dumps({'opcode': OPCODES['PARSE_ERROR']}).encode())
                except:
                    pass
                continue

    async def is_available(self, address: str) -> bool:
        """
            Checks if address is available
            Arguments:
                - address: Address (str)
            Returns: bool
        """
        if address.lower() in self.addresses.keys():
            return {'result': False, 'message': STRINGS['ADDRESS_NOT_AVAILABLE']}
        if len(address) > self.maximum_address_length:
            return {'result': False, 'message': STRINGS['ADDRESS_TOO_LONG']}
        if len(address) < 3:
            return {'result': False, 'message': STRINGS['ADDRESS_TOO_SHORT']}

        for k in address:
            if k not in self.allowed_address_characters:
                return {'result': False, 'message': STRINGS['ADDRESS_IS_BAD']}
                
        return {'result': True, 'message': STRINGS['ADDRESS_AVAILABLE']}

    async def register_address(self, address: str, password: str) -> bool:
        """
            Registers the address.
            Arguments:
                - address: Address (str, for example: someemail)
                - password: Password (str, for example: verysecurepassword)
            Returns: bool
        """
        available = await self.is_available(address)
        if not available['result']:
            return available

        self.addresses[address.lower()] = {
            'password': password,
            'mails': [],
            'register_date': time.time(),
            'admin': False
        }
        return {'result': True, 'message': STRINGS['REGISTER_SUCCESSFUL']}

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
            return {'result': False, 'message': STRINGS['INVALID_CREDENTIALS']}
        
        if to_address not in self.addresses.keys():
            return {'result': False, 'message': STRINGS['ADDRESS_NOT_FOUND']}

        if len(files) > 15:
            return {'result': False, 'message': STRINGS['FILES_LIMIT']}

        for file in files:
            if not file:
                continue
            if 'file_id' not in file.keys() or len(file.keys()) > 1:
                return {'result': False, 'message': STRINGS['INVALID_FILE']}

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
        return {'result': True, 'message': STRINGS['MAIL_SENT']}

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
            return {'result': False, 'message': STRINGS['INVALID_CREDENTIALS']}
        
        return json.dumps({'result': True, 'data': self.addresses[address.lower()]['mails']})

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
        writer.write(json.dumps({'opcode': OPCODES['CLIENT_INITIALIZE']}).encode())
        await writer.drain()

        result = await reader.read(16)
        try:
            parsed = json.loads(result.decode())
            opcode = parsed['opcode']
        except:
            raise errors.InitializingError(f"Got bad response from the server: {result}")
        if opcode != OPCODES['CONNECTION_INITIALIZED']:
            raise errors.InitializingError(f"Client was not initialized, got {opcode} instead of {OPCODES['CONNECTION_INITIALIZED']}.")

        self.reader = reader
        self.writer = writer

    async def close(self) -> None:
        """
            Closes the connection.
        """
        if not self.writer:
            return
            
        await self.send_raw_message(json.dumps({'opcode': OPCODES['CLIENT_DISCONNECT']}).encode())
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
        await self.send_raw_message(json.dumps({'opcode': OPCODES['IS_AVAILABLE'], 'address': address}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        try:
            parsed = json.loads(result.decode())
            available = parsed['result']
        except:
            return False
        return available

    async def register_address(self, address: str, password: str, timeout: float = 5) -> bool:
        """
            Checks if address is available
            Arguments:
                - address: Address (str)
                - timeout: Timeout (float)
                - password: Password (str, for example: verysecurepassword)
            Returns: bool
        """
        await self.send_raw_message(json.dumps({'opcode': OPCODES['REGISTER'], 'address': address, 'password': password}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        try:
            parsed = json.loads(result.decode())
            result = parsed['result']
        except:
            return False
        return result

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
        await self.send_raw_message(json.dumps({'opcode': OPCODES['SEND_MAIL'], 'address': address, 'password': password, 'to_address': to_address, 'text': text, 'files': files}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        try:
            parsed = json.loads(result.decode())
            result = parsed['result']
        except:
            return False
        return result

    async def get_mails(self, address: str, password: str, timeout: float = 5) -> list[dict] | bool:
        """
            Gets the mails
            Arguments:
                - address: Address (str, for example: someemail)
                - password: Password (str, for example: verysecurepassword)
            Returns: list[dict] | bool (on error)
        """
        await self.send_raw_message(json.dumps({'opcode': OPCODES['GET_MAILS'], 'address': address, 'password': password}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        try:
            parsed = json.loads(result.decode())
            result = parsed['result']
            if not result:
                raise
            mails = parsed['data']
        except:
            return False
        return mails
