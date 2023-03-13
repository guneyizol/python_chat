import asyncio
import signal
import sys
import json
import aioconsole


myname = 'name'
myip = '192.168.1.7'

aleykumselam = {
    'type': 'aleykumselam'
}

hello = {
    'type': 'hello'
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
        elif message.get('type') == 'message':
            print(message['content'])
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


async def send_message():
    ip = await aioconsole.ainput('enter recipient IP: ')
    message = await aioconsole.ainput('enter your message (end it with a newline): ')

    writer = None
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, 12345), timeout=5)

        writer.write((json.dumps({
            'type': 'message',
            'content': message,
            'myname': myname
        }) + '\n').encode())
        await writer.drain()
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()


async def control():
    key = await aioconsole.ainput('To send a message, press M\n'
                                  'To see the available recipient IPs, press A\n'
                                  'To exit, press E\n')
    while True:
        key = key.lower()
        if key == 'm':
            if not peers:
                await aioconsole.aprint('There are no available recipients. Try later.')
            else:
                await asyncio.create_task(send_message())
        elif key == 'a':
            if not peers:
                await aioconsole.aprint('There are no available recipients.')
            for name, ip in peers.items():
                await aioconsole.aprint(f'{name}: {ip}')
        elif key == 'e':
            sys.exit(0)

        key = await aioconsole.ainput()


def keyboardInterruptHandler():
    print('\nexiting')
    sys.exit(0)


async def main():
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, keyboardInterruptHandler)

    global myip
    myip = await aioconsole.ainput('Enter your ip: ')

    global myname
    myname = await aioconsole.ainput('Enter your name: ')
    hello['myname'] = myname
    aleykumselam['myname'] = myname

    global broadcast_domain
    broadcast_domain = await aioconsole.ainput('Enter broadcast domain: ')

    listen_task = asyncio.create_task(listen())
    hello_task = asyncio.create_task(send_hello())
    control_task = asyncio.create_task(control())
    await asyncio.gather(listen_task, hello_task, control_task)


asyncio.run(main())