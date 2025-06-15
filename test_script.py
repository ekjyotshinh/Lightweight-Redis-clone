import subprocess
import time


def read_resp_response(proc_stdout):
    """
    Read a full RESP response (handles simple string, bulk string, etc.).
    """
    line = proc_stdout.readline()
    if not line:
        return b''

    if line.startswith(b"$"):  # Bulk string
        length = int(line[1:].strip())
        if length == -1:
            return line  # Null bulk string
        body = proc_stdout.read(length + 2)  # +2 for \r\n
        return line + body

    elif line.startswith((b"+", b"-", b":")):  # Simple string, error, or integer
        return line

    elif line.startswith(b"*"):  # Array (for CONFIG GET)
        count = int(line[1:].strip())
        parts = [line]
        for _ in range(count):
            parts.append(proc_stdout.readline())  # Read bulk length
            bulk_len = int(parts[-1][1:].strip())
            parts.append(proc_stdout.read(bulk_len + 2))  # Read bulk body
        return b''.join(parts)

    return line  # fallback


def send_sequence(client_id, command_sequence):
    proc = subprocess.Popen(
        ['nc', 'localhost', '6379'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    success = True
    for i, (cmd, expected, delay) in enumerate(command_sequence):

        if delay > 0:
            time.sleep(delay)

        proc.stdin.write(cmd)
        proc.stdin.flush()

        response = read_resp_response(proc.stdout)

        print(f"[Client {client_id}] Sent: {repr(cmd.strip())}")
        print(f"[Client {client_id}] Expected: {repr(expected)}")
        print(f"[Client {client_id}] Received: {repr(response)}")

        if response != expected:
            print(f"[Client {client_id}] ❌ TEST FAILED at step {i + 1}")
            success = False
            break
        else:
            print(f"[Client {client_id}] ✅ Step {i + 1} PASSED")

    proc.stdin.close()
    proc.stdout.close()
    proc.stderr.close()
    proc.wait()

    if success:
        print(f"[Client {client_id}] ✅ ALL TESTS PASSED\n")
    else:
        print(f"[Client {client_id}] ❌ SEQUENCE FAILED\n")


# Test case format: (command_bytes, expected_response_bytes, delay_after_command)
test_sequences = [
    [
        # SET hello world PX 500
        (b"*5\r\n$3\r\nSET\r\n$5\r\nhello\r\n$5\r\nworld\r\n$2\r\nPX\r\n$3\r\n500\r\n", b"+OK\r\n", 0),
        # Immediately GET hello
        (b"*2\r\n$3\r\nGET\r\n$5\r\nhello\r\n", b"$5\r\nworld\r\n", 0),
        # Wait 1s then GET hello again (should be expired)
        (b"*2\r\n$3\r\nGET\r\n$5\r\nhello\r\n", b"$-1\r\n", 1),
    ],
    [
        # Simple SET & GET without expiry
        (b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n", b"+OK\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n", b"$3\r\nbar\r\n", 0),
    ],
    [
        # CONFIG GET dir
        (b"*3\r\n$6\r\nCONFIG\r\n$3\r\nGET\r\n$3\r\ndir\r\n",
         b"*2\r\n$3\r\ndir\r\n$11\r\n/redis-data\r\n", 0)
    ],
    [
        # CONFIG GET dbfilename
        (b"*3\r\n$6\r\nCONFIG\r\n$3\r\nGET\r\n$10\r\ndbfilename\r\n",
         b"*2\r\n$10\r\ndbfilename\r\n$7\r\nrdbfile\r\n", 0)
    ],
]

# Run each test sequence
for i, sequence in enumerate(test_sequences):
    send_sequence(i + 1, sequence)
