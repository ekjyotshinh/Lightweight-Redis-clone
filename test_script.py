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
    [
        # DEL existing key
        (b"*3\r\n$3\r\nSET\r\n$3\r\nabc\r\n$3\r\nxyz\r\n", b"+OK\r\n", 0),
        (b"*2\r\n$3\r\nDEL\r\n$3\r\nabc\r\n", b":1\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$3\r\nabc\r\n", b"$-1\r\n", 0),
    ],
    [
        # DEL non-existing key
        (b"*2\r\n$3\r\nDEL\r\n$6\r\nnotkey\r\n", b":0\r\n", 0),
    ],
    [
        # PING RESP
        (b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n", 0),
    ],
    [
        # PING plain text
        (b"PING\r\n", b"+PONG\r\n", 0),
    ],
    [
        # Unknown command
        (b"*1\r\n$7\r\nNOEXIST\r\n", b"-ERR unknown command\r\n", 0),
    ],
    [
        # Overwrite value
        (b"*3\r\n$3\r\nSET\r\n$4\r\nsame\r\n$5\r\nfirst\r\n", b"+OK\r\n", 0),
        (b"*3\r\n$3\r\nSET\r\n$4\r\nsame\r\n$6\r\nsecond\r\n", b"+OK\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$4\r\nsame\r\n", b"$6\r\nsecond\r\n", 0),
    ],
    # 🔁 Overwrite value
    [
        (b"*3\r\n$3\r\nSET\r\n$3\r\none\r\n$3\r\nONE\r\n", b"+OK\r\n", 0),
        (b"*3\r\n$3\r\nSET\r\n$3\r\none\r\n$3\r\nTWO\r\n", b"+OK\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$3\r\none\r\n", b"$3\r\nTWO\r\n", 0),
    ],
    # 🧪 Multiple GETs after SETs
    [
        (b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$3\r\nval\r\n", b"+OK\r\n", 0),
        (b"*3\r\n$3\r\nSET\r\n$4\r\nname\r\n$4\r\njohn\r\n", b"+OK\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n", b"$3\r\nval\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$4\r\nname\r\n", b"$4\r\njohn\r\n", 0),
    ],
    # ⏳ Multiple keys with PX, mix of expired and not
    [
        (b"*5\r\n$3\r\nSET\r\n$5\r\nfast1\r\n$3\r\n123\r\n$2\r\nPX\r\n$3\r\n100\r\n", b"+OK\r\n", 0),
        (b"*5\r\n$3\r\nSET\r\n$5\r\nslow1\r\n$3\r\n999\r\n$2\r\nPX\r\n$4\r\n2000\r\n", b"+OK\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$5\r\nfast1\r\n", b"$3\r\n123\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$5\r\nslow1\r\n", b"$3\r\n999\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$5\r\nfast1\r\n", b"$-1\r\n", 0.15),
        (b"*2\r\n$3\r\nGET\r\n$5\r\nslow1\r\n", b"$3\r\n999\r\n", 0),
    ],
    # 🧱 Long key and long value
    [
        (b"*3\r\n$3\r\nSET\r\n$10\r\nbigkey1234\r\n$20\r\n" +
         b"x" * 20 + b"\r\n", b"+OK\r\n", 0),
        (b"*2\r\n$3\r\nGET\r\n$10\r\nbigkey1234\r\n",
         b"$20\r\n" + b"x" * 20 + b"\r\n", 0),
    ],
    # 🔎 GET non-existent key
    [
        (b"*2\r\n$3\r\nGET\r\n$7\r\nmissing\r\n", b"$-1\r\n", 0),
    ],
]

# Run each test sequence
for i, sequence in enumerate(test_sequences):
    send_sequence(i + 1, sequence)
