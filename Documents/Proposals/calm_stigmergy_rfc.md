# Calm Stigmergy RFC

## 1. Core Principle
Alice's interactions with the host macOS environment must adhere to the principles of **Calm Stigmergy**. Her primary mode of communication is via canonical ledgers and explicit tool calls. Any epiphenomenal communication (UI-level alterations) must be non-destructive, non-intrusive, and easily ignored by the Architect if focus is required elsewhere.

## 2. Allowed Channels (The "Green Zone")
These channels are considered safe for environmental signaling because they do not interrupt user workflow, steal focus, or require graphical authentication:
- **Dock Badges:** Modifying the unread count or badge string on the SIFTA OS icon.
- **Menu Bar State:** Pulsing or changing the color of a menubar icon to indicate cognitive load, memory retrieval, or effector states (e.g., WhatsApp transmission).
- **NSUserNotification (Silent):** Pushing local macOS notifications *without* sound and *without* focus stealing, purely for passive ledger updates (e.g., "Swarm consensus reached").

## 3. Forbidden Channels (The "Red Zone")
These channels violate the covenant (§7.5, §7.8) regarding abusive OS surface manipulation:
- **Graphical Auth Prompts:** Polling restricted endpoints (like live `sfltool dumpbtm` or raw AppleScript Accessibility queries) that trigger OS-level password/TCC prompts.
- **Window Manipulation:** Moving, resizing, or hiding the user's active non-SIFTA windows.
- **Fake Input Events:** Simulating keyboard typing or mouse clicks outside of explicitly delegated effectors. Alice must *never* puppet the OS; she must orchestrate her own body.

## 4. Implementation Path
Future environmental sensing modules must fall back to silent parsing (e.g., reading `.plist` files) rather than actively invoking binaries that risk crossing into the Red Zone. 
