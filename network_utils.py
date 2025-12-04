from __future__ import annotations

import json
import socket
import threading
from typing import Any, Optional


class ConnectionClosed(Exception):
    pass
class JSONSocket:

    def __init__(self, sock: socket.socket, encoding: str = "utf-8") -> None:
        self._socket = sock
        self._encoding = encoding
        self._buffer = bytearray()
        self._send_lock = threading.Lock()

    def fileno(self) -> int:
        return self._socket.fileno()

    def settimeout(self, value: Optional[float]) -> None:
        self._socket.settimeout(value)

    def send(self, message: Any) -> None:
        payload = json.dumps(message, ensure_ascii=False).encode(self._encoding) + b"\n"
        with self._send_lock:
            self._socket.sendall(payload)

    def receive(self, timeout: Optional[float] = None) -> Any:
        previous_timeout = self._socket.gettimeout()
        try:
            if timeout is not None:
                self._socket.settimeout(timeout)

            while True:
                newline_index = self._buffer.find(b"\n")
                if newline_index != -1:
                    raw = self._buffer[:newline_index]
                    del self._buffer[:newline_index + 1]
                    if not raw:
                        continue
                    return json.loads(raw.decode(self._encoding))

                chunk = self._socket.recv(4096)
                if not chunk:
                    raise ConnectionClosed("Il socket remoto è stato chiuso")
                self._buffer.extend(chunk)
        except socket.timeout as exc:
            raise TimeoutError("Timeout durante la ricezione del messaggio") from exc
        finally:
            if timeout is not None:
                self._socket.settimeout(previous_timeout)

    def close(self) -> None:
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        finally:
            self._socket.close()

    @property
    def socket(self) -> socket.socket:
        return self._socket

__all__ = ["JSONSocket", "ConnectionClosed"]
