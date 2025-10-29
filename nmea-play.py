#!python3
import argparse
import asyncio
import time

# I like netcat
# nc localhost 10110

# an async generator for the next line from an nmea file
async def next_nmea(filename, noGps):
    reality_offset = None
    with open(filename) as f:
        next_delivery = time.monotonic()
        for line in f:
            # check validity
            if len(line)<6:
                continue
            # timestamp?
            if line[3:6] == 'ZDA':
                timestamp = int(line[7:9]) * 3600 + int(line[9:11]) * 60 + int(line[11:13])
                if not reality_offset:
                    reality_offset = time.monotonic() - timestamp
                else:
                    next_delivery = timestamp + reality_offset
            # delay until it's time to deliver
            await asyncio.sleep(next_delivery - time.monotonic())
            next_delivery += len(line)/600. # 4800 bit/sec
            # serve
            if not (noGps and (line[3:6] == 'GLL' or line[3:6] == 'VTG')):
                yield line

class ServeIterable:
    def __init__(self, port):
        self.port = port
        self.clients = []

    def new_client(self, reader, writer):
        self.clients.append(writer)
        print(f"Added client: {writer.transport.get_extra_info('peername')}")

    async def playback_loop(self, iterable):
        await asyncio.start_server(self.new_client, port=self.port)
        async for line in iterable:
            for client in self.clients:
                try:
                    await client.drain()
                    client.write(line.encode())
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    self.clients.remove(client)
                    print(f"Lost client: {client.transport.get_extra_info('peername')}")
            

parser = argparse.ArgumentParser(
    description="Plays an NMEA log file through TCP with sensible timings."
)
parser.add_argument('filename', help="An NMEA log file containing 'ZDA' timestamps")
parser.add_argument('port', help="TCP port number to serve from (default 10110)", nargs='?', default=10110)
parser.add_argument('--nogps', action='store_true', help='Disable GPS output')
args = parser.parse_args()

asyncio.run(ServeIterable(args.port).playback_loop(next_nmea(args.filename, args.nogps)))
