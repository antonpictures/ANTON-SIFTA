#!/usr/bin/env python3
"""sifta.core.transport — in-process / localhost IPC / remote node (DB5).

One interface so bridges stop hardcoding host:port. Continuous pub/sub
shaped as publish/subscribe of dict envelopes. Only transports needed now.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class Transport(ABC):
    @abstractmethod
    def publish(self, topic: str, payload: dict[str, Any]) -> str:
        ...

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[dict[str, Any]], None]) -> None:
        ...

    def close(self) -> None:
        return None


class InProcessTransport(Transport):
    """Same-process deposit tray (default)."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._history: list[dict[str, Any]] = []

    def publish(self, topic: str, payload: dict[str, Any]) -> str:
        msg_id = uuid.uuid4().hex[:12]
        env = {
            "msg_id": msg_id,
            "topic": topic,
            "ts": time.time(),
            "payload": payload,
        }
        self._history.append(env)
        for h in list(self._subs.get(topic, [])):
            try:
                h(env)
            except Exception:
                pass
        # also wildcard
        for h in list(self._subs.get("*", [])):
            try:
                h(env)
            except Exception:
                pass
        return msg_id

    def subscribe(self, topic: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._subs.setdefault(topic, []).append(handler)


class LocalhostIPCTransport(Transport):
    """UDP localhost pub/sub (best-effort, no hard host hardcoding at call sites)."""

    def __init__(self, port: int = 0, bind_host: str = "127.0.0.1"):
        self._bind_host = bind_host
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((bind_host, int(port)))
        self.port = int(self._sock.getsockname()[1])
        self._subs: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def publish(self, topic: str, payload: dict[str, Any]) -> str:
        msg_id = uuid.uuid4().hex[:12]
        env = {
            "msg_id": msg_id,
            "topic": topic,
            "ts": time.time(),
            "payload": payload,
        }
        data = json.dumps(env, default=str).encode("utf-8")
        # broadcast to self port (loopback peer group uses same port family)
        self._sock.sendto(data, (self._bind_host, self.port))
        return msg_id

    def subscribe(self, topic: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._subs.setdefault(topic, []).append(handler)

    def _recv_loop(self) -> None:
        self._sock.settimeout(0.3)
        while self._running:
            try:
                data, _addr = self._sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                env = json.loads(data.decode("utf-8", errors="replace"))
            except Exception:
                continue
            topic = str(env.get("topic") or "")
            for h in list(self._subs.get(topic, [])) + list(self._subs.get("*", [])):
                try:
                    h(env)
                except Exception:
                    pass

    def close(self) -> None:
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass


class RemoteNodeTransport(Transport):
    """
    Thin HTTP-shaped remote publish (fire-and-forget POST JSON).
    Endpoint is configured once; call sites only pass topic + payload.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._subs: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def publish(self, topic: str, payload: dict[str, Any]) -> str:
        import urllib.request

        msg_id = uuid.uuid4().hex[:12]
        env = {
            "msg_id": msg_id,
            "topic": topic,
            "ts": time.time(),
            "payload": payload,
        }
        data = json.dumps(env, default=str).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/stream/publish",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=2.0)
        except Exception:
            pass
        for h in list(self._subs.get(topic, [])) + list(self._subs.get("*", [])):
            try:
                h(env)
            except Exception:
                pass
        return msg_id

    def subscribe(self, topic: str, handler: Callable[[dict[str, Any]], None]) -> None:
        # Local mirror only — full remote subscribe needs a daemon poller.
        self._subs.setdefault(topic, []).append(handler)


def make_transport(kind: str = "inprocess", **kwargs: Any) -> Transport:
    kind = (kind or "inprocess").lower()
    if kind in {"inprocess", "in_process", "local"}:
        return InProcessTransport()
    if kind in {"localhost", "ipc", "udp"}:
        return LocalhostIPCTransport(**kwargs)
    if kind in {"remote", "http"}:
        return RemoteNodeTransport(base_url=kwargs.get("base_url") or "http://127.0.0.1:8765")
    raise ValueError(f"unknown transport kind: {kind}")
