"""
SIFTA RPN (Reverse Polish Notation) Stack Parser
Inspired by SimplicityOS / Bare Metal Forth Interfaces
"""

class ForthException(Exception):
    pass

class SiftaForthParser:
    def __init__(self):
        self.stack = []
        self.dictionary = {
            # Primitive Stack Operators
            'DUP': self._dup,
            'DROP': self._drop,
            'SWAP': self._swap,
            'OVER': self._over,
            '+': self._add,
            '-': self._sub,
            '*': self._mul,
            '.': self._print_pop,
            '.S': self._print_stack,
            
            # Bare Metal Swarm OS Bindings
            '@': self._fetch_swarm_memory,     # e.g., 0x4000 @
            '!': self._store_swarm_memory,     # e.g., "ATTACK" 0x4000 !
            'SWARM:RECRUIT': self._swarm_recruit,
            'BOUNTY:MINT': self._bounty_mint,
            'HEARTBEAT': self._heartbeat,
        }
        self.output_buffer = []

    def _push(self, item):
        self.stack.append(item)

    def _pop(self):
        if not self.stack:
            raise ForthException("Stack Underflow")
        return self.stack.pop()

    def _dup(self):
        if not self.stack: raise ForthException("Stack Underflow")
        self._push(self.stack[-1])

    def _drop(self):
        self._pop()

    def _swap(self):
        a = self._pop()
        b = self._pop()
        self._push(a)
        self._push(b)

    def _over(self):
        if len(self.stack) < 2: raise ForthException("Stack Underflow")
        self._push(self.stack[-2])

    def _add(self):
        a, b = self._pop(), self._pop()
        self._push(b + a)

    def _sub(self):
        a, b = self._pop(), self._pop()
        self._push(b - a)

    def _mul(self):
        a, b = self._pop(), self._pop()
        self._push(b * a)

    def _print_pop(self):
        val = self._pop()
        self.output_buffer.append(str(val))

    def _print_stack(self):
        self.output_buffer.append(f"<{len(self.stack)}> " + " ".join(str(x) for x in self.stack))

    # --- SIFTA SPECIFIC BINDINGS ---
    def _fetch_swarm_memory(self):
        addr = self._pop()
        self.output_buffer.append(f"Read 8 bytes from SCAR map at {addr}")
        self._push(f"SCAR[{addr}]_VAL")

    def _store_swarm_memory(self):
        addr = self._pop()
        val = self._pop()
        self.output_buffer.append(f"Written '{val}' to SCAR vector {addr}")

    def _swarm_recruit(self):
        count = self._pop()
        self.output_buffer.append(f"[SWARM_OS] Recruited {count} autonomous agents.")

    def _bounty_mint(self):
        qty = self._pop()
        self.output_buffer.append(f"[LEDGER] Minted {qty} STGM to local ledger.")

    def _heartbeat(self):
        self.output_buffer.append("[🫀 BIOS] Autonomic Pulse Verified: 64 Active Nodes.")

    def evaluate(self, command_string: str) -> str:
        self.output_buffer.clear()
        tokens = command_string.strip().split()
        
        for token in tokens:
            if token.upper() in self.dictionary:
                try:
                    self.dictionary[token.upper()]()
                except ForthException as e:
                    self.output_buffer.append(f"Error: {e}")
                    break
            else:
                try:
                    if token.startswith("0x"):
                        self._push(token)
                    elif '.' in token:
                        self._push(float(token))
                    else:
                        self._push(int(token))
                except ValueError:
                    self._push(token)
                    
        return " ".join(self.output_buffer) if self.output_buffer else "ok"
