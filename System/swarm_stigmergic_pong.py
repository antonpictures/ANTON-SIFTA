#!/usr/bin/env python3
"""Two-swarm stigmergic Pong simulation.

Each paddle is controlled only by the average of binary votes from its own
swimmers. Swimmers estimate the ball's arrival locally, deposit into a shared
one-dimensional pheromone field, then read the field centroid before voting.
The field evaporates and diffuses every step. No swimmer moves a paddle
directly and there is no hidden perfect-tracking controller.

The rolling vote digest makes ballot membership and sequence auditable inside
one run. It is a local hash-chain receipt, not a signature or cryptocurrency.

R1625 upgrade (triple-IDE): optional GAME_STGM economy (vote stake / save pay)
and optional LLM microvotes (think=false) for a sample of swimmers — slower, opt-in.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Optional

from System.swimmer_pheromone_identity import SwimmerIdentity, verify_trace


TRUTH_LABEL = "STIGMERGIC_CARPENTER_PONG_V3"
FIELD_BINS = 52
PADDLE_HALF_HEIGHT = 0.075
PADDLE_SPEED = 0.62
PADDLE_LEFT_X = 0.075
PADDLE_RIGHT_X = 0.925
BALL_RADIUS = 0.012
BALL_BASE_SPEED = 0.46

Side = Literal["left", "right"]


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def reflect_unit(value: float) -> float:
    """Reflect an unbounded vertical coordinate into the [0, 1] court."""
    folded = float(value) % 2.0
    return folded if folded <= 1.0 else 2.0 - folded


def normalized_entropy(values: Iterable[float]) -> float:
    positive = [max(0.0, float(v)) for v in values]
    total = sum(positive)
    if total <= 1e-12 or len(positive) <= 1:
        return 0.0
    entropy = 0.0
    for value in positive:
        if value <= 0.0:
            continue
        probability = value / total
        entropy -= probability * math.log(probability)
    return clamp(entropy / math.log(len(positive)), 0.0, 1.0)


@dataclass(frozen=True)
class Swimmer:
    uid: str
    public_key_hex: str
    acuity: float
    anticipation: float
    field_follow: float
    bias: float
    noise: float


@dataclass
class Ball:
    x: float = 0.5
    y: float = 0.5
    vx: float = BALL_BASE_SPEED
    vy: float = 0.12


@dataclass
class SwarmState:
    side: Side
    swimmers: list[Swimmer]
    rng: random.Random = field(repr=False)
    pheromone: list[float] = field(default_factory=lambda: [0.0] * FIELD_BINS)
    paddle_y: float = 0.5
    paddle_velocity: float = 0.0
    vote_average: float = 0.0
    agreement: float = 0.0
    field_centroid: float = 0.5
    field_entropy: float = 0.0
    up_votes: int = 0
    down_votes: int = 0
    neutral_votes: int = 0
    last_votes: list[int] = field(default_factory=list)
    last_targets: list[float] = field(default_factory=list)
    vote_digest: str = "0" * 16
    signal_bias: float = 0.0
    signal_age: float = 0.0
    signal_interval: float = 0.08
    chorus_target: float = 0.5
    chorus_confidence: float = 0.0
    chorus_advice_age: float = 1e9
    chorus_model: str = ""

    @property
    def field_mass(self) -> float:
        return round(sum(self.pheromone), 6)


class StigmergicPongSimulation:
    """Deterministic game engine used by the Qt surface and headless tests."""

    def __init__(
        self,
        *,
        seed: int = 1625,
        swimmers_per_side: int = 64,
        stgm_economy: bool = True,
        llm_microvote: bool = False,
        llm_sample: int = 4,
        llm_every_ticks: int = 90,
        llm_model: str = "",
    ) -> None:
        self.seed = int(seed)
        self.swimmers_per_side = max(8, min(160, int(swimmers_per_side)))
        self.ball_rng = random.Random(self.seed ^ 0xB411)
        self._identities: dict[str, SwimmerIdentity] = {}
        self.tick = 0
        self.round_number = 1
        self.left_score = 0
        self.right_score = 0
        self.rally_hits = 0
        self.longest_rally = 0
        self.last_event: dict[str, Any] = {}
        self.ball = Ball()
        self.ball_trail: list[tuple[float, float]] = []
        self.stgm_economy = bool(stgm_economy)
        self.llm_microvote = bool(llm_microvote)
        self.llm_sample = max(0, min(16, int(llm_sample)))
        self.llm_every_ticks = max(15, int(llm_every_ticks))
        self.llm_model = str(llm_model or "")
        self.llm_overrides: dict[str, int] = {}
        self.llm_last_report: dict[str, Any] = {}
        self.crypto_checkpoint_interval = 30
        self.verified_ballots = 0
        self.invalid_ballots = 0
        self.crypto_digest = "0" * 16
        self.last_signed_ballots: list[dict[str, Any]] = []
        self.chorus_calls = 0
        self.chorus_pressure_stgm_equiv = 0.0
        self.economy = None
        if self.stgm_economy:
            try:
                from System.swarm_carpenter_pong_stgm import PongGameStgmEconomy

                self.economy = PongGameStgmEconomy(enabled=True)
            except Exception:
                self.economy = None
                self.stgm_economy = False
        self.left = self._make_swarm("left", self.seed + 101)
        self.right = self._make_swarm("right", self.seed + 202)
        self._init_economy_wallets()
        self.reset_ball(direction=1)

    def _init_economy_wallets(self) -> None:
        if self.economy is None:
            return
        self.economy.reset_for_swimmers(self.all_swimmer_ids)

    def _make_swarm(self, side: Side, side_seed: int) -> SwarmState:
        rng = random.Random(side_seed)
        swimmers: list[Swimmer] = []
        for index in range(self.swimmers_per_side):
            identity = SwimmerIdentity(f"carpenter-pong:{self.seed}:{side}:{index}")
            uid = identity.id
            self._identities[uid] = identity
            swimmers.append(
                Swimmer(
                    uid=uid,
                    public_key_hex=identity.public_key.hex(),
                    acuity=rng.uniform(0.65, 1.0),
                    anticipation=rng.uniform(0.70, 1.08),
                    field_follow=rng.uniform(0.25, 0.62),
                    bias=rng.uniform(-0.025, 0.025),
                    noise=rng.uniform(0.008, 0.038),
                )
            )
        return SwarmState(side=side, swimmers=swimmers, rng=rng)

    @property
    def all_swimmer_ids(self) -> list[str]:
        return [s.uid for s in self.left.swimmers + self.right.swimmers]

    def reset_match(self, *, seed: int | None = None, swimmers_per_side: int | None = None) -> None:
        if seed is not None:
            self.seed = int(seed)
        if swimmers_per_side is not None:
            self.swimmers_per_side = max(8, min(160, int(swimmers_per_side)))
        self.ball_rng = random.Random(self.seed ^ 0xB411)
        self._identities = {}
        self.tick = 0
        self.round_number = 1
        self.left_score = 0
        self.right_score = 0
        self.rally_hits = 0
        self.longest_rally = 0
        self.last_event = {}
        self.ball_trail = []
        self.llm_overrides = {}
        self.llm_last_report = {}
        self.verified_ballots = 0
        self.invalid_ballots = 0
        self.crypto_digest = "0" * 16
        self.last_signed_ballots = []
        self.chorus_calls = 0
        self.chorus_pressure_stgm_equiv = 0.0
        self.left = self._make_swarm("left", self.seed + 101)
        self.right = self._make_swarm("right", self.seed + 202)
        self._init_economy_wallets()
        self.reset_ball(direction=1)

    def reset_ball(self, *, direction: int | None = None) -> None:
        sign = int(direction or self.ball_rng.choice((-1, 1)))
        sign = -1 if sign < 0 else 1
        angle = self.ball_rng.uniform(-0.48, 0.48)
        self.ball = Ball(
            x=0.5,
            y=self.ball_rng.uniform(0.30, 0.70),
            vx=sign * BALL_BASE_SPEED * math.cos(angle),
            vy=BALL_BASE_SPEED * math.sin(angle),
        )
        self.ball_trail = [(self.ball.x, self.ball.y)]
        self.rally_hits = 0

    @staticmethod
    def aggregate_votes(votes: Iterable[int]) -> float:
        ballot = [max(-1, min(1, int(v))) for v in votes]
        return sum(ballot) / len(ballot) if ballot else 0.0

    @staticmethod
    def apply_vote_average(swarm: SwarmState, vote_average: float, dt: float) -> None:
        """The only paddle actuator: Carpenter-style aggregate of local votes."""
        swarm.vote_average = clamp(vote_average, -1.0, 1.0)
        swarm.paddle_velocity = swarm.vote_average * PADDLE_SPEED
        swarm.paddle_y = clamp(
            swarm.paddle_y + swarm.paddle_velocity * max(0.0, float(dt)),
            PADDLE_HALF_HEIGHT,
            1.0 - PADDLE_HALF_HEIGHT,
        )

    def _evaporate_and_diffuse(self, swarm: SwarmState) -> None:
        old = swarm.pheromone
        updated: list[float] = []
        for index, value in enumerate(old):
            left = old[index - 1] if index > 0 else value
            right = old[index + 1] if index + 1 < len(old) else value
            diffused = value + 0.085 * (left + right - 2.0 * value)
            updated.append(max(0.0, diffused * 0.958))
        swarm.pheromone = updated

    def _time_to_paddle(self, side: Side) -> tuple[float, bool]:
        plane = PADDLE_LEFT_X if side == "left" else PADDLE_RIGHT_X
        velocity_toward = self.ball.vx < 0.0 if side == "left" else self.ball.vx > 0.0
        if velocity_toward and abs(self.ball.vx) > 1e-9:
            return max(0.0, (plane - self.ball.x) / self.ball.vx), True
        return 0.22, False

    def _estimate_target(self, swarm: SwarmState, swimmer: Swimmer) -> float:
        time_to_plane, approaching = self._time_to_paddle(swarm.side)
        if not approaching:
            time_to_plane += 0.22 * swimmer.anticipation
        predicted = reflect_unit(
            self.ball.y + self.ball.vy * time_to_plane * swimmer.anticipation
        )
        noise_scale = swimmer.noise * (1.0 if approaching else 1.55)
        noisy = predicted + swimmer.bias + swarm.rng.gauss(0.0, noise_scale)
        return clamp(noisy + swarm.signal_bias, 0.02, 0.98)

    @staticmethod
    def _field_centroid(pheromone: list[float]) -> float:
        mass = sum(pheromone)
        if mass <= 1e-12:
            return 0.5
        return sum(((i + 0.5) / len(pheromone)) * value for i, value in enumerate(pheromone)) / mass

    def _update_swarm(self, swarm: SwarmState, dt: float) -> None:
        self._evaporate_and_diffuse(swarm)
        swarm.chorus_advice_age += dt
        swarm.signal_age += dt
        if swarm.signal_age >= swarm.signal_interval:
            swarm.signal_age = 0.0
            swarm.signal_interval = swarm.rng.uniform(0.055, 0.135)
            ball_speed = math.hypot(self.ball.vx, self.ball.vy)
            shared_noise = swarm.rng.gauss(0.0, 0.014 + 0.048 * ball_speed)
            swarm.signal_bias = clamp(
                swarm.signal_bias * 0.58 + shared_noise,
                -0.115,
                0.115,
            )
        targets: list[float] = []
        for swimmer in swarm.swimmers:
            target = self._estimate_target(swarm, swimmer)
            targets.append(target)
            index = min(FIELD_BINS - 1, max(0, int(target * FIELD_BINS)))
            deposit = 0.030 + 0.026 * swimmer.acuity
            swarm.pheromone[index] = min(8.0, swarm.pheromone[index] + deposit)

        centroid = self._field_centroid(swarm.pheromone)
        votes: list[int] = []
        dead_zone = 0.012
        for swimmer, target in zip(swarm.swimmers, targets):
            local_target = (
                target * (1.0 - swimmer.field_follow)
                + centroid * swimmer.field_follow
            )
            if swarm.chorus_confidence > 0.0 and swarm.chorus_advice_age <= 12.0:
                cortex_mix = min(
                    0.55,
                    0.12 + 0.43 * swarm.chorus_confidence * swimmer.acuity,
                )
                local_target = (
                    local_target * (1.0 - cortex_mix)
                    + swarm.chorus_target * cortex_mix
                )
            error = local_target - swarm.paddle_y
            vote = 1 if error > dead_zone else -1 if error < -dead_zone else 0
            # Optional LLM override (cached sample)
            if self.llm_microvote and swimmer.uid in self.llm_overrides:
                vote = int(self.llm_overrides[swimmer.uid])
            # GAME_STGM settles at signed decision checkpoints, not every
            # rendered frame. Broke swimmers remain neutral between epochs.
            if self.economy is not None and vote != 0:
                if not self.economy.can_vote(swimmer.uid):
                    vote = 0
                elif self.tick == 1 or self.tick % self.crypto_checkpoint_interval == 0:
                    if not self.economy.charge_vote(
                        swimmer.uid, vote=vote, tick=self.tick
                    ):
                        vote = 0
            votes.append(vote)

        swarm.last_targets = targets
        swarm.last_votes = votes
        swarm.up_votes = sum(1 for vote in votes if vote < 0)
        swarm.down_votes = sum(1 for vote in votes if vote > 0)
        swarm.neutral_votes = len(votes) - swarm.up_votes - swarm.down_votes
        swarm.field_centroid = centroid
        swarm.field_entropy = normalized_entropy(swarm.pheromone)
        swarm.agreement = (
            max(swarm.up_votes, swarm.down_votes, swarm.neutral_votes) / len(votes)
            if votes
            else 0.0
        )
        vote_average = self.aggregate_votes(votes)
        self.apply_vote_average(swarm, vote_average, dt)

        ballot = "|".join(
            f"{swimmer.uid}:{vote}" for swimmer, vote in zip(swarm.swimmers, votes)
        )
        swarm.vote_digest = hashlib.sha256(
            f"{swarm.vote_digest}|{self.tick}|{swarm.side}|{ballot}".encode("ascii")
        ).hexdigest()[:16]

    def council_observations(self) -> dict[str, list[dict[str, Any]]]:
        """Return one compact observation from every swimmer for a batch call."""
        result: dict[str, list[dict[str, Any]]] = {"left": [], "right": []}
        for swarm in (self.left, self.right):
            for index, swimmer in enumerate(swarm.swimmers):
                target = swarm.last_targets[index] if index < len(swarm.last_targets) else self.ball.y
                result[swarm.side].append(
                    {
                        "id": swimmer.uid,
                        "target": round(target, 4),
                        "field_follow": round(swimmer.field_follow, 3),
                        "vote": swarm.last_votes[index] if index < len(swarm.last_votes) else 0,
                    }
                )
        return result

    def apply_chorus_advice(
        self,
        *,
        left_target: float,
        left_confidence: float,
        right_target: float,
        right_confidence: float,
        model: str,
        estimated_prompt_tokens: int = 0,
    ) -> None:
        for swarm, target, confidence in (
            (self.left, left_target, left_confidence),
            (self.right, right_target, right_confidence),
        ):
            swarm.chorus_target = clamp(target, 0.02, 0.98)
            swarm.chorus_confidence = clamp(confidence, 0.0, 1.0)
            swarm.chorus_advice_age = 0.0
            swarm.chorus_model = str(model)
        self.chorus_calls += 1
        # Local pressure telemetry only; never reaches the canonical wallet.
        self.chorus_pressure_stgm_equiv += max(0, int(estimated_prompt_tokens)) * 0.00000001

    def _sign_ballot_checkpoint(self) -> None:
        rows: list[dict[str, Any]] = []
        verified = invalid = 0
        timestamp = 1_700_000_000.0 + self.tick / 60.0
        for swarm in (self.left, self.right):
            for swimmer, vote in zip(swarm.swimmers, swarm.last_votes):
                payload = json.dumps(
                    {
                        "domain": "SIFTA-CARPENTER-PONG-BALLOT-V1",
                        "tick": self.tick,
                        "side": swarm.side,
                        "vote": int(vote),
                        "field_centroid": round(swarm.field_centroid, 6),
                        "chorus_target": round(swarm.chorus_target, 6),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                trace = self._identities[swimmer.uid].deposit(
                    "carpenter-pong/ballot",
                    payload,
                    ts=timestamp,
                )
                valid = verify_trace(trace)
                verified += int(valid)
                invalid += int(not valid)
                rows.append(
                    {
                        **trace.to_dict(),
                        "verified": valid,
                        "vote": int(vote),
                        "side": swarm.side,
                    }
                )
        self.last_signed_ballots = rows
        self.verified_ballots = verified
        self.invalid_ballots = invalid
        self.crypto_digest = hashlib.sha256(
            "|".join(row["signature_hex"] for row in rows).encode("ascii")
        ).hexdigest()[:16]

    def _paddle_hit(self, swarm: SwarmState) -> bool:
        return abs(self.ball.y - swarm.paddle_y) <= PADDLE_HALF_HEIGHT + BALL_RADIUS

    def _bounce_from_paddle(self, swarm: SwarmState, direction: int) -> None:
        offset = clamp(
            (self.ball.y - swarm.paddle_y) / PADDLE_HALF_HEIGHT,
            -1.0,
            1.0,
        )
        speed = min(
            0.90,
            max(BALL_BASE_SPEED, math.hypot(self.ball.vx, self.ball.vy) * 1.022),
        )
        vertical = clamp(
            self.ball.vy * 0.34
            + offset * speed * 0.76
            + swarm.paddle_velocity * 0.16,
            -speed * 0.82,
            speed * 0.82,
        )
        horizontal = math.sqrt(max(0.11, speed * speed - vertical * vertical))
        self.ball.vx = direction * horizontal
        self.ball.vy = vertical
        self.rally_hits += 1
        self.longest_rally = max(self.longest_rally, self.rally_hits)
        # GAME_STGM: pay swimmers whose vote pointed toward the ball
        if self.economy is not None and swarm.last_votes:
            correct: list[str] = []
            for swimmer, vote in zip(swarm.swimmers, swarm.last_votes):
                # ball below paddle (higher y) needs +1; ball above needs -1
                if vote == 0:
                    continue
                want = 1 if self.ball.y > swarm.paddle_y else -1 if self.ball.y < swarm.paddle_y else 0
                if want != 0 and vote == want:
                    correct.append(swimmer.uid)
            self.economy.reward_save(correct, side=swarm.side, tick=self.tick)

    def _goal(self, scorer: Side) -> dict[str, Any]:
        if scorer == "left":
            self.left_score += 1
            next_direction = 1
            loser = self.right
        else:
            self.right_score += 1
            next_direction = -1
            loser = self.left
        # tax wrong voters on the side that missed
        if self.economy is not None and loser.last_votes:
            wrong: list[str] = []
            for swimmer, vote in zip(loser.swimmers, loser.last_votes):
                want = 1 if self.ball.y > loser.paddle_y else -1 if self.ball.y < loser.paddle_y else 0
                if vote != 0 and want != 0 and vote != want:
                    wrong.append(swimmer.uid)
            self.economy.tax_miss(wrong, side=loser.side, tick=self.tick)
        event = {
            "event": "goal",
            "scorer": scorer,
            "score": [self.left_score, self.right_score],
            "rally_hits": self.rally_hits,
            "tick": self.tick,
            "left_vote_digest": self.left.vote_digest,
            "right_vote_digest": self.right.vote_digest,
            "economy": self.economy.snapshot() if self.economy else None,
        }
        self.last_event = event
        self.round_number += 1
        self.reset_ball(direction=next_direction)
        return event

    def _maybe_llm_sample(self) -> None:
        """Sample a few swimmers; they ask local LLM UP/DOWN (think=false). Slow; opt-in."""
        if not self.llm_microvote or self.llm_sample <= 0:
            return
        if self.tick % self.llm_every_ticks != 0:
            return
        try:
            from System.swarm_carpenter_pong_stgm import ask_llm_up_down
        except Exception as exc:
            self.llm_last_report = {"ok": False, "reason": str(exc)}
            return
        picked: list[tuple[str, Side, float]] = []
        for swarm in (self.left, self.right):
            sample = list(swarm.swimmers)
            swarm.rng.shuffle(sample)
            for sw in sample[: max(1, self.llm_sample // 2)]:
                picked.append((sw.uid, swarm.side, swarm.paddle_y))
        results = []
        for uid, side, paddle_y in picked:
            row = ask_llm_up_down(
                ball_y=self.ball.y,
                paddle_y=paddle_y,
                side=side,
                model=self.llm_model,
                timeout_s=1.8,
            )
            if row.get("ok") and int(row.get("vote") or 0) != 0:
                self.llm_overrides[uid] = int(row["vote"])
            results.append({"uid": uid[:8], **{k: row.get(k) for k in ("ok", "vote", "raw", "reason", "model")}})
        self.llm_last_report = {
            "tick": self.tick,
            "n": len(results),
            "overrides": len(self.llm_overrides),
            "samples": results[:8],
        }

    def step(self, dt: float = 1.0 / 60.0) -> list[dict[str, Any]]:
        dt = clamp(dt, 1.0 / 600.0, 0.08)
        self.tick += 1
        self._update_swarm(self.left, dt)
        self._update_swarm(self.right, dt)
        if self.tick == 1 or self.tick % self.crypto_checkpoint_interval == 0:
            self._sign_ballot_checkpoint()

        previous_x = self.ball.x
        self.ball.x += self.ball.vx * dt
        self.ball.y += self.ball.vy * dt

        if self.ball.y <= BALL_RADIUS:
            self.ball.y = BALL_RADIUS
            self.ball.vy = abs(self.ball.vy)
        elif self.ball.y >= 1.0 - BALL_RADIUS:
            self.ball.y = 1.0 - BALL_RADIUS
            self.ball.vy = -abs(self.ball.vy)

        events: list[dict[str, Any]] = []
        if self.ball.vx < 0.0 and previous_x >= PADDLE_LEFT_X > self.ball.x:
            if self._paddle_hit(self.left):
                self.ball.x = PADDLE_LEFT_X + BALL_RADIUS
                self._bounce_from_paddle(self.left, 1)
            else:
                events.append(self._goal("right"))
        elif self.ball.vx > 0.0 and previous_x <= PADDLE_RIGHT_X < self.ball.x:
            if self._paddle_hit(self.right):
                self.ball.x = PADDLE_RIGHT_X - BALL_RADIUS
                self._bounce_from_paddle(self.right, -1)
            else:
                events.append(self._goal("left"))

        self.ball_trail.append((self.ball.x, self.ball.y))
        self.ball_trail = self.ball_trail[-22:]
        return events

    def snapshot(self) -> dict[str, Any]:
        def swarm_row(swarm: SwarmState) -> dict[str, Any]:
            return {
                "side": swarm.side,
                "swimmers": len(swarm.swimmers),
                "paddle_y": round(swarm.paddle_y, 6),
                "vote_average": round(swarm.vote_average, 6),
                "agreement": round(swarm.agreement, 6),
                "field_centroid": round(swarm.field_centroid, 6),
                "field_entropy": round(swarm.field_entropy, 6),
                "field_mass": swarm.field_mass,
                "votes": {
                    "up": swarm.up_votes,
                    "down": swarm.down_votes,
                    "neutral": swarm.neutral_votes,
                },
                "vote_digest": swarm.vote_digest,
                "chorus": {
                    "target_y": round(swarm.chorus_target, 6),
                    "confidence": round(swarm.chorus_confidence, 6),
                    "age_s": round(swarm.chorus_advice_age, 3),
                    "model": swarm.chorus_model,
                },
            }

        return {
            "truth_label": TRUTH_LABEL,
            "seed": self.seed,
            "tick": self.tick,
            "round": self.round_number,
            "score": [self.left_score, self.right_score],
            "rally_hits": self.rally_hits,
            "longest_rally": self.longest_rally,
            "ball": {
                "x": round(self.ball.x, 6),
                "y": round(self.ball.y, 6),
                "vx": round(self.ball.vx, 6),
                "vy": round(self.ball.vy, 6),
            },
            "left": swarm_row(self.left),
            "right": swarm_row(self.right),
            "identity_unique": len(set(self.all_swimmer_ids)) == len(self.all_swimmer_ids),
            "crypto": {
                "signature_algorithm": "Ed25519",
                "verified_ballots": self.verified_ballots,
                "invalid_ballots": self.invalid_ballots,
                "checkpoint_digest": self.crypto_digest,
                "checkpoint_interval_ticks": self.crypto_checkpoint_interval,
            },
            "digest_note": "rolling vote digest is not a signature; checkpoint ballots are separately Ed25519 signed",
            "stgm_economy": self.economy.snapshot() if self.economy else {"enabled": False},
            "llm_microvote": {
                "enabled": self.llm_microvote,
                "mode": "whole_swarm_batched_council",
                "sample": self.swimmers_per_side * 2,
                "every_ticks": self.llm_every_ticks,
                "last": self.llm_last_report,
                "calls": self.chorus_calls,
                "pressure_stgm_equiv": round(self.chorus_pressure_stgm_equiv, 9),
                "economy_effect": "telemetry_only_no_mint_no_spend",
            },
        }


__all__ = [
    "BALL_RADIUS",
    "FIELD_BINS",
    "PADDLE_HALF_HEIGHT",
    "PADDLE_LEFT_X",
    "PADDLE_RIGHT_X",
    "PADDLE_SPEED",
    "StigmergicPongSimulation",
    "SwarmState",
    "Swimmer",
    "clamp",
    "normalized_entropy",
    "reflect_unit",
]
