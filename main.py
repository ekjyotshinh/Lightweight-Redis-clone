import os
import socket
import threading
import time
import json

# In-memory key-value store with expiry support
# store: key -> {"value": bytes, "expire_at": float|None}
store = {}
store_lock = threading.Lock()

# Configuration parameters for RDB persistence
config = {
    b"dir": b"/redis-data",
    b"dbfilename": b"rdbfile"
}
persistence_file = "data.rdb.json"
dirty = False  # set to True when store changes


def main():
    print("Server starting on localhost:6379")
    load_store_from_file()
    threading.Thread(target=autosave_thread, daemon=True).start()
    threading.Thread(target=cleanup_expired_keys, daemon=True).start()

    server_socket = socket.create_server(("localhost", 6379), reuse_port=True)

    try:
        while True:
            connection, _ = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(connection,))
            thread.daemon = True
            thread.start()
    finally:
        server_socket.close()


def load_store_from_file(path=persistence_file):
    global store
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        raw = json.load(f)
    now = time.time()
    with store_lock:
        for k, v in raw.items():
            if v["expire_at"] is None or v["expire_at"] > now:
                store[k.encode()] = {
                    "value": v["value"].encode(),
                    "expire_at": v["expire_at"]
                }


def save_store_to_file(path=persistence_file):
    global dirty
    now = time.time()

    with store_lock:
        serializable = {
            k.decode(): {
                "value": v["value"].decode(),
                "expire_at": v["expire_at"]
            }
            for k, v in store.items()
            if v["expire_at"] is None or v["expire_at"] > now
        }
        dirty = False

    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp_path, path)


def autosave_thread(interval=5):
    while True:
        time.sleep(interval)
        if dirty:
            save_store_to_file()


def cleanup_expired_keys(interval=10):
    while True:
        time.sleep(interval)
        now = time.time()
        with store_lock:
            expired = [k for k, v in store.items() if v["expire_at"]
                       is not None and v["expire_at"] < now]
            for k in expired:
                del store[k]


def handle_client(connection):
    try:
        buffer = b""
        while True:
            data = connection.recv(1024)
            if not data:
                break
            buffer += data

            cmd = parse_resp(buffer)
            if cmd is None:
                # it is a simple command
                if buffer.strip().upper() == b"PING":
                    connection.sendall(b"+PONG\r\n")
                    buffer = b""
                    continue
                elif buffer.strip():
                    connection.sendall(b"-ERR unknown command\r\n")
                    buffer = b""
                    continue
                # else wait for more data
                continue

            # Process the RESP array command
            command = cmd[0].upper()

            if command == b"PING":
                connection.sendall(b"+PONG\r\n")
            elif command == b"ECHO" and len(cmd) == 2:
                connection.sendall(encode_bulk_string(cmd[1]))
            elif command == b"SET" and len(cmd) >= 3:
                response = handle_set_command(cmd)
                connection.sendall(response)
            elif command == b"GET" and len(cmd) == 2:
                response = handle_get_command(cmd)
                connection.sendall(response)
            elif command == b"DEL" and len(cmd) == 2:
                response = handle_del_command(cmd)
                connection.sendall(response)
            elif command == b"CONFIG" and len(cmd) == 3 and cmd[1].upper() == b"GET":
                response = handle_get_config_command(cmd)
                connection.sendall(response)
            else:
                connection.sendall(b"-ERR unknown command\r\n")

            # Clear buffer after processing one command
            buffer = b""
    finally:
        connection.close()


def handle_get_config_command(cmd):
    param = cmd[2].lower()
    if param in config:
        response = encode_array([
            param,
            config[param]
        ])
    else:
        response = encode_array([])  # empty array if unknown param
    return response


def handle_set_command(cmd):
    key = cmd[1]
    value = cmd[2]
    expire_at = None

    if len(cmd) == 5 and cmd[3].upper() == b"PX":
        try:
            ms = int(cmd[4])
            expire_at = time.time() + ms / 1000
        except ValueError:
            return b"-ERR PX value is not an integer\r\n"
    elif len(cmd) not in [3, 5]:
        return b"-ERR syntax error\r\n"

    with store_lock:
        global dirty
        dirty = True
        store[key] = {"value": value, "expire_at": expire_at}
    return b"+OK\r\n"


def handle_get_command(cmd):
    key = cmd[1]
    with store_lock:
        entry = store.get(key)

        # print(f"GET key: {key}")
        # print(f"Entry found: {entry}")
        # print(f"Current time: {time.time()}")

        if entry is None:
            # print("Key not found.")
            return b"$-1\r\n"

        expire_at = entry.get("expire_at")
        if expire_at is not None and expire_at < time.time():
            del store[key]
            return b"$-1\r\n"

        return encode_bulk_string(entry["value"])


def handle_del_command(cmd):
    key = cmd[1]
    with store_lock:
        global dirty
        if key in store:
            del store[key]
            dirty = True
            return b":1\r\n"
        else:
            return b":0\r\n"


def encode_bulk_string(s):
    return b"$" + str(len(s)).encode() + b"\r\n" + s + b"\r\n"


def encode_array(items):
    out = b"*" + str(len(items)).encode() + b"\r\n"
    for item in items:
        out += encode_bulk_string(item)
    return out


def parse_resp(data):
    """
    Parses a RESP array of bulk strings.
    Example input:
    b'*2\r\n$4\r\nECHO\r\n$3\r\nhey\r\n'
    Returns list of bytes: [b'ECHO', b'hey'] or None if incomplete/invalid
    """
    lines = data.split(b'\r\n')
    if not lines or not lines[0].startswith(b'*'):
        return None

    try:
        num_elements = int(lines[0][1:])
        elements = []
        idx = 1
        for _ in range(num_elements):
            if idx >= len(lines) or not lines[idx].startswith(b'$'):
                return None
            length = int(lines[idx][1:])
            idx += 1
            if idx >= len(lines):
                return None
            element = lines[idx]
            if len(element) != length:
                return None
            idx += 1
            elements.append(element)
        # print(elements)
        return elements
    except Exception:
        return None


if __name__ == "__main__":
    main()
