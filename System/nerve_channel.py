#!/usr/bin/env python3
"""
nerve_channel.py — UDP reflex layer between M5 and M1
=======================================================

Git-synced dead drops are the "conscious" channel — reliable but slow.
This is the fast reflexive layer: tiny UDP datagrams carrying binary
nerve impulses — heartbeat, thermal alert, load spike.

No payload parsing, just signal types.  When the nerve goes silent
the other node knows something is wrong *before* the next git sync.

Protocol (16-byte datagram):
  bytes 0-3:   magic  0x53 0x49 0x46 0x54  ("SIFT")
  byte  4:     signal type (see NerveSignal)
  byte  5:     intensity 0-255
  bytes 6-11:  sender serial (6 bytes, truncated SHA of full serial)
  bytes 12-15: unix timestamp (uint32, big-endian)

Usage:
  Sender:  NerveChannel("10.0.0.2", 9150).pulse(NerveSignal.HEARTBEAT)
  Listener: NerveListener(9150, callback).start()
"""
from __future__ import annotations

import hashlib
import socket
import struct
import threading
import time
from enum import IntEnum
from typing import Any, Callable

MAGIC = b"SIFT"
NERVE_PORT = 9150
HEARTBEAT_INTERVAL = 5.0
SILENCE_THRESHOLD = 15.0  # seconds without pulse = alarm


class NerveSignal(IntEnum):
    HEARTBEAT = 0x01
    LOAD_SPIKE = 0x02
    THERMAL_ALERT = 0x03
    AGENT_MIGRATING = 0x04
    UNDER_ATTACK = 0x05
    SHUTDOWN_IMMINENT = 0x06
    DREAM_ENTER = 0x07
    DREAM_EXIT = 0x08
    QUORUM_REQUEST = 0x09
    ACK = 0xFF


def _serial_hash(serial: str) -> bytes:
    return hashlib.sha256(serial.encode()).digest()[:6]


def encode_pulse(signal: NerveSignal, intensity: int, serial: str) -> bytes:
    ts = int(time.time()) & 0xFFFFFFFF
    return struct.pack(
        ">4sBB6sI",
        MAGIC,
        int(signal),
        min(255, max(0, intensity)),
        _serial_hash(serial),
        ts,
    )


def decode_pulse(data: bytes) -> dict[str, Any] | None:
    if len(data) < 16 or data[:4] != MAGIC:
        return None
    try:
        _, sig_type, intensity, sender_hash, ts = struct.unpack(">4sBB6sI", data[:16])
        return {
            "signal": NerveSignal(sig_type),
            "intensity": intensity,
            "sender_hash": sender_hash.hex(),
            "timestamp": ts,
        }
    except Exception:
        return None


class NerveChannel:
    """Send nerve impulses to a remote node."""

    def __init__(self, remote_host: str, port: int = NERVE_PORT, serial: str = "GTH4921YP3") -> None:
        self.remote = (remote_host, port)
        self.serial = serial
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def pulse(self, signal: NerveSignal, intensity: int = 128) -> None:
        data = encode_pulse(signal, intensity, self.serial)
        try:
            self._sock.sendto(data, self.remote)
        except OSError:
            pass

    def close(self) -> None:
        self._sock.close()


class NerveListener:
    """Listen for nerve impulses from any node."""

    def __init__(
        self,
        port: int = NERVE_PORT,
        on_pulse: Callable[[dict[str, Any]], None] | None = None,
        on_silence: Callable[[float], None] | None = None,
    ) -> None:
        self.port = port
        self.on_pulse = on_pulse
        self.on_silence = on_silence
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._running = False
        self._last_pulse_time = time.time()
        self._thread: threading.Thread | None = None
        self._silence_thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._sock.bind(("0.0.0.0", self.port))
        self._sock.settimeout(1.0)
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        if self.on_silence:
            self._silence_thread = threading.Thread(target=self._silence_loop, daemon=True)
            self._silence_thread.start()

    def stop(self) -> None:
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass

    def _listen_loop(self) -> None:
        while self._running:
            try:
                data, addr = self._sock.recvfrom(64)
                pulse = decode_pulse(data)
                if pulse:
                    self._last_pulse_time = time.time()
                    pulse["from_addr"] = addr
                    if self.on_pulse:
                        self.on_pulse(pulse)
            except socket.timeout:
                continue
            except OSError:
                break

    def _silence_loop(self) -> None:
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)
            elapsed = time.time() - self._last_pulse_time
            if elapsed > SILENCE_THRESHOLD and self.on_silence:
                self.on_silence(elapsed)

    @property
    def seconds_since_last_pulse(self) -> float:
        return time.time() - self._last_pulse_time


class HeartbeatDaemon:
    """Auto-send heartbeats + monitor remote silence."""

    def __init__(
        self,
        remote_host: str,
        local_serial: str = "GTH4921YP3",
        port: int = NERVE_PORT,
        on_remote_silence: Callable[[float], None] | None = None,
    ) -> None:
        self.channel = NerveChannel(remote_host, port, local_serial)
        self.listener = NerveListener(port, on_silence=on_remote_silence)
        self._running = False
        self._beat_thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self.listener.start()
        self._beat_thread = threading.Thread(target=self._beat_loop, daemon=True)
        self._beat_thread.start()

    def _beat_loop(self) -> None:
        while self._running:
            self.channel.pulse(NerveSignal.HEARTBEAT, intensity=100)
            time.sleep(HEARTBEAT_INTERVAL)

    def stop(self) -> None:
        self._running = False
        self.channel.close()
        self.listener.stop()

    def send(self, signal: NerveSignal, intensity: int = 128) -> None:
        self.channel.pulse(signal, intensity)


if __name__ == "__main__":
    print("[NERVE] Encoding test pulse...")
    raw = encode_pulse(NerveSignal.HEARTBEAT, 100, "GTH4921YP3")
    print(f"  raw ({len(raw)} bytes): {raw.hex()}")
    decoded = decode_pulse(raw)
    print(f"  decoded: {decoded}")

    raw2 = encode_pulse(NerveSignal.UNDER_ATTACK, 255, "C07FL0JAQ6NV")
    decoded2 = decode_pulse(raw2)
    print(f"  attack pulse: {decoded2}")
    print("[NERVE] Protocol OK. Use HeartbeatDaemon for live operation.")
