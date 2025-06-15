import socket
import threading
import time

# In-memory key-value store with expiry support
# store: key -> {"value": bytes, "expire_at": float|None}
store = {}
store_lock = threading.Lock()


def main():
    print("Server starting on localhost:6379")

    server_socket = socket.create_server(("localhost", 6379), reuse_port=True)

    try:
        while True:
            connection, _ = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(connection,))
            thread.daemon = True  # allows threads to be killed with the main process
            thread.start()
    finally:
        server_socket.close()


def handle_client(connection):
    try:
        buffer = b""
        while True:
            data = connection.recv(1024)
            if not data:
                break
            buffer += data

            # Try parsing command
            cmd = parse_resp(buffer)
            if cmd is None:
                # it is a simple command
                if buffer.strip().upper() == b"PING":
                    connection.sendall(b"+PONG\r\n")
                    buffer = b""
                    continue
                elif buffer.strip():
                    # Unknown inline command (not RESP)
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
            else:
                connection.sendall(b"-ERR unknown command\r\n")

            # Clear buffer after processing one command
            buffer = b""
    finally:
        connection.close()


def handle_set_command(cmd):
    """
    SET key value [PX milliseconds]
    """
    key = cmd[1]
    value = cmd[2]
    expire_at = None

    # Optional PX argument
    if len(cmd) > 3:
        # Must be exactly 5 elements for PX usage
        if len(cmd) == 5 and cmd[3].upper() == b"PX":
            try:
                ms = int(cmd[4])
                expire_at = time.time() + ms / 1000
                # print(f"Current time: {time.time()}")
                # print(f"Key expires at Unix time: {expire_at}")
            except ValueError:
                return b"-ERR PX value is not an integer\r\n"
        else:
            return b"-ERR syntax error\r\n"

    with store_lock:  # lock is automatically released
        store[key] = {"value": value, "expire_at": expire_at}
        # print(store)
    return b"+OK\r\n"


def handle_get_command(cmd):
    key = cmd[1]
    with store_lock:  # lock is automatically released
        entry = store.get(key)
        # print(entry)
        # print(time.time())
        if entry is None:
            return b"$-1\r\n"  # RESP null bulk string
        if entry["expire_at"] is not None and entry["expire_at"] < time.time():
            # Key expired, remove it
            # print("deleteing it")
            del store[key]
            return b"$-1\r\n"
        return encode_bulk_string(entry["value"])


def encode_bulk_string(s):
    return b"$" + str(len(s)).encode() + b"\r\n" + s + b"\r\n"


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
            if idx >= len(lines):
                return None
            if not lines[idx].startswith(b'$'):
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
        return elements
    except Exception:
        return None


if __name__ == "__main__":
    main()
