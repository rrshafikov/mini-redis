# Async TCP server, reads RESP, routes to command handlers.

import os
import asyncio
from typing import Optional
from .datastore import DataStore
from .protocol import RESPReader, encode_error, normalize_command
from .commands import registry

DEFAULT_HOST = os.environ.get("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", "6380"))


class MiniRedisServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, cleanup_interval: float = 1.0):
        self.host = host
        self.port = port
        self.store = DataStore()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._server: Optional[asyncio.AbstractServer] = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        resp_reader = RESPReader(reader)
        try:
            while True:
                try:
                    obj = await resp_reader.read_object()
                except asyncio.IncompleteReadError:
                    break
                except Exception as e:
                    writer.write(encode_error(f"ERR {e}"))
                    await writer.drain()
                    break

                cmd, args = normalize_command(obj)
                if not cmd:
                    writer.write(encode_error("ERR empty command"))
                    await writer.drain()
                    continue

                handler = registry.get(cmd)
                if handler is None:
                    writer.write(encode_error(f"ERR unknown command '{cmd}'"))
                    await writer.drain()
                    continue

                try:
                    reply = await handler(args, self.store)
                except Exception as e:
                    writer.write(encode_error(f"ERR {e}"))
                else:
                    writer.write(reply)
                await writer.drain()
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self):
        self._server = await asyncio.start_server(self.handle_client, self.host, self.port)
        self._cleanup_task = asyncio.create_task(self.store.cleanup_task())
        sockets = self._server.sockets or []
        addrs = ", ".join(str(s.getsockname()) for s in sockets)
        print(f"mini-redis listening on {addrs}")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def serve_forever(self):
        await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Mini Redis-like TCP server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    server = MiniRedisServer(args.host, args.port)
    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
