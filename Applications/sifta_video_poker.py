#!/usr/bin/env python3
"""
sifta_video_poker.py - Stigmergic Video Poker
═══════════════════════════════════════════════════════════════════════════════
A native Python port of the STGM Video Poker. 
ALICE plays with you. 52 chaotic agents determine the deck shuffle.
"""
from __future__ import annotations

import sys
import math
import random
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont

_APP_DIR = Path(__file__).resolve().parent
_REPO = _APP_DIR.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.sifta_base_widget import SiftaBaseWidget

# ── Poker Evaluation Logic ──────────────────────────────────────────────────

SUITS = ['♠', '♥', '♦', '♣']
VALUES = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

def val_to_int(v: str) -> int:
    if v == 'J': return 11
    if v == 'Q': return 12
    if v == 'K': return 13
    if v == 'A': return 14
    return int(v)

class Card:
    def __init__(self, suit: str, value: str):
        self.suit = suit
        self.value = value
    def __repr__(self):
        return f"{self.value}{self.suit}"
    def is_red(self):
        return self.suit in ('♥', '♦')

PAY_TABLE = {
    'royal flush': 250,
    'straight flush': 50,
    'four of a kind': 25,
    'full house': 9,
    'flush': 6,
    'straight': 4,
    'three of a kind': 3,
    'two pair': 2,
    'jacks or better': 1,
    'NO WIN': 0
}

def evaluate_hand(hand: List[Card]) -> str:
    if len(hand) != 5:
        return 'NO WIN'
    
    suits = [c.suit for c in hand]
    vals = [val_to_int(c.value) for c in hand]
    
    is_flush = len(set(suits)) == 1
    
    vals.sort()
    is_straight = False
    # Check normal straight
    if vals == [vals[0]+i for i in range(5)]:
        is_straight = True
    # Check Ace-low straight (A, 2, 3, 4, 5)
    elif vals == [2, 3, 4, 5, 14]:
        is_straight = True
        vals = [1, 2, 3, 4, 5] # Normalise for Royal check

    counts = Counter(vals)
    freqs = sorted(counts.values(), reverse=True)
    
    if is_flush and is_straight:
        if vals == [10, 11, 12, 13, 14]:
            return 'royal flush'
        return 'straight flush'
        
    if freqs == [4, 1]:
        return 'four of a kind'
    if freqs == [3, 2]:
        return 'full house'
    if is_flush:
        return 'flush'
    if is_straight:
        return 'straight'
    if freqs == [3, 1, 1]:
        return 'three of a kind'
    if freqs == [2, 2, 1]:
        return 'two pair'
    
    # Jacks or better
    if freqs == [2, 1, 1, 1]:
        for val, count in counts.items():
            if count == 2 and val >= 11: # J, Q, K, A
                return 'jacks or better'
                
    return 'NO WIN'


# ── LUCK ENGINE (PI-Modulated Biological Probability) ───────────────────────

def calculate_luck() -> float:
    """
    Returns LUCK as a percentage between 1.0% and 6.0%.
    Uses PI as the irrational seed — never repeatable, never mechanical.
    
    This is Alice's CHOICE, just like the biological latency.
    PI makes it feel alive.
    """
    # Random position on the PI circle
    theta = random.uniform(0, 2 * math.pi)
    
    # Project onto [0, 1] using sin — naturally bounded, irrational
    pi_factor = (math.sin(theta) + 1.0) / 2.0  # 0.0 to 1.0
    
    # Scale to 1% - 6% range
    luck_pct = 1.0 + pi_factor * 5.0
    
    return round(luck_pct, 2)


# ── Biological Deck (Stigmergic Luck Engine) ───────────────────────────────

class DeckAgent:
    def __init__(self, card: Card):
        self.card = card
        self.x = random.uniform(0, 100)
        self.y = random.uniform(0, 100)
        self.vx = random.uniform(-1, 1)
        self.vy = random.uniform(-1, 1)

class BiologicalDeck(QWidget):
    """Hidden UI element or background that shuffles via Swimmer physics."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(200, 50) # Minimalist visual
        self.agents = []
        for s in SUITS:
            for v in VALUES:
                self.agents.append(DeckAgent(Card(s, v)))
        
        self.heat = 1.0
        self.luck = calculate_luck()  # Current LUCK percentage
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
    
    def reroll_luck(self):
        """New LUCK value each hand — PI decides."""
        self.luck = calculate_luck()
        
    def tick(self):
        self.heat = max(1.0, self.heat * 0.95)
        speed = 1.0 * self.heat
        
        # LUCK GRAVITY: high-value cards get a subtle pull toward center
        # The pull strength is proportional to LUCK %
        luck_force = self.luck / 100.0  # 0.01 to 0.06
        
        for a in self.agents:
            a.x += a.vx * speed
            a.y += a.vy * speed
            
            # LUCK PHYSICS: Face cards and Aces feel gravitational pull toward center
            card_value = val_to_int(a.card.value)
            if card_value >= 11:  # J, Q, K, A
                # Gentle drift toward center (50, 50)
                dx = 50 - a.x
                dy = 50 - a.y
                dist = math.hypot(dx, dy)
                if dist > 1:
                    a.vx += (dx / dist) * luck_force * self.heat
                    a.vy += (dy / dist) * luck_force * self.heat
            
            if a.x <= 0 or a.x >= 100: a.vx *= -1
            if a.y <= 0 or a.y >= 100: a.vy *= -1
            a.vx += random.uniform(-0.1, 0.1) * self.heat
            a.vy += random.uniform(-0.1, 0.1) * self.heat
            # Normalize
            l = math.hypot(a.vx, a.vy)
            if l > 0:
                a.vx /= l
                a.vy /= l
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(8, 10, 18))
        painter.setPen(Qt.PenStyle.NoPen)
        for a in self.agents:
            col = QColor(247, 118, 142) if a.card.is_red() else QColor(100, 108, 140)
            painter.setBrush(col)
            # Map 100x100 to widget size
            px = int(a.x / 100 * self.width())
            py = int(a.y / 100 * self.height())
            painter.drawEllipse(px, py, 3, 3)

    def draw_cards(self, count: int, exclude: List[Card] = []) -> List[Card]:
        """Draws cards by harvesting agents physically closest to the center."""
        # Sort agents by distance to center (50, 50)
        valid_agents = [a for a in self.agents if a.card not in exclude]
        valid_agents.sort(key=lambda a: (a.x - 50)**2 + (a.y - 50)**2)
        return [a.card for a in valid_agents[:count]]


# ── Poker Canvas ────────────────────────────────────────────────────────────

class PokerCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.hand: List[Card] = []
        self.held: List[bool] = [False]*5
        self.result_text = ""
        
        # Load a nice font
        self.card_font = QFont("Courier New", 24, QFont.Weight.Bold)
        self.suit_font = QFont("Courier New", 32, QFont.Weight.Bold)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(15, 18, 25))
        
        if not self.hand:
            # Draw placeholder
            painter.setPen(QColor(100, 108, 140))
            painter.setFont(QFont("Courier New", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "♠ Type 'deal' to ALICE to draw cards ♠")
            return

        # Draw 5 cards
        card_w = 80
        card_h = 120
        spacing = 15
        total_w = 5 * card_w + 4 * spacing
        start_x = (self.width() - total_w) // 2
        y = 50

        for i, card in enumerate(self.hand):
            x = start_x + i * (card_w + spacing)
            
            # Card BG
            painter.setBrush(QColor(24, 28, 40))
            painter.setPen(QPen(QColor(65, 72, 104), 2))
            if self.held[i]:
                painter.setBrush(QColor(36, 40, 59))
                painter.setPen(QPen(QColor(0, 255, 200), 2)) # Highlight held
                
            painter.drawRoundedRect(x, y, card_w, card_h, 8, 8)
            
            # Text Color
            color = QColor(247, 118, 142) if card.is_red() else QColor(169, 177, 214)
            painter.setPen(color)
            
            # Value
            painter.setFont(self.card_font)
            painter.drawText(x + 5, y + 25, card.value)
            # Suit
            painter.setFont(self.suit_font)
            painter.drawText(x, y, card_w, card_h, Qt.AlignmentFlag.AlignCenter, card.suit)
            
            if self.held[i]:
                painter.setPen(QColor(0, 255, 200))
                painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
                painter.drawText(x, y + card_h + 15, card_w, 20, Qt.AlignmentFlag.AlignCenter, "HELD")

        # Draw Result
        if self.result_text:
            painter.setPen(QColor(255, 158, 100))
            painter.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
            painter.drawText(0, y - 40, self.width(), 30, Qt.AlignmentFlag.AlignCenter, self.result_text.upper())


# ── Main Application ────────────────────────────────────────────────────────

class StigmergicVideoPokerApp(SiftaBaseWidget):
    APP_NAME = "Stigmergic Video Poker"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.set_status("Initializing Biological Luck Engine...")
        
        try:
            from System.casino_vault import CasinoVault
            self.vault = CasinoVault(architect_id="IOAN_M5")
        except ImportError:
            self._gci.append_system_message("[SYSTEM ERROR] Could not locate Casino Vault.")
            return

        self.bet = 0.1
        self.phase = 'betting' # betting -> dealt -> drawn -> gamble
        self.gamble_winnings = 0.0  # current winnings at risk in double-or-nothing
        
        # HUD
        hud_layout = QHBoxLayout()
        self.wallet_label = QLabel("")
        self.wallet_label.setStyleSheet("color: #9ece6a; font-weight: bold; font-family: monospace; font-size: 14px;")
        
        self.casino_label = QLabel("")
        self.casino_label.setStyleSheet("color: #f7768e; font-weight: bold; font-family: monospace; font-size: 14px; padding-left: 20px;")
        
        self.luck_label = QLabel("")
        self.luck_label.setStyleSheet("color: #bb9af7; font-weight: bold; font-family: monospace; font-size: 14px; padding-left: 20px;")
        
        hud_layout.addWidget(self.wallet_label)
        hud_layout.addWidget(self.casino_label)
        hud_layout.addWidget(self.luck_label)
        
        hud_layout.addStretch()
        
        self.deck_engine = BiologicalDeck()
        hud_layout.addWidget(self.deck_engine)
        
        layout.addLayout(hud_layout)
        
        self.canvas = PokerCanvas()
        layout.addWidget(self.canvas)
        
        # ── BUTTONS ─────────────────────────────────────────────────────────
        btn_style = """
            QPushButton {
                background-color: #1a1b26;
                color: #c0caf5;
                border: 2px solid #414868;
                border-radius: 6px;
                padding: 8px 16px;
                font-family: 'Courier New';
                font-size: 13px;
                font-weight: bold;
                min-width: 55px;
            }
            QPushButton:hover {
                background-color: #24283b;
                border-color: #7aa2f7;
                color: #7aa2f7;
            }
            QPushButton:pressed {
                background-color: #414868;
            }
            QPushButton:disabled {
                background-color: #0f1018;
                color: #414868;
                border-color: #292e42;
            }
        """
        deal_style = btn_style.replace("#414868", "#9ece6a").replace("#7aa2f7", "#9ece6a")
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        
        self.btn_deal = QPushButton("♠ DEAL")
        self.btn_deal.setStyleSheet(deal_style)
        self.btn_deal.clicked.connect(self._btn_deal_clicked)
        btn_row.addWidget(self.btn_deal)
        
        self.hold_buttons: list[QPushButton] = []
        for i in range(5):
            btn = QPushButton(f"HOLD {i+1}")
            btn.setStyleSheet(btn_style)
            btn.setEnabled(False)
            btn.clicked.connect(lambda checked, idx=i: self._btn_hold_clicked(idx))
            btn_row.addWidget(btn)
            self.hold_buttons.append(btn)
        
        self.btn_draw = QPushButton("♦ DRAW")
        self.btn_draw.setStyleSheet(btn_style.replace("#414868", "#f7768e").replace("#7aa2f7", "#f7768e"))
        self.btn_draw.setEnabled(False)
        self.btn_draw.clicked.connect(self._btn_draw_clicked)
        btn_row.addWidget(self.btn_draw)
        
        layout.addLayout(btn_row)

        # ── DOUBLE OR NOTHING ROW ─────────────────────────────────────────
        gamble_style = """
            QPushButton {
                background-color: #1a1b26;
                border: 2px solid #414868;
                border-radius: 6px;
                padding: 10px 20px;
                font-family: 'Courier New';
                font-size: 14px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #24283b; }
            QPushButton:pressed { background-color: #414868; }
            QPushButton:disabled {
                background-color: #0f1018;
                color: #414868;
                border-color: #292e42;
            }
        """
        gamble_row = QHBoxLayout()
        gamble_row.setSpacing(12)

        self.gamble_label = QLabel("")
        self.gamble_label.setStyleSheet("color: #bb9af7; font-weight: bold; font-family: monospace; font-size: 13px;")
        gamble_row.addWidget(self.gamble_label)

        gamble_row.addStretch()

        self.btn_red = QPushButton("🔴 RED")
        self.btn_red.setStyleSheet(gamble_style.replace("#414868", "#f7768e") + "QPushButton { color: #f7768e; }")
        self.btn_red.setEnabled(False)
        self.btn_red.clicked.connect(lambda: self._gamble_guess("red"))
        gamble_row.addWidget(self.btn_red)

        self.btn_black = QPushButton("⚫ BLACK")
        self.btn_black.setStyleSheet(gamble_style.replace("#414868", "#a9b1d6") + "QPushButton { color: #a9b1d6; }")
        self.btn_black.setEnabled(False)
        self.btn_black.clicked.connect(lambda: self._gamble_guess("black"))
        gamble_row.addWidget(self.btn_black)

        self.btn_cashin = QPushButton("💰 CASH IN")
        self.btn_cashin.setStyleSheet(gamble_style.replace("#414868", "#9ece6a") + "QPushButton { color: #9ece6a; }")
        self.btn_cashin.setEnabled(False)
        self.btn_cashin.clicked.connect(self._gamble_cashin)
        gamble_row.addWidget(self.btn_cashin)

        layout.addLayout(gamble_row)
        
        # Hook GCI (text commands still work too)
        if self._gci:
            self._gci.message_sent.connect(self.on_user_typing)
            self._gci.chat_display.append("<span style='color:#7aa2f7;'>[SYSTEM: Use the buttons below or type commands. LUCK is decided by PI.]</span>")
        self.update_hud()

    def update_hud(self):
        player_stgm = round(self.vault.get_real_player_wallet(), 2)
        casino_stgm = round(self.vault.casino_balance, 2)
        luck = self.deck_engine.luck
        self.wallet_label.setText(f"Architect Wallet: {player_stgm} STGM | Bet: {self.bet} STGM")
        self.casino_label.setText(f"Casino Vault: {casino_stgm} STGM")
        self.luck_label.setText(f"🍀 LUCK: {luck:.2f}% (π)")
    
    def _update_button_states(self):
        """Enable/disable buttons based on current game phase."""
        is_betting = self.phase in ('betting', 'drawn')
        is_dealt = self.phase == 'dealt'
        is_gamble = self.phase == 'gamble'
        
        self.btn_deal.setEnabled(is_betting)
        self.btn_deal.setText("♠ DEAL" if is_betting else "---")
        
        self.btn_draw.setEnabled(is_dealt)
        
        for i, btn in enumerate(self.hold_buttons):
            btn.setEnabled(is_dealt)
            if is_dealt and self.canvas.held[i]:
                btn.setText(f"✓ HELD {i+1}")
                btn.setStyleSheet(btn.styleSheet().replace("#414868", "#00ffc8"))
            else:
                btn.setText(f"HOLD {i+1}")

        # Double-or-nothing buttons
        self.btn_red.setEnabled(is_gamble)
        self.btn_black.setEnabled(is_gamble)
        self.btn_cashin.setEnabled(is_gamble)
        if is_gamble:
            self.gamble_label.setText(f"DOUBLE OR NOTHING — {self.gamble_winnings:.2f} STGM at risk!")
        else:
            self.gamble_label.setText("")
    
    def _btn_deal_clicked(self):
        if self.phase in ('betting', 'drawn'):
            self._do_deal()
    
    def _btn_hold_clicked(self, idx: int):
        if self.phase == 'dealt':
            self.canvas.held[idx] = not self.canvas.held[idx]
            self.canvas.update()
            self._update_button_states()
    
    def _btn_draw_clicked(self):
        if self.phase == 'dealt':
            self._do_draw()

    def on_user_typing(self, text: str):
        # Increase heat
        self.deck_engine.heat = min(20.0, self.deck_engine.heat + 5.0)
        
        text_lower = text.lower()
        
        # Parse commands
        if "deal" in text_lower or "draw" in text_lower or "start" in text_lower:
            if self.phase in ('betting', 'drawn'):
                self._do_deal()
            elif self.phase == 'dealt':
                self._do_draw()
                
        elif "hold" in text_lower or "keep" in text_lower:
            if self.phase == 'dealt':
                nums = [int(s) for s in re.findall(r'\b[1-5]\b', text_lower)]
                # Also check words like one, two, three
                word_map = {'one':1, 'two':2, 'three':3, 'four':4, 'five':5, 'first':1, 'second':2, 'third':3, 'fourth':4, 'fifth':5}
                for w, n in word_map.items():
                    if w in text_lower and n not in nums:
                        nums.append(n)
                
                if "all" in text_lower:
                    nums = [1,2,3,4,5]
                elif "none" in text_lower:
                    nums = []
                    
                if nums:
                    # Apply holds
                    for n in nums:
                        idx = n - 1
                        self.canvas.held[idx] = not self.canvas.held[idx]
                    self.canvas.update()
                    if self._gci:
                        self._gci.chat_display.append(f"<span style='color:#7aa2f7;'>[SYSTEM: Cards held. Type 'deal' to draw replacements.]</span>")
                else:
                    if self._gci:
                        self._gci.chat_display.append("<span style='color:#7aa2f7;'>[SYSTEM: Specify which cards to hold, e.g. 'hold 1 4']</span>")

    def _do_deal(self):
        # Process financial transaction
        if not self.vault.process_bet(self.bet):
            if self._gci: self._gci.chat_display.append("<span style='color:#f7768e;'>[SYSTEM: Insufficient STGM. Cut-off protocol engaged. Produce memories to earn more capital.]</span>")
            return
        
        # LUCK rerolls every hand — PI decides
        self.deck_engine.reroll_luck()
        self.update_hud()
        
        self.phase = 'dealt'
        # Draw 5 cards from engine
        self.canvas.hand = self.deck_engine.draw_cards(count=5)
        self.canvas.held = [False] * 5
        self.canvas.result_text = ""
        self.canvas.update()
        self._update_button_states()
        
        if self._gci:
            wallet = round(self.vault.get_real_player_wallet(), 2)
            luck = self.deck_engine.luck
            self._gci.chat_display.append(f"<span style='color:#7aa2f7;'>[SYSTEM: Placed {self.bet} bet. Dealt 5 cards. LUCK: {luck:.2f}% (π). Architect STGM: {wallet}]</span>")

    def _do_draw(self):
        self.phase = 'drawn'
        # Replace non-held cards
        kept = [self.canvas.hand[i] for i in range(5) if self.canvas.held[i]]
        needed = 5 - len(kept)
        new_cards = self.deck_engine.draw_cards(count=needed, exclude=kept)
        
        final_hand = []
        new_idx = 0
        for i in range(5):
            if self.canvas.held[i]:
                final_hand.append(self.canvas.hand[i])
            else:
                final_hand.append(new_cards[new_idx])
                new_idx += 1
                
        self.canvas.hand = final_hand
        self.canvas.held = [False] * 5
        
        # Evaluate
        result = evaluate_hand(final_hand)
        payout_mult = PAY_TABLE.get(result, 0)
        win_amount = payout_mult * self.bet
        
        if win_amount > 0:
            # Don't pay out yet — enter gamble phase
            self.gamble_winnings = win_amount
            self.phase = 'gamble'
            self.canvas.result_text = f"{result} (+{win_amount:.1f} STGM) — DOUBLE OR CASH IN?"
            if self._gci:
                self._gci.chat_display.append(
                    f"<span style='color:#bb9af7;'>[SYSTEM: 🎰 WON {win_amount:.2f} STGM ({result})! "
                    f"Guess RED or BLACK to double, or CASH IN to keep it safe.]</span>")
        else:
            self.canvas.result_text = "NO WIN"
            self.phase = 'drawn'  # back to betting
            
        self.update_hud()
        self.canvas.update()
        self._update_button_states()

    def _gamble_guess(self, guess: str):
        """Double-or-nothing: flip a card. Red or Black?"""
        if self.phase != 'gamble' or self.gamble_winnings <= 0:
            return

        # Flip a fresh card from the biological deck
        flip_card = self.deck_engine.draw_cards(count=1)[0]
        card_is_red = flip_card.is_red()
        player_said_red = guess == "red"

        if card_is_red == player_said_red:
            # WIN — double it
            self.gamble_winnings *= 2
            self.canvas.result_text = (
                f"✅ {flip_card} is {'RED' if card_is_red else 'BLACK'}! "
                f"DOUBLED → {self.gamble_winnings:.2f} STGM — go again?")
            if self._gci:
                self._gci.chat_display.append(
                    f"<span style='color:#9ece6a;'>[SYSTEM: ✅ Flipped {flip_card} — "
                    f"{'RED' if card_is_red else 'BLACK'}! Winnings doubled to "
                    f"{self.gamble_winnings:.2f} STGM. Guess again or CASH IN.]</span>")
            # Stay in gamble phase — can keep doubling
        else:
            # BUST — lose everything
            lost = self.gamble_winnings
            self.gamble_winnings = 0
            self.phase = 'drawn'  # back to betting
            self.canvas.result_text = (
                f"💀 {flip_card} is {'RED' if card_is_red else 'BLACK'}! "
                f"BUST — lost {lost:.2f} STGM")
            if self._gci:
                self._gci.chat_display.append(
                    f"<span style='color:#f7768e;'>[SYSTEM: 💀 Flipped {flip_card} — "
                    f"{'RED' if card_is_red else 'BLACK'}! BUST. Lost {lost:.2f} STGM. "
                    f"The house always wins... sometimes.]</span>")

        self.canvas.update()
        self.update_hud()
        self._update_button_states()

    def _gamble_cashin(self):
        """Cash in winnings — safe choice."""
        if self.phase != 'gamble' or self.gamble_winnings <= 0:
            return

        cashed = self.gamble_winnings
        self.vault.process_payout(cashed, reason="gamble_cashin")
        self.gamble_winnings = 0
        self.phase = 'drawn'  # back to betting
        self.canvas.result_text = f"💰 CASHED IN {cashed:.2f} STGM — smart move."
        if self._gci:
            self._gci.chat_display.append(
                f"<span style='color:#9ece6a;'>[SYSTEM: 💰 Cashed in {cashed:.2f} STGM. "
                f"Smart money. Warren Buffett approves.]</span>")

        self.canvas.update()
        self.update_hud()
        self._update_button_states()

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = StigmergicVideoPokerApp()
    window.resize(1000, 600)
    window.show()
    sys.exit(app.exec())
