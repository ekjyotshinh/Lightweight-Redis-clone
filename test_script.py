import subprocess
import threading


def send_ping(client_id):
    # Open a subprocess to run 'nc localhost 6379'
    proc = subprocess.Popen(
        ['nc', 'localhost', '6379'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True  # for text mode (str instead of bytes)
    )

    # Send PING command and close input (so nc knows we're done)
    proc.stdin.write('PING\n')
    proc.stdin.flush()
    proc.stdin.close()

    # Read response
    response = proc.stdout.read().strip()

    print(f"Client {client_id} received: {response}")

    proc.stdout.close()
    proc.stderr.close()
    proc.wait()


threads = []
num_clients = 2  # number of concurrent clients to simulate

for i in range(num_clients):
    t = threading.Thread(target=send_ping, args=(i+1,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()
