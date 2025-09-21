# Minimal RESP2 encoder/decoder for server.

import asyncio
from typing import Optional, Union, List, Any

CRLF = b"\r\n"


class RESPError(Exception):
    pass


def encode_simple_string(s: str) -> bytes:
    return b"+" + s.encode("utf-8") + CRLF


def encode_error(s: str) -> bytes:
    return b"-" + s.encode("utf-8") + CRLF


def encode_integer(i: int) -> bytes:
    return b":" + str(i).encode("utf-8") + CRLF


def encode_bulk_string(data: Optional[Union[bytes, str]]) -> bytes:
    if data is None:
        return b"$-1" + CRLF
    if isinstance(data, str):
        data = data.encode("utf-8")
    return b"$" + str(len(data)).encode("utf-8") + CRLF + data + CRLF


def encode_array(items: Optional[List[Any]]) -> bytes:
    if items is None:
        return b"*-1" + CRLF
    out = [b"*" + str(len(items)).encode("utf-8") + CRLF]
    for it in items:
        if it is None:
            out.append(b"$-1" + CRLF)
        elif isinstance(it, bytes):
            out.append(b"$" + str(len(it)).encode("utf-8") + CRLF + it + CRLF)
        elif isinstance(it, str):
            bs = it.encode("utf-8")
            out.append(b"$" + str(len(bs)).encode("utf-8") + CRLF + bs + CRLF)
        elif isinstance(it, int):
            out.append(encode_integer(it))
        else:
            bs = str(it).encode("utf-8")
            out.append(b"$" + str(len(bs)).encode("utf-8") + CRLF + bs + CRLF)
    return b"".join(out)


class RESPReader:
    def __init__(self, reader: asyncio.StreamReader):
        self.reader = reader

    async def read_line(self) -> bytes:
        line = await self.reader.readline()
        if not line:
            raise EOFError("Client disconnected")
        if line.endswith(CRLF):
            return line[:-2]
        if line.endswith(b"\n"):
            return line[:-1]
        raise RESPError("Protocol error: line without CRLF")

    async def read_bulk(self, length: int) -> bytes:
        data = await self.reader.readexactly(length)
        crlf = await self.reader.readexactly(2)
        if crlf != CRLF:
            raise RESPError("Protocol error: bulk missing CRLF")
        return data

    async def read_object(self):
        prefix = await self.reader.readexactly(1)
        if prefix == b"+":
            return (await self.read_line()).decode("utf-8")
        if prefix == b"-":
            raise RESPError((await self.read_line()).decode("utf-8"))
        if prefix == b":":
            return int((await self.read_line()).decode("utf-8"))
        if prefix == b"$":
            length = int((await self.read_line()).decode("utf-8"))
            if length == -1:
                return None
            return await self.read_bulk(length)
        if prefix == b"*":
            length = int((await self.read_line()).decode("utf-8"))
            if length == -1:
                return None
            arr = []
            for _ in range(length):
                arr.append(await self.read_object())
            return arr
        # inline-commands fallback:
        rest = await self.reader.readline()
        line = (prefix + rest).strip().decode("utf-8")
        parts = line.split()
        return [p.encode("utf-8") for p in parts]


def normalize_command(obj):
    """
    Convert decoded RESP object to (CMD: str, args: List[bytes]).
    """
    if isinstance(obj, list):
        if not obj:
            return "", []
        parts: List[bytes] = []
        for item in obj:
            if item is None:
                parts.append(b"")
            elif isinstance(item, bytes):
                parts.append(item)
            elif isinstance(item, str):
                parts.append(item.encode("utf-8"))
            elif isinstance(item, int):
                parts.append(str(item).encode("utf-8"))
            else:
                parts.append(str(item).encode("utf-8"))
        cmd = parts[0].decode("utf-8").upper()
        return cmd, parts[1:]
    if isinstance(obj, (bytes, str)):
        s = obj.decode("utf-8") if isinstance(obj, bytes) else obj
        parts = s.strip().split()
        if not parts:
            return "", []
        return parts[0].upper(), [p.encode("utf-8") for p in parts[1:]]
    raise RESPError("Unsupported command format")
