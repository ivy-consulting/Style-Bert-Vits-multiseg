import json
import socket
import logging
from enum import IntEnum, auto
from typing import Any, Final

logger = logging.getLogger(__name__)

WORKER_PORT: Final[int] = 7861
HEADER_SIZE: Final[int] = 4
SOCKET_TIMEOUT: Final[float] = 10.0  # Timeout in seconds

class RequestType(IntEnum):
    STATUS = auto()
    QUIT_SERVER = auto()
    PYOPENJTALK = auto()

class ConnectionClosedException(Exception):
    pass

def send_data(sock: socket.socket, data: dict[str, Any]) -> None:
    try:
        sock.settimeout(SOCKET_TIMEOUT)
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        header = len(json_data).to_bytes(HEADER_SIZE, byteorder="big")
        sock.sendall(header + json_data)
    except socket.timeout:
        logger.error("Socket send timeout after %s seconds", SOCKET_TIMEOUT)
        raise ConnectionClosedException("Socket send timeout")
    except Exception as e:
        logger.error("Error sending data: %s", e)
        raise

def __receive_until(sock: socket.socket, size: int) -> bytes:
    data = b""
    try:
        sock.settimeout(SOCKET_TIMEOUT)
        while len(data) < size:
            part = sock.recv(size - len(data))
            if not part:
                logger.error("Connection closed while receiving %d bytes, got %d", size, len(data))
                raise ConnectionClosedException("Connection closed during data transfer")
            data += part
        return data
    except socket.timeout:
        logger.error("Socket receive timeout after %s seconds", SOCKET_TIMEOUT)
        raise ConnectionClosedException("Socket receive timeout")
    except Exception as e:
        logger.error("Error receiving data: %s", e)
        raise

def receive_data(sock: socket.socket) -> dict[str, Any]:
    try:
        header = __receive_until(sock, HEADER_SIZE)
        data_length = int.from_bytes(header, byteorder="big")
        if data_length <= 0:
            logger.error("Invalid data length: %d", data_length)
            raise ValueError("Invalid data length")
        body = __receive_until(sock, data_length)
        try:
            decoded_body = body.decode('utf-8')
            return json.loads(decoded_body)
        except UnicodeDecodeError as e:
            logger.error("Failed to decode response: %s, raw bytes: %r", e, body)
            # Attempt fallback decoding (e.g., Shift-JIS for Japanese)
            try:
                decoded_body = body.decode('shift-jis', errors='replace')
                logger.warning("Fallback to Shift-JIS decoding: %s", decoded_body)
                return json.loads(decoded_body)
            except Exception as fallback_e:
                logger.error("Fallback decoding failed: %s", fallback_e)
                raise ValueError(f"Invalid response encoding: {e}")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s, decoded body: %s", e, decoded_body)
            raise ValueError(f"Invalid JSON response: {e}")
    except Exception as e:
        logger.error("Error receiving data: %s", e)
        raise