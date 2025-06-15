import subprocess
import threading


def send_command(client_id, command_bytes, expected_response_bytes):
    proc = subprocess.Popen(
        ['nc', 'localhost', '6379'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Send command (raw bytes)
    proc.stdin.write(command_bytes)
    proc.stdin.flush()
    proc.stdin.close()

    # Read full response (also bytes)
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


# Byte-based RESP command inputs
test_cases = [
    (b"PING\r\n", b"+PONG\r\n"),
    (b"*2\r\n$4\r\nECHO\r\n$5\r\nhello\r\n", b"$5\r\nhello\r\n"),
    (b"*2\r\n$4\r\nECHO\r\n$7\r\nchatgpt\r\n", b"$7\r\nchatgpt\r\n"),
    (b"FOO\r\n", b"-ERR unknown command\r\n"),
]

threads = []

for i, (cmd, expected) in enumerate(test_cases):
    t = threading.Thread(target=send_command, args=(i + 1, cmd, expected))
    t.start()
    threads.append(t)

for t in threads:
    t.join()
