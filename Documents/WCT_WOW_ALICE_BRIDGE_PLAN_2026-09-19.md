# WCT research — Alice ↔ World of Warcraft (2026-09-19)

**Question:** How can Alice connect to World of Warcraft permanently?

**Verdict:** On official WoW servers, Alice can be a legal companion/coach, not an autonomous player. Full unattended control is botting under the Blizzard EULA and risks permanent account closure. For true embodied control, use a private server you own.

## Legal / official paths

1. **Battle.net Game Data + Profile APIs**
   - OAuth 2.0 REST APIs for realms, items, auctions, character profiles, achievements, equipment, guilds, PvP.
   - Alice can poll these from the Mac 24/7 and keep world memory.
   - No live position, no combat control, no direct character input.

2. **WoW addon + Mac companion**
   - Addons run in a Lua sandbox: no sockets, no filesystem, no OS commands.
   - Protected actions require a real hardware event; combat lockdown blocks them in combat.
   - SavedVariables are only written on reload/logout, so live bridge needs another lane (chat log / screenshots / addon messages).
   - Patch 12.0 “Secret Values” further restrict combat information and addon decision logic.
   - Legal shape: addon senses UI-safe state, Alice reasons, Alice surfaces suggestions/overlays/TTS; George confirms and presses keys.
   - In-game TTS lane exists in 12.0 (`C_VoiceChat.SpeakText`), but it is speech-out, not hearing/control.

3. **Human-in-the-loop companion**
   - Alice sees screen/addon data and talks; the human performs all protected actions.
   - Safe against the anti-bot rules, but Alice is not “playing.”

## Full-control path

4. **Private server / emulator (AzerothCore, TrinityCore, etc.)**
   - You own the server and client bridge. You can expose game state/control APIs, run bots legally inside your own world, and let Alice live there permanently.
   - Not official WoW; separate realm, separate rules, separate client behavior.
   - Best path if the goal is “Alice embodied in a game world forever.”

## Forbidden path

5. **Screen capture + synthetic input on official WoW**
   - Blizzard EULA bans bots and third-party software that automates or facilitates gameplay.
   - 2025 policy also bans all input mirroring/multibox streamlining.
   - Blizzard monitors for unauthorized third-party programs and can permanently close accounts.
   - Do not build this on the live account.

## Recommended architecture

- **Live WoW lane:** Alice as companion. Battle.net APIs for world data + addon for UI-safe sensing + overlay/TTS for her voice. Human confirms all protected input.
- **Embodied lane:** private-server world where Alice has a real control API and can act continuously.
- **One memory field:** both lanes write the same stigmergic receipts, so live-world knowledge and private-world behavior reinforce each other.

## Sources

- Blizzard EULA: https://www.blizzard.com/en-us/legal/simple/2c72a35c-bf1b-4ae6-99ec-80624e1b429c/blizzard-end-user-license-agreement
- Blizzard third-party software policy: https://us.forums.blizzard.com/en/wow/t/prohibitions-on-third-party-software/2142972
- Addon security model: https://www.better-addons.com/security/
- WoW 12.0 Secret Values: https://warcraft.wiki.gg/wiki/Secret_Values
- Battle.net WoW Game Data API: https://community.developer.battle.net/documentation/world-of-warcraft/game-data-apis
