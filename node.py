import asyncio
import base64
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

file = {
    'type': 4
}

ack = {
    'type': 5
}

peers = {}

class BroadcastProtocol(asyncio.DatagramProtocol):
    def __init__(self, *, loop = None):
        self.loop = asyncio.get_event_loop() if loop is None else loop

    def connection_made(self, transport: asyncio.transports.DatagramTransport):
        self.transport = transport
        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast()

    def datagram_received(self, data, addr):
        self.loop.create_task(self.handle_income_packet(data, addr))
    
    async def handle_income_packet(self, data, addr):
        writer = None
        try:
            message = json.loads(data.decode())

            if message['type'] == 'hello':
                if addr[0] != myip:
                    peers[addr[0]] = message['myname']

                    _, writer = await asyncio.wait_for(asyncio.open_connection(*addr), timeout=5)

                    writer.write((json.dumps(aleykumselam) + '\n').encode())
                    await writer.drain()
            elif message['type'] == 4:
                f = open(message['name'], 'wb')
                f.write(base64.b64decode(message['body']))

                print('written body')
                f.close()

                print(f'{peers[addr[0]]} sent the file {message["name"]}')

                self.transport.sendto(json.dumps(ack).encode(), addr)
        except:
            pass
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

    def broadcast(self):
        global peers
        peers = {}
        self.transport.sendto((json.dumps(hello)).encode(), (f'{broadcast_domain}.255', 12345))
        self.loop.call_later(60, self.broadcast)


class SendFileProtocol:
    def __init__(self, message, on_con_lost):
        self.message = message
        self.on_con_lost = on_con_lost

    def connection_made(self, transport):
        self.transport = transport
        self.send_file()

    def datagram_received(self, data, addr):
        message = json.loads(data.decode())

        print(f'received message of type {message["type"]} from {addr[0]}')

        self.transport.close()
    
    def send_file(self):
        self.transport.sendto((json.dumps(self.message)).encode())
    
    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Connection closed")
        self.on_con_lost.set_result(True)


async def handle_connection(reader, writer):
    try:
        data = await reader.readline()

        message = json.loads(data.decode().rstrip())

        ip, _ = writer.get_extra_info('peername')

        if message.get('type') == 'aleykumselam':
            peers[ip] = message['myname']
        if message.get('type') == 'message':
            print(f"{peers[ip]}: {message['content']}")
    except:
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def listen():
    server = await asyncio.start_server(handle_connection, myip, 12345)
    await server.serve_forever()


async def send_message():
    ip = await aioconsole.ainput('Enter recipient IP: ')
    message = await aioconsole.ainput('Enter your message (end it with a newline): ')

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


async def send_file():
    filename = await aioconsole.ainput('Enter the filename: ')
    ip = await aioconsole.ainput('Enter recipient IP: ')

    try:
        f = open(filename, 'rb')
        data = f.read()

        file['name'] = filename
        file['body'] = str(base64.b64encode(data))[2:-1]

        loop = asyncio.get_running_loop()

        on_con_lost = loop.create_future()

        transport, protocol = await loop.create_datagram_endpoint(
            lambda: SendFileProtocol(file, on_con_lost),
            remote_addr=(ip, 12345))

        try:
            await on_con_lost
        finally:
            transport.close()
    except OSError:
        print('Could not open the file. Make sure the file name is correct.')


async def control():
    key = await aioconsole.ainput('To send a message, press M\n'
                                  'To send a file, press F\n'
                                  'To see the available recipient IPs, press A\n'
                                  'To exit, press Ctrl+C\n')
    while True:
        key = key.lower()
        if key == 'm':
            if not peers:
                await aioconsole.aprint('There are no available recipients. Try later.')
            else:
                await asyncio.create_task(send_message())
        elif key == 'f':
            if not peers:
                await aioconsole.aprint('There are no available recipients. Try later.')
            else:
                await asyncio.create_task(send_file())
        elif key == 'a':
            if not peers:
                await aioconsole.aprint('There are no available recipients.')
            for name, ip in peers.items():
                await aioconsole.aprint(f'{name}: {ip}')

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
    receive_file_task = asyncio.create_task(receive_file())
    hello_task = asyncio.create_task(loop.create_datagram_endpoint(
        lambda: BroadcastProtocol(loop=loop),
        local_addr=('0.0.0.0', 12345),
        allow_broadcast=True
    ))
    control_task = asyncio.create_task(control())
    await asyncio.gather(listen_task, receive_file_task, hello_task, control_task)


asyncio.run(main())