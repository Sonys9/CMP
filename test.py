import cmp
import asyncio
import base64
from opcodes import OPCODES

async def main():
    server = cmp.Server('127.0.0.1', 16760)
    client = cmp.Client('127.0.0.1', 16760)
    await server.start()
    await client.connect()

    available = await client.is_address_available('admin', 1) # True
    print(available)

    result = await client.register_address('admin', 'admin', 1) # True
    print(result)

    result = await client.register_address('admin', 'admin', 1) # False
    print(result)

    with open('image.png', 'rb') as f:
        image_content = f.read()

    result = await client.send_mail('admin', 'admin', 'admin2', 'Hey!', files=[{'file_id': 'image.png'}]) # True
    print(result)
    

    #mails = await client.get_mails('admin', 'admin') # 
    #print(mails)
    
    #await client.send_raw_message(OPCODES['PING'])
    #result = await client.wait_for_raw_message(1024, 1)
    #print(f'Message: {result}')

    


    await client.close()

if __name__ == '__main__':
    asyncio.run(main())