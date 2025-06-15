import subprocess
import threading
import time


def send_command(client_id, command_bytes, expected_response_bytes):
    proc = subprocess.Popen(
        ['nc', 'localhost', '6379'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    proc.stdin.write(command_bytes)
    proc.stdin.flush()
    proc.stdin.close()

    response = proc.stdout.read()

    print(f"[Client {client_id}] Sent: {repr(command_bytes)}")
    print(f"[Client {client_id}] Expected: {repr(expected_response_bytes)}")
    print(f"[Client {client_id}] Received: {repr(response)}")

    if response != expected_response_bytes:
        print(f"[Client {client_id}] ❌ TEST FAILED")
    else:
        print(f"[Client {client_id}] ✅ TEST PASSED")

    proc.stdout.close()
    proc.stderr.close()
    proc.wait()


# RESP test cases
test_cases = [
    # PING
    (b"PING\r\n", b"+PONG\r\n"),

    # ECHO
    (b"*2\r\n$4\r\nECHO\r\n$5\r\nhello\r\n", b"$5\r\nhello\r\n"),
    (b"*2\r\n$4\r\nECHO\r\n$7\r\nchatgpt\r\n", b"$7\r\nchatgpt\r\n"),

    # Unknown command
    (b"FOO\r\n", b"-ERR unknown command\r\n"),

    # SET key value
    (b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n", b"+OK\r\n"),

    # GET existing key
    (b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n", b"$3\r\nbar\r\n"),

    # GET missing key
    (b"*2\r\n$3\r\nGET\r\n$6\r\nno_key\r\n", b"$-1\r\n"),
]

threads = []

for i, (cmd, expected) in enumerate(test_cases):
    t = threading.Thread(target=send_command, args=(i + 1, cmd, expected))
    t.start()
    threads.append(t)
    # Small delay to make sure SET runs before GET
    time.sleep(0.1)

for t in threads:
    t.join()
