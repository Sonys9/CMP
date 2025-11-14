import cmp
import asyncio
from opcodes import OPCODES

async def main():
    server = cmp.Server('127.0.0.1', 16760)
    client = cmp.Client('127.0.0.1', 16760)
    await server.start()
    await client.connect()

    available = await client.is_address_available('admin', 1)
    print(available)

    result = await client.register_address('admin', 'admin', 1)
    print(result)

    result = await client.register_address('admin', 'admin', 1)
    print(result)

    result = await client.register_address('admin', 'admin2', 1)
    print(result)

    result = await client.register_address('admin2', 'admin', 1)
    print(result)

    available = await client.is_address_available('admin', 1)
    print(available)


    result = await client.send_mail('admin', 'admin', 'admin2', 'Hey!')
    print(result)
    
    #await client.send_raw_message(OPCODES['PING'])
    #result = await client.wait_for_raw_message(1024, 1)
    #print(f'Message: {result}')

    


    await client.close()

if __name__ == '__main__':
    asyncio.run(main())