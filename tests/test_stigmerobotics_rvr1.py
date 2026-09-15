import socket
import struct
import threading
import time

import pytest

from System.stigmerobotics_rvr1 import (
    CAPABILITIES,
    CONTROL,
    HELLO,
    LIDAR,
    Packet,
    RoverClient,
    SESSION_OPEN,
    VELOCITY,
    Observations,
    decode,
    encode,
    sequence_is_newer,
    velocity_payload,
)


KEY = b"loopback-test-key"


def capabilities(challenge=0x1020304050607080):
    return struct.pack("<BBHhhHBBQ", 1, 1, 4210, 1000, 1667, 1000, 24, 0x07, challenge)


def control(sequence=0, status=0, state=0, remaining=0):
    return struct.pack("<HBBHBx", sequence, status, state, remaining, 1)


class FirmwareSimulator:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.address = self.sock.getsockname()
        self.commands = []
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self._stop.set()
        self.sock.close()
        self.thread.join(timeout=2)

    def _run(self):
        self.sock.settimeout(0.05)
        while not self._stop.is_set():
            try:
                data, peer = self.sock.recvfrom(256)
            except (socket.timeout, OSError):
                continue
            packet = decode(data, KEY)
            if packet.kind == HELLO:
                self.sock.sendto(encode(Packet(CAPABILITIES, packet.session, capabilities()), KEY), peer)
            elif packet.kind == SESSION_OPEN:
                assert packet.payload == struct.pack("<Q", 0x1020304050607080)
                self.sock.sendto(encode(Packet(CONTROL, packet.session, control()), KEY), peer)
            elif packet.kind == VELOCITY:
                linear, angular, timeout_ms, sequence = struct.unpack("<hhHH", packet.payload)
                self.commands.append((linear, angular, timeout_ms, sequence))
                self.sock.sendto(encode(Packet(CONTROL, packet.session,
                                               control(sequence, 1, 1, timeout_ms)), KEY), peer)


def test_wire_round_trip_and_mutations():
    packet = Packet(VELOCITY, 7, velocity_payload(200, -10, 250, 3))
    encoded = encode(packet, KEY)
    assert decode(encoded, KEY) == packet
    with pytest.raises(ValueError, match="authentication"):
        decode(encoded[:-1] + bytes([encoded[-1] ^ 1]), KEY)
    damaged = bytearray(encoded)
    damaged[12] ^= 1
    with pytest.raises(ValueError, match="authentication|CRC"):
        decode(bytes(damaged), KEY)
    with pytest.raises(ValueError):
        encode(packet, b"")
    with pytest.raises(ValueError):
        velocity_payload(0, 0, 0, 1)


def test_sequence_wrap_is_strict():
    assert sequence_is_newer(0, 65535)
    assert sequence_is_newer(2, 1)
    assert not sequence_is_newer(1, 2)
    assert not sequence_is_newer(10, 10)


def test_lidar_requires_ordered_complete_scan():
    eye = Observations()
    first = Packet(LIDAR, 9, struct.pack("<HBBBBhHhh", 4, 1, 0, 1, 0, 0, 4, 100, 200))
    last = Packet(LIDAR, 9, struct.pack("<HBBBBhHhh", 4, 2, 1, 1, 0, 0, 4, 300, 400))
    assert eye.ingest(last, 1.0) is None
    assert eye.ingest(first, 1.1) is None
    result = eye.ingest(last, 1.2)
    assert result["points_mm"] == [(100, 200), (300, 400)]
    assert result["coverage"] == "front_180_degrees"
    assert eye.ingest(first, 1.3) is None


def test_lidar_rejects_stale_or_oversized_chunk():
    eye = Observations()
    stale = Packet(LIDAR, 1, struct.pack("<HBBBBhHhh", 1, 3, 0, 1, 0, 0, 1001, 1, 2))
    assert eye.ingest(stale, 1.0) is None
    oversized = Packet(LIDAR, 1, struct.pack("<HBBBBhH", 1, 3, 0, 0, 0, 0, 0))
    with pytest.raises(ValueError):
        eye.ingest(oversized, 1.1)


def test_obstacle_gate_requires_fresh_front_clearance():
    eye = Observations()
    clear = Packet(LIDAR, 1, struct.pack(
        "<HBBBBhHhhhh", 2, 3, 0, 2, 0, 0, 0, 450, 0, 500, 300))
    assert eye.ingest(clear, 10.0) is not None
    assert eye.obstacle_clear(200, now=10.5)
    assert not eye.obstacle_clear(200, now=11.1)
    assert not eye.obstacle_clear(-200, now=10.5)
    blocked = Packet(LIDAR, 1, struct.pack(
        "<HBBBBhHhhhh", 3, 3, 0, 2, 0, 0, 0, 250, 0, 500, 300))
    assert eye.ingest(blocked, 12.0) is not None
    assert not eye.obstacle_clear(200, now=12.1)
    assert eye.obstacle_clear(0, now=12.1)


def test_client_handshake_and_finite_velocity_command():
    firmware = FirmwareSimulator()
    firmware.start()
    client = RoverClient("127.0.0.1", KEY, port=firmware.address[1])
    try:
        opened = client.open()
        assert opened["status"] == "accepted"
        sent = client.velocity(200, -10, timeout_ms=250)
        assert sent["status"] == "sent"
        deadline = time.monotonic() + 1
        while not firmware.commands and time.monotonic() < deadline:
            time.sleep(0.01)
        assert firmware.commands == [(200, -10, 250, sent["sequence"])]
        with pytest.raises(ValueError):
            client.velocity(1001, 0)
    finally:
        client.close()
        firmware.close()


def test_client_rejects_non_ipv4_and_unopened_velocity():
    with pytest.raises(ValueError):
        RoverClient("example.test", KEY)
    client = RoverClient("127.0.0.1", KEY, port=4210)
    try:
        with pytest.raises(RuntimeError, match="not open"):
            client.velocity(0, 0)
    finally:
        client.close()
