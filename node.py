import asyncio
import signal
import sys
import json


myname = 'name'
myip = '192.168.1.7'

aleykumselam = {
    'type': 'aleykumselam',
    'myname': myname
}

hello = {
    'type': 'hello',
    'myname': myname
}

broadcast_domain = '192.168.1'

peers = {}

async def handle_connection(reader, writer):
    try:
        data = await reader.readline()
        message = json.loads(data.decode().rstrip())
        if message.get('type') == 'hello':
            addr = writer.get_extra_info('peername')

            ip, _ = addr
            peers[message['myname']] = ip

            writer.write((json.dumps(aleykumselam) + '\n').encode())
            await writer.drain()
    except:
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def listen():
    server = await asyncio.start_server(handle_connection, myip, 12345)
    await server.serve_forever()


async def get_aleykumselam(ip):
    writer = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, 12345), timeout=5)

        writer.write((json.dumps(hello) + '\n').encode())
        await writer.drain()

        data = await asyncio.wait_for(reader.readline(), timeout=5)

        message = json.loads(data.decode().rstrip())

        if message['type'] == 'aleykumselam':
            peers[message['myname']] = ip
        
        print(peers)
    except:
        pass  # ignore any errors and go on
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()
        
        
async def send_hello():
    while True:
        hellos = []

        for i in range(2, 256):
            ip = f'{broadcast_domain}.{i}'
            if ip != myip:
                hellos.append(get_aleykumselam(ip))
        
        await asyncio.gather(*hellos)
        await asyncio.sleep(2)


def keyboardInterruptHandler():
    print('\nexiting')
    sys.exit(0)


async def main():
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, keyboardInterruptHandler)

    listen_task = asyncio.create_task(listen())
    hello_task = asyncio.create_task(send_hello())
    await asyncio.gather(listen_task, hello_task)


asyncio.run(main())