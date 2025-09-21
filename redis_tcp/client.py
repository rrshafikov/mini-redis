# Simple RESP client + REPL
import socket, sys

CRLF = b"\r\n"


def encode_array(parts):
    out = [b"*" + str(len(parts)).encode() + CRLF]
    for p in parts:
        if isinstance(p, str):
            p = p.encode()
        out.append(b"$" + str(len(p)).encode() + CRLF + p + CRLF)
    return b"".join(out)


def decode_reply(sock):
    def readn(n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise EOFError
            buf += chunk
        return buf

    def readline():
        buf = b""
        while True:
            ch = sock.recv(1)
            if not ch:
                raise EOFError
            buf += ch
            if buf.endswith(CRLF):
                return buf[:-2]

    prefix = readn(1)
    if prefix == b"+":
        return readline().decode()
    if prefix == b"-":
        return Exception(readline().decode())
    if prefix == b":":
        return int(readline().decode())
    if prefix == b"$":
        length = int(readline().decode())
        if length == -1: return None
        data = readn(length)
        assert readn(2) == CRLF
        try: return data.decode()
        except UnicodeDecodeError: return data
    if prefix == b"*":
        length = int(readline().decode())
        if length == -1: return None
        return [decode_reply(sock) for _ in range(length)]
    # fallback
    line = prefix + readline() + CRLF
    return line.decode().strip()


def repl(host="127.0.0.1", port=6380):
    print(f"Connected to mini-redis at {host}:{port}. Ctrl+C to exit.")
    with socket.create_connection((host, port)) as sock:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                print()
                break
            if not line:
                continue
            parts = line.split()
            sock.sendall(encode_array(parts))
            reply = decode_reply(sock)
            if isinstance(reply, Exception):
                print(f"(error) {reply}")
            else:
                print(reply)


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 6380
    if len(sys.argv) >= 2: host = sys.argv[1]
    if len(sys.argv) >= 3: port = int(sys.argv[2])
    repl(host, port)
