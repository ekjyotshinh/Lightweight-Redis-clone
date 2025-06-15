import subprocess
import threading
import time


def send_command(client_id, command_bytes, expected_response_bytes, delay_before_check=0):
    """
    Send command_bytes to the Redis-like server,
    then optionally wait delay_before_check seconds before reading the response.
    """
    proc = subprocess.Popen(
        ['nc', 'localhost', '6379'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    proc.stdin.write(command_bytes)
    proc.stdin.flush()
    proc.stdin.close()

    if delay_before_check > 0:
        time.sleep(delay_before_check)

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


# RESP test cases including expiry tests
test_cases = [
    # Basic commands
    (b"PING\r\n", b"+PONG\r\n", 0),

    (b"*2\r\n$4\r\nECHO\r\n$5\r\nhello\r\n", b"$5\r\nhello\r\n", 0),
    (b"*2\r\n$4\r\nECHO\r\n$7\r\nchatgpt\r\n", b"$7\r\nchatgpt\r\n", 0),

    (b"FOO\r\n", b"-ERR unknown command\r\n", 0),

    # SET and GET without expiry
    (b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n", b"+OK\r\n", 0),
    (b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n", b"$3\r\nbar\r\n", 0),

    (b"*2\r\n$3\r\nGET\r\n$6\r\nno_key\r\n", b"$-1\r\n", 0),

    # SET with PX expiry 500ms
    (b"*5\r\n$3\r\nSET\r\n$5\r\nhello\r\n$5\r\nworld\r\n$2\r\nPX\r\n$3\r\n500\r\n", b"+OK\r\n", 0),

    # Immediately get key, should exist
    (b"*2\r\n$3\r\nGET\r\n$5\r\nhello\r\n", b"$5\r\nworld\r\n", 0),

    # Wait 600ms (> expiry) then get key, should be expired (null bulk string)
    (b"*2\r\n$3\r\nGET\r\n$5\r\nhello\r\n", b"$-1\r\n", 0.6),
]

threads = []

for i, (cmd, expected, delay) in enumerate(test_cases):
    t = threading.Thread(target=send_command,
                         args=(i + 1, cmd, expected, delay))
    t.start()
    threads.append(t)

for t in threads:
    t.join()
