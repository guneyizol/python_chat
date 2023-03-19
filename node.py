import asyncio
import signal
import sys
import json
import aioconsole
import socket


myname = 'name'
myip = '192.168.1.7'
broadcast_domain = '192.168.1'

aleykumselam = {
    'type': 'aleykumselam'
}

hello = {
    'type': 'hello'
}

peers = {}

class BroadcastProtocol(asyncio.DatagramProtocol):
    def __init__(self, *, loop = None):
        self.loop = asyncio.get_event_loop() if loop is None else loop

    def connection_made(self, transport: asyncio.transports.DatagramTransport):
        print('started')
        self.transport = transport
        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast()

    def datagram_received(self, data, addr):
        self.loop.create_task(self.handle_income_packet(data, addr))
    
    async def handle_income_packet(self, data, addr):
        print('data received:', data, addr)
        writer = None
        try:
            message = json.loads(data.decode().rstrip())

            if message['type'] == 'hello':
                if addr[0] != myip:
                    peers[addr[0]] = message['myname']

                    _, writer = await asyncio.wait_for(asyncio.open_connection(*addr), timeout=5)

                    writer.write((json.dumps(aleykumselam) + '\n').encode())
                    await writer.drain()
            print(peers)
        except:
            pass
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

    def broadcast(self):
        self.transport.sendto((json.dumps(hello) + '\n').encode(), (f'{broadcast_domain}.255', 12345))
        self.loop.call_later(5, self.broadcast)


async def handle_connection(reader, writer):
    try:
        data = await reader.readline()
        message = json.loads(data.decode().rstrip())
        addr = writer.get_extra_info('peername')

        ip, _ = addr
        if message.get('type') == 'aleykumselam':
            peers[ip] = message['myname']
        if message.get('type') == 'message':
            print(f"{peers[ip]}: {message['content']}")

        print(peers)
    except:
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def listen():
    server = await asyncio.start_server(handle_connection, myip, 12345)
    await server.serve_forever()


async def send_message():
    ip = await aioconsole.ainput('enter recipient ip: ')
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
    except ConnectionRefusedError:
        print('The peer is offline. Your message was not delivered.')
        del peers[ip]
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
    bd = await aioconsole.ainput('Enter the broadcast domain (default is 192.168.1): ')
    broadcast_domain = bd if bd else '192.168.1'

    listen_task = asyncio.create_task(listen())
    hello_task = asyncio.create_task(loop.create_datagram_endpoint(
        lambda: BroadcastProtocol(loop=loop),
        local_addr=(f'{broadcast_domain}.255', 12345),
        allow_broadcast=True
    ))
    control_task = asyncio.create_task(control())
    await asyncio.gather(listen_task, hello_task, control_task)


asyncio.run(main())