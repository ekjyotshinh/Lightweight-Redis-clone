# Lightweight Redis-like Key-Value Store

This project implements a simple, in-memory Redis-like key-value store in Python. It supports basic Redis commands (`PING`, `SET`, `GET`, `CONFIG GET`), with optional key expiry (`PX`), and **RDB-style persistence** using a JSON file.

---

## Features

-   In-memory key-value storage
-   Key expiration via `SET key value PX milliseconds`
-   Periodic persistence to disk (`data.rdb.json`)
-   Auto-reload persisted data on startup
-   Multi-threaded client support (concurrent connections)
-   Integration test suite using `nc` and subprocess

---

## 🛠️ How It Works

### Commands Supported

| Command                 | Description                       |
| ----------------------- | --------------------------------- |
| `PING`                  | Returns `PONG`                    |
| `SET key value`         | Stores a key-value pair           |
| `SET key value PX <ms>` | Stores key-value pair with expiry |
| `GET key`               | Retrieves value if not expired    |
| `DEL key`               | Deletes from store if present     |

---

## Running the Server

### Requirements

-   Python 3.7+
-   Linux/macOS (`nc` used in tests)

### Start the Server

```bash
python3 main.py
```
