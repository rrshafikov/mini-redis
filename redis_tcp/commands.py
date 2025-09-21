# Command registry and core commands (start with PING)

from typing import Callable, Awaitable, List, Optional
from .datastore import DataStore
from .protocol import encode_simple_string, encode_bulk_string, encode_integer, encode_error

Handler = Callable[[List[bytes], DataStore], Awaitable[bytes]]


class CommandRegistry:
    def __init__(self):
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str):
        def deco(fn: Handler):
            self._handlers[name.upper()] = fn
            return fn
        return deco

    def get(self, name: str) -> Optional[Handler]:
        return self._handlers.get(name.upper())


registry = CommandRegistry()


@registry.register("PING")
async def cmd_ping(args: List[bytes], store: DataStore) -> bytes:
    if args:
        return encode_bulk_string(args[0])
    return encode_simple_string("PONG")
