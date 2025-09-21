import socket
from time import sleep

CRLF = b"\r\n"


def send_cmd(addr, *parts):
    host, port = addr
    with socket.create_connection((host, port), timeout=2.0) as s:
        payload = b"*" + str(len(parts)).encode() + CRLF
        for p in parts:
            if isinstance(p, str): p = p.encode()
            payload += b"$" + str(len(p)).encode() + CRLF + p + CRLF
        s.sendall(payload)
        return read_reply(s)


def read_reply(sock):
    def readn(n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk: raise EOFError
            buf += chunk
        return buf

    def readline():
        buf = b""
        while True:
            ch = sock.recv(1)
            if not ch: raise EOFError
            buf += ch
            if buf.endswith(CRLF): return buf[:-2]

    prefix = readn(1)
    if prefix == b"+": return ("simple", readline().decode())
    if prefix == b"-": return ("error", readline().decode())
    if prefix == b":": return ("int", int(readline().decode()))
    if prefix == b"$":
        length = int(readline().decode())
        if length == -1: return ("bulk", None)
        data = readn(length); assert readn(2) == CRLF
        try: return ("bulk", data.decode())
        except UnicodeDecodeError: return ("bulk", data)
    raise AssertionError("Unknown reply type")


def test_ping(server_address):
    rtype, val = send_cmd(server_address, "PING")
    assert (rtype, val) == ("simple", "PONG")

    rtype, val = send_cmd(server_address, "PING", "hey")
    assert (rtype, val) == ("bulk", "hey")


def test_set_get(server_address):
    rtype, val = send_cmd(server_address, "SET", "a", "1")
    assert (rtype, val) == ("simple", "OK")

    rtype, val = send_cmd(server_address, "GET", "a")
    assert (rtype, val) == ("bulk", "1")


def test_set_nx_xx(server_address):
    send_cmd(server_address, "DEL", "nxkey")

    rtype, _ = send_cmd(server_address, "SET", "nxkey", "v", "NX")
    assert rtype == "simple"

    rtype, val = send_cmd(server_address, "SET", "nxkey", "v2", "NX")
    assert rtype == "bulk" and val is None

    rtype, val = send_cmd(server_address, "SET", "xxkey", "v2", "XX")
    assert rtype == "bulk" and val is None

    send_cmd(server_address, "SET", "xxkey", "v")

    rtype, val = send_cmd(server_address, "SET", "xxkey", "v2", "XX")
    assert rtype == "simple"


def test_ttl(server_address):
    send_cmd(server_address, "SET", "t1", "x", "EX", "1")

    rtype, ttl = send_cmd(server_address, "TTL", "t1")
    assert rtype == "int" and ttl in (0, 1)

    sleep(1.2)

    rtype, ttl2 = send_cmd(server_address, "TTL", "t1")
    assert (rtype, ttl2) == ("int", -2)


def test_expire_and_get(server_address):
    send_cmd(server_address, "SET", "k", "v")

    rtype, res = send_cmd(server_address, "EXPIRE", "k", "1")
    assert (rtype, res) == ("int", 1)

    rtype, ttl = send_cmd(server_address, "TTL", "k")
    assert rtype == "int" and ttl in (0, 1)

    sleep(1.1)

    rtype, val = send_cmd(server_address, "GET", "k")
    assert (rtype, val) == ("bulk", None)


def test_del_exists(server_address):
    send_cmd(server_address, "SET", "d1", "x")
    send_cmd(server_address, "SET", "d2", "y")

    rtype, count = send_cmd(server_address, "EXISTS", "d1", "missing", "d2")
    assert (rtype, count) == ("int", 2)

    rtype, count = send_cmd(server_address, "DEL", "d1", "d2", "missing")
    assert (rtype, count) == ("int", 2)

    rtype, count = send_cmd(server_address, "EXISTS", "d1", "d2")
    assert (rtype, count) == ("int", 0)


def test_px_and_pexpire(server_address):
    rtype, val = send_cmd(server_address, "SET", "pxk", "v", "PX", "100")
    assert (rtype, val) == ("simple", "OK")

    rtype, ttl = send_cmd(server_address, "TTL", "pxk")
    assert rtype == "int" and ttl in (0, 1)

    rtype, res = send_cmd(server_address, "PEXPIRE", "pxk2", "100")
    assert (rtype, res) == ("int", 0)

    send_cmd(server_address, "SET", "pxk2", "v2")

    rtype, res = send_cmd(server_address, "PEXPIRE", "pxk2", "100")
    assert (rtype, res) == ("int", 1)


def test_keep_ttl(server_address):
    send_cmd(server_address, "SET", "kt", "v", "EX", "2")

    rtype, ttl1 = send_cmd(server_address, "TTL", "kt")
    assert rtype == "int" and ttl1 in (1, 2)

    rtype, val = send_cmd(server_address, "SET", "kt", "v2", "KEEPTTL")
    assert (rtype, val) == ("simple", "OK")

    rtype, ttl2 = send_cmd(server_address, "TTL", "kt")
    assert rtype == "int" and ttl2 >= 0


def test_wrong_arity_and_unknown(server_address):
    rtype, msg = send_cmd(server_address, "GET")
    assert rtype == "error"

    rtype, msg = send_cmd(server_address, "EXPIRE", "k", "str")
    assert rtype == "error"

    rtype, msg = send_cmd(server_address, "FOOBAR")
    assert rtype == "error"
