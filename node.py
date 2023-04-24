import asyncio
import base64
import signal
import sys
import json
import aioconsole
import socket


myname = 'name'

import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))

myip = s.getsockname()[0]

s.close()

broadcast_domain = myip[:myip.rfind('.')]

print(myip, broadcast_domain)

aleykumselam = {
    'type': 'aleykumselam'
}

hello = {
    'type': 'hello'
}

peers = {}


class ReceiveBuffer(list):
    SIZE = 10


class BroadcastProtocol(asyncio.DatagramProtocol):
    def __init__(self, *, loop = None):
        self.loop = asyncio.get_event_loop() if loop is None else loop

    def connection_made(self, transport: asyncio.transports.DatagramTransport):
        self.transport = transport
        self.buffer = ReceiveBuffer()
        self.file_data = {}

        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        self.loop.create_task(self.read_buffer())

        self.broadcast()

    def datagram_received(self, data, addr):
        self.loop.create_task(self.handle_income_packet(data, addr))
    
    async def read_buffer(self):
        while True:
            if self.buffer:
                message = self.buffer[0]
                data = base64.b64decode(message['body'])
                self.file_data[message['seq']] = data

                del self.buffer[0]
            
            
            await asyncio.sleep(0)     
    
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
                print(f'got packet {message["seq"]}')

                if len(self.buffer) < self.buffer.SIZE:
                    self.buffer.append(message)

                    ack = {
                        'type': 5,
                        'seq': message['seq'],
                        'rwnd': self.buffer.SIZE - len(self.buffer)
                    }

                    self.transport.sendto(json.dumps(ack).encode(), addr)

                    data = base64.b64decode(message['body'])

                    if data == b'end_of_file':
                        f = open(message['name'], 'wb')

                        for i in range(1, message['seq']):
                            f.write(self.file_data[i])
                        
                        f.close()

                    print(len(self.buffer))   
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
    def __init__(self, loop, filename, packet_size, on_con_lost):
        self.loop = asyncio.get_event_loop() if loop is None else loop

        f = open(filename, 'rb')
        data = f.read()

        n_packets = len(data) // packet_size
        
        packet_data = []
        for i in range(n_packets):
            packet_data.append(data[packet_size * i : packet_size * (i + 1)])
        
        if n_packets * packet_size < len(data):
            packet_data.append(data[packet_size * n_packets : packet_size * (n_packets + 1)])
        
        packets = [{
            'type': 4,
            'name': filename,
            'seq': i,
            'body': str(base64.b64encode(data))[2:-1]
        } for i, data in enumerate(packet_data, start=1)]

        self.packets = packets
        self.end_packet = {
            'type': 4,
            'name': filename,
            'seq': packets[-1]['seq'] + 1,
            'body': str(base64.b64encode(b'end_of_file'))[2:-1]
        }

        self.in_flight = []
        self.acked = []
        self.rwnd = 0

        self.on_con_lost = on_con_lost

    def connection_made(self, transport):
        self.transport = transport
        self.loop.create_task(self.send_file())

    def datagram_received(self, data, addr):
        message = json.loads(data.decode())

        if message['seq'] == self.end_packet['seq']:
            self.transport.close()
        
        if message['seq'] not in self.acked:
            self.acked.append(message['seq'])
        
        self.rwnd = message['rwnd']

    async def send_file(self):
        await self.send_packet(self.packets[0])

        print('first packet acked')

        packet_tasks = []
        while len(self.acked) < len(self.packets):
            next_packets = [packet
                            for packet in self.packets[1:]
                            if packet['seq'] not in self.acked
                                and packet['seq'] not in self.in_flight][:self.rwnd - len(self.in_flight)]

            packet_tasks.extend(asyncio.create_task(self.send_packet(packet)) for packet in next_packets)

            await asyncio.sleep(0)
        
        print('waiting other packets')
        await asyncio.gather(*packet_tasks)
        
        await self.send_packet(self.end_packet)
        
    async def send_packet(self, packet):
        self.in_flight.append(packet['seq'])

        self.transport.sendto((json.dumps(packet)).encode())

        print(f'sent packet {packet["seq"]}')

        try:
            await asyncio.wait_for(self.wait_ack(packet['seq']), timeout=1)
        except asyncio.TimeoutError:
            del self.in_flight[self.in_flight.index(packet['seq'])]
            await self.send_packet(packet)
    
    async def wait_ack(self, seq):
        while seq not in self.acked:
            await asyncio.sleep(0)
        
        print(f'got acked for {seq}')
        del self.in_flight[self.in_flight.index(seq)]
    
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
    name = await aioconsole.ainput('Enter recipient name: ')
    ip = list(peers.keys())[list(peers.values()).index(name)]
    
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
    name = await aioconsole.ainput('Enter recipient name: ')

    ip = list(peers.keys())[list(peers.values()).index(name)]
    try:
        loop = asyncio.get_running_loop()

        on_con_lost = loop.create_future()

        transport, protocol = await loop.create_datagram_endpoint(
            lambda: SendFileProtocol(loop, filename, 1500, on_con_lost),
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
                await send_message()
        elif key == 'f':
            if not peers:
                await aioconsole.aprint('There are no available recipients. Try later.')
            else:
                await send_file()
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

    global myname
    myname = await aioconsole.ainput('Enter your name: ')
    hello['myname'] = myname
    aleykumselam['myname'] = myname

    listen_coro = listen()
    hello_coro = loop.create_datagram_endpoint(
        lambda: BroadcastProtocol(loop=loop),
        local_addr=('0.0.0.0', 12345),
        allow_broadcast=True
    )
    control_coro = control()
    await asyncio.gather(listen_coro, hello_coro, control_coro)


asyncio.run(main())