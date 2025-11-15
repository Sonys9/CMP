import cmp
import asyncio
import base64
from opcodes import OPCODES
import json
import sys

async def main():
    server = cmp.Server('127.0.0.1', 16760)
    client = cmp.Client('127.0.0.1', 16760)
    try:
        await server.start()
        await asyncio.sleep(0.05)
        await client.connect()

        available = await client.is_address_available('admin', 1)
        print('is "admin" available:', available)

        result = await client.register_address('admin', 'admin', 1)
        print('register admin:', result)

        result = await client.register_address('admin2', 'admin2', 1)
        print('register admin2:', result)

        with open('image.png', 'rb') as f:
            image_content = f.read()

        result = await client.send_mail('admin', 'admin', 'admin2', 'Hey!', files=[{'file_id': 'image.png'}])
        print('send mail result:', result)

        mails_admin2 = await client.get_mails('admin2', 'admin2', 1)
        print('admin2 mails raw:', mails_admin2)
        try:
            print('admin2 mails parsed:', json.dumps(mails_admin2, indent=2))
        except Exception:
            pass

        mails_admin = await client.get_mails('admin', 'admin', 1)
        print('admin mails raw:', mails_admin)
        try:
            print('admin mails parsed:', json.dumps(mails_admin, indent=2))
        except Exception:
            pass

        await client.close()
    except Exception as e:
        print('Error during test run:', e, file=sys.stderr)
        try:
            await client.close()
        except Exception:
            pass
    finally:
        try:
            srv = getattr(server, 'server', None)
            if srv:
                srv.close()
                await srv.wait_closed()
        except Exception:
            pass

if __name__ == '__main__':
    asyncio.run(main())
