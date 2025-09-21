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


@registry.register("SET")
async def cmd_set(args, store: DataStore) -> bytes:
    if len(args) < 2:
        return encode_error("ERR wrong number of arguments for 'SET' command")
    key, value = args[0], args[1]
    ex_seconds = None
    keep_ttl = False
    nx = False
    xx = False

    i = 2
    while i < len(args):
        opt = args[i].decode("utf-8").upper()
        if opt == "EX":
            i += 1
            if i >= len(args):
                return encode_error("ERR syntax error")
            try:
                ex_seconds = int(args[i].decode("utf-8"))
            except ValueError:
                return encode_error("ERR value is not an integer or out of range")
        elif opt == "PX":
            i += 1
            if i >= len(args):
                return encode_error("ERR syntax error")
            try:
                ms = int(args[i].decode("utf-8"))
                ex_seconds = ms / 1000.0
            except ValueError:
                return encode_error("ERR value is not an integer or out of range")
        elif opt == "NX":
            nx = True
        elif opt == "XX":
            xx = True
        elif opt == "KEEPTTL":
            keep_ttl = True
        else:
            return encode_error("ERR syntax error")
        i += 1

    ok = await store.set(key, value, ex_seconds=ex_seconds, keep_ttl=keep_ttl, nx=nx, xx=xx)
    if ok:
        return encode_simple_string("OK")
    return encode_bulk_string(None)  # (nil) when NX/XX condition fails


@registry.register("GET")
async def cmd_get(args, store: DataStore) -> bytes:
    if len(args) != 1:
        return encode_error("ERR wrong number of arguments for 'GET' command")
    val = await store.get(args[0])
    return encode_bulk_string(val)


@registry.register("TTL")
async def cmd_ttl(args, store: DataStore) -> bytes:
    if len(args) != 1:
        return encode_error("ERR wrong number of arguments for 'TTL' command")
    t = await store.ttl(args[0])
    return encode_integer(t)


@registry.register("EXPIRE")
async def cmd_expire(args, store: DataStore) -> bytes:
    if len(args) != 2:
        return encode_error("ERR wrong number of arguments for 'EXPIRE' command")
    try:
        sec = int(args[1].decode("utf-8"))
    except ValueError:
        return encode_error("ERR value is not an integer or out of range")
    res = await store.expire(args[0], sec)
    return encode_integer(res)


@registry.register("PEXPIRE")
async def cmd_pexpire(args, store: DataStore) -> bytes:
    if len(args) != 2:
        return encode_error("ERR wrong number of arguments for 'PEXPIRE' command")
    try:
        ms = int(args[1].decode("utf-8"))
    except ValueError:
        return encode_error("ERR value is not an integer or out of range")
    res = await store.pexpire(args[0], ms)
    return encode_integer(res)
