import asyncio, socket, time, threading, os, sys
import pytest
from redis_tcp.server import MiniRedisServer

# ensure project root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def server_address():
    # free port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()

    server = MiniRedisServer(host, port)

    def run():
        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.get_event_loop().run_until_complete(server.serve_forever())

    t = threading.Thread(target=run, daemon=True)
    t.start()

    # wait until server is up
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            s = socket.create_connection((host, port), timeout=0.2)
            s.close()
            break
        except OSError:
            time.sleep(0.05)

    yield (host, port)
