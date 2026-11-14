"""Pinned public DNS, TLS hostname verification, and bounded redirects/body."""

import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 2 * 1024 * 1024


def destination(url):
    u = urlsplit(url)
    if (
        u.scheme not in {"http", "https"}
        or not u.hostname
        or u.username
        or u.password
        or u.fragment
    ):
        raise ValueError("Invalid public URL")
    port = u.port or (443 if u.scheme == "https" else 80)
    if port not in {80, 443}:
        raise ValueError("Only HTTP(S) public ports allowed")
    addresses = socket.getaddrinfo(u.hostname, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Non-public destination rejected")
    return u, port, addresses[0]


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, address, secure):
        super().__init__(host, port, timeout=5)
        self.address, self.secure = address, secure

    def connect(self):
        family, socktype, proto, _, target = self.address
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(5)
        try:
            sock.connect(target)
            self.sock = (
                ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)
                if self.secure
                else sock
            )
        except BaseException:
            sock.close()
            raise


def fetch(url, max_bytes=MAX_BYTES):
    deadline = time.monotonic() + 20
    for _ in range(4):
        if time.monotonic() >= deadline:
            raise ValueError("Retrieval time limit exceeded")
        u, port, address = destination(url)
        conn = PinnedHTTP(u.hostname, port, address, u.scheme == "https")
        try:
            conn.request(
                "GET",
                (u.path or "/") + ("?" + u.query if u.query else ""),
                headers={"User-Agent": "OpportunityOS/1.0", "Accept-Encoding": "identity"},
            )
            response = conn.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Redirect missing destination")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError("Source is not reachable")
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise ValueError("Compressed responses are not supported")
            length = response.getheader("Content-Length")
            if length and int(length) > max_bytes:
                raise ValueError("Response exceeds limit")
            chunks = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("Retrieval time limit exceeded")
                conn.sock.settimeout(min(5, remaining))
                piece = response.read1(min(65536, max_bytes + 1 - len(chunks)))
                if not piece:
                    break
                chunks.extend(piece)
                if len(chunks) > max_bytes:
                    raise ValueError("Response exceeds limit")
            return bytes(chunks)
        finally:
            conn.close()
    raise ValueError("Too many redirects")
