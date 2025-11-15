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
        self.host = host
        self.port = port
        self.addresses = {}
        self.maximum_address_length = maximum_address_length
        self.allowed_address_characters = allowed_address_characters
        self.pool = {}
        
    async def start(self) -> None:
        self.server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client_address = writer.get_extra_info('peername')

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                try:
                    parsed = json.loads(data.decode())
                    opcode = parsed.get('opcode')
                except Exception:
                    writer.write(json.dumps({'opcode': OPCODES['PARSE_ERROR']}).encode())
                    await writer.drain()
                    continue

                if opcode not in OPCODES.values():
                    writer.write(json.dumps({'opcode': OPCODES['UNKNOWN_OPCODE']}).encode())
                    await writer.drain()
                    continue

                if opcode == OPCODES['CLIENT_DISCONNECT']:
                    writer.write(json.dumps({'opcode': OPCODES['CONNECTION_CLOSED']}).encode())
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return
                
                if opcode == OPCODES['CLIENT_INITIALIZE'] or opcode == OPCODES['PING']:
                    writer.write(json.dumps({'opcode': OPCODES['CONNECTION_INITIALIZED']}).encode())
                    await writer.drain()
                    continue

                if opcode == OPCODES['IS_AVAILABLE']:
                    address = parsed.get('address')
                    if address is None:
                        writer.write(json.dumps({'opcode': OPCODES['PARSE_ERROR']}).encode())
                        await writer.drain()
                        continue
                    available = await self.is_available(address)
                    writer.write(json.dumps({'opcode': OPCODES['IS_AVAILABLE'], 'result': available}).encode())
                    await writer.drain()
                    continue

                if opcode == OPCODES['REGISTER']:
                    address = parsed.get('address')
                    password = parsed.get('password')
                    if address is None or password is None:
                        writer.write(json.dumps({'opcode': OPCODES['PARSE_ERROR']}).encode())
                        await writer.drain()
                        continue
                    result = await self.register_address(address, password)
                    writer.write(json.dumps({'opcode': OPCODES['REGISTER'], 'result': result}).encode())
                    await writer.drain()
                    continue

                if opcode == OPCODES['SEND_MAIL']:
                    address = parsed.get('address')
                    password = parsed.get('password')
                    to_address = parsed.get('to_address')
                    text = parsed.get('text')
                    files = parsed.get('files', [])
                    if None in (address, password, to_address, text) or not isinstance(files, list):
                        writer.write(json.dumps({'opcode': OPCODES['PARSE_ERROR']}).encode())
                        await writer.drain()
                        continue
                    result = await self.send_mail(address, password, to_address, text, files)
                    writer.write(json.dumps({'opcode': OPCODES['SEND_MAIL'], 'result': result}).encode())
                    await writer.drain()
                    continue
                
                if opcode == OPCODES['GET_MAILS']:
                    address = parsed.get('address')
                    password = parsed.get('password')
                    if address is None or password is None:
                        writer.write(json.dumps({'opcode': OPCODES['PARSE_ERROR']}).encode())
                        await writer.drain()
                        continue
                    result = await self.get_mails(address, password)
                    if result:
                        writer.write(json.dumps({'opcode': OPCODES['GET_MAILS'], 'result': True, 'data': result}).encode())
                        await writer.drain()
                        continue
                    writer.write(json.dumps({'opcode': OPCODES['GET_MAILS'], 'result': False}).encode())
                    await writer.drain()
                    continue

                if opcode == OPCODES['UPLOAD_FILE']:
                    writer.write(json.dumps({'opcode': OPCODES['UPLOAD_FILE'], 'result': False, 'message': STRINGS.get('NOT_IMPLEMENTED', 'Not implemented')}).encode())
                    await writer.drain()
                    continue
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def is_available(self, address: str) -> bool:
        if not isinstance(address, str):
            return {'result': False, 'message': STRINGS['ADDRESS_IS_BAD']}
        al = address.lower()
        if al in self.addresses.keys():
            return {'result': False, 'message': STRINGS['ADDRESS_NOT_AVAILABLE']}
        if len(al) > self.maximum_address_length:
            return {'result': False, 'message': STRINGS['ADDRESS_TOO_LONG']}
        if len(al) < 3:
            return {'result': False, 'message': STRINGS['ADDRESS_TOO_SHORT']}

        for k in al:
            if k not in self.allowed_address_characters:
                return {'result': False, 'message': STRINGS['ADDRESS_IS_BAD']}
                
        return {'result': True, 'message': STRINGS['ADDRESS_AVAILABLE']}

    async def register_address(self, address: str, password: str) -> bool:
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
        if not isinstance(address, str):
            return False
        addr = address.lower()
        if addr not in self.addresses.keys():
            return False
        if self.addresses[addr]['password'] != password:
            return False
        return True

    async def send_mail(self, address: str, password: str, to_address: str, text: str, files: list[dict]) -> bool:
        is_valid = await self.check_credentials(address.lower(), password)
        if not is_valid:
            return {'result': False, 'message': STRINGS['INVALID_CREDENTIALS']}
        
        if to_address.lower() not in self.addresses.keys():
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
        is_valid = await self.check_credentials(address.lower(), password)
        if not is_valid:
            return {'result': False, 'message': STRINGS['INVALID_CREDENTIALS']}
        
        return self.addresses[address.lower()]['mails']

class Client:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
    
    async def connect(self, timeout: float = 5) -> None:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(
            self.host, self.port
        ), timeout=timeout)
        writer.write(json.dumps({'opcode': OPCODES['CLIENT_INITIALIZE']}).encode())
        await writer.drain()

        result = await reader.read(16)
        try:
            parsed = json.loads(result.decode())
            opcode = parsed['opcode']
        except Exception:
            raise errors.InitializingError(f"Got bad response from the server: {result}")
        if opcode != OPCODES['CONNECTION_INITIALIZED']:
            raise errors.InitializingError(f"Client was not initialized, got {opcode} instead of {OPCODES['CONNECTION_INITIALIZED']}.")

        self.reader = reader
        self.writer = writer

    async def close(self) -> None:
        if not self.writer:
            return
            
        await self.send_raw_message(json.dumps({'opcode': OPCODES['CLIENT_DISCONNECT']}).encode())
        self.writer.close()
        await self.writer.wait_closed()

    async def send_raw_message(self, message: bytes, timeout: float = 5) -> None:
        if not self.writer:
            raise errors.InitializingError('Client was not initialized.')

        self.writer.write(message)
        await asyncio.wait_for(self.writer.drain(), timeout=timeout)

    async def wait_for_raw_message(self, bytes_: int = 1024, timeout: float = 5) -> bytes:
        if not self.reader:
            raise errors.InitializingError('Client was not initialized.')
        try:
            result = await asyncio.wait_for(self.reader.read(bytes_), timeout=timeout)
        except asyncio.TimeoutError:
            return b''
        return result

    async def is_address_available(self, address: str, timeout: float = 5) -> bool:
        await self.send_raw_message(json.dumps({'opcode': OPCODES['IS_AVAILABLE'], 'address': address}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        try:
            parsed = json.loads(result.decode())
            available = parsed['result']
        except Exception:
            return False
        return available

    async def register_address(self, address: str, password: str, timeout: float = 5) -> bool:
        await self.send_raw_message(json.dumps({'opcode': OPCODES['REGISTER'], 'address': address, 'password': password}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        try:
            parsed = json.loads(result.decode())
            result = parsed['result']
        except Exception:
            return False
        return result

    async def send_mail(self, address: str, password: str, to_address: str, text: str, files: list[dict] | None = None, timeout: float = 5) -> bool:
        files = files or []
        await self.send_raw_message(json.dumps({'opcode': OPCODES['SEND_MAIL'], 'address': address, 'password': password, 'to_address': to_address, 'text': text, 'files': files}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        try:
            parsed = json.loads(result.decode())
            result = parsed['result']
        except Exception:
            return False
        return result

    async def get_mails(self, address: str, password: str, timeout: float = 5) -> list[dict] | bool:
        await self.send_raw_message(json.dumps({'opcode': OPCODES['GET_MAILS'], 'address': address, 'password': password}).encode(), timeout=timeout)
        result = await self.wait_for_raw_message(1024, timeout=timeout)
        try:
            parsed = json.loads(result.decode())
            result = parsed['result']
            if not result:
                raise Exception()
            mails = parsed['data']
        except Exception:
            return False
        return mails
