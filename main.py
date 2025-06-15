import socket
import threading


def main():
    print("Server starting on localhost:6379")

    server_socket = socket.create_server(("localhost", 6379), reuse_port=True)
    connection, _ = server_socket.accept()

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
        while True:
            data = connection.recv(1024)
            if not data:
                break  # Client closed connection

            # Split data by newline to handle multiple commands
            commands = data.split(b"\n")
            for command in commands:
                if command.strip().upper() == b"PING":
                    connection.sendall(b"+PONG\r\n")
                elif command.strip():  # If command isn't empty, but not PING
                    connection.sendall(b"-ERR unknown command\r\n")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
