import socket
import threading


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
                elif buffer.strip():  # unknown inline command
                    connection.sendall(b"-ERR unknown command\r\n")
                    buffer = b""
                    continue

            # Process command
            command = cmd[0].upper()
            if command == b"PING":
                connection.sendall(b"+PONG\r\n")
            elif command == b"ECHO" and len(cmd) == 2:
                connection.sendall(encode_bulk_string(cmd[1]))
            else:
                connection.sendall(b"-ERR unknown command\r\n")

            # Clear buffer after processing one command
            buffer = b""
    finally:
        connection.close()


def encode_bulk_string(s):
    return b"$" + str(len(s)).encode() + b"\r\n" + s + b"\r\n"


def parse_resp(data):
    # Basic parser for RESP array with bulk strings
    # Example input:
    # ECHO command --> b'*2\r\n$4\r\nECHO\r\n$3\r\nhey\r\n'
    lines = data.split(b'\r\n')
    if not lines or not lines[0].startswith(b'*'):
        return None

    try:
        num_elements = int(lines[0][1:])  # num of elements in the array
        elements = []
        idx = 1
        for _ in range(num_elements):
            # $ this character appears before bulk string an contains the length in bytes
            if not lines[idx].startswith(b'$'):
                return None
            length = int(lines[idx][1:])
            idx += 1
            element = lines[idx]
            idx += 1
            elements.append(element)
        return elements
    except Exception:
        return None


# RESP


# RESP Encoding of: ECHO hey
# b"*2\r\n"        # * means Array, and 2 is the number of elements in the array
# b"$4\r\n"        # $ means Bulk String, and 4 is the number of bytes in the first element
# b"ECHO\r\n"      # The first bulk string: the command name "ECHO"
# b"$3\r\n"        # Second bulk string, 3 bytes in length
# b"hey\r\n"       # The argument to ECHO — "hey"


if __name__ == "__main__":
    main()
