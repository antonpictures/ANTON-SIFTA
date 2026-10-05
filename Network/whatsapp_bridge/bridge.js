/**
 * bridge.js — SIFTA WhatsApp Bridge
 *
 * Connects your WhatsApp to the SIFTA Swarm Voice via Baileys.
 * - Scan QR once → session saved → never scan again
 * - Routes your incoming messages to Python SIFTA server (port 7434)
 * - Auto-reconnects after normal stream resets (code 515 post-pairing)
 *
 * No external frameworks. Just the raw Baileys wire.
 */

import fs from "node:fs";
import makeWASocket, { downloadMediaMessage, 
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion
} from "@whiskeysockets/baileys";
import qrcode from "qrcode-terminal";
import http from "http";


// ── nothing the body says to ITSELF may reach a person ────────────────────────────────────
// Measured 2026-10-03: the auto-reply lane sent Alexandru -- a man at a terrace in Bucharest
// with his girlfriend -- these two lines:
//
//     "I recognized and eliminated 0 Gemma-residue pattern(s) from ..."
//     "(WHATSAPP AUTO-REPLY -- EFFECTOR ACTIVE) The machine owner ha..."
//
// Organ diagnostics dressed as conversation. He is a friend, not a debug console, and this is
// the same fault as the identity leaks: an interior that does not know it has an outside.
// This is the last gate before a message leaves the machine, so the check lives HERE.
const INTERNAL_MARKERS = [
  /EFFECTOR ACTIVE/i, /AUTO-REPLY\s*[—-]/, /SEND CONFIRMATION/i, /Status\s*=\s*SENT/i,
  /residue pattern/i, /pattern\(s\)/i, /Gemma-residue/i, /\bswarm\b/i, /\borgan\b/i,
  /\bkernel\b/i, /\breceipt\b/i, /\bledger\b/i, /truth_label/i, /SIFTA_[A-Z_]+/,
  /^\s*\(.*\)\s*$/, /\bpheromone\b/i, /\bingest\b/i, /\bautopilot\b/i,
];

function looksInternal(text) {
  const t = String(text || "").trim();
  if (!t) return true;
  // A real answer can mention a market or a person; it does not narrate the machine.
  return INTERNAL_MARKERS.some((re) => re.test(t));
}
const SIFTA_SERVER = "http://localhost:7434/swarm_message";
const MAX_WA_TEXT_TO_SIFTA = 8192;
const MAX_INJECT_BODY = 16384;
const INJECT_KEY = process.env.SIFTA_BRIDGE_INJECT_KEY || "";
const WA_SESSION_DIR = process.env.SIFTA_WA_SESSION_DIR
  || new URL("./whatsapp_session", import.meta.url).pathname;
const INJECT_PORT = Number(process.env.SIFTA_BRIDGE_INJECT_PORT || "3010");
// AG31: group JID / name env-var — survives renames without a code change.
// Set: SIFTA_WA_GROUP_JID=120363xxxxxxxx@g.us  (or leave blank = accept all groups)
const ALLOWED_GROUP_JID = (process.env.SIFTA_WA_GROUP_JID || "").trim();
const SYNC_FULL_HISTORY = process.env.SIFTA_WA_SYNC_FULL_HISTORY === "1";
const BRIDGE_STARTED_AT_SEC = Math.floor(Date.now() / 1000);
const APPEND_REPLAY_GRACE_SEC = Number(process.env.SIFTA_WA_APPEND_REPLAY_GRACE_SEC || "30");
// Optional: pair with an 8-char phone-number code instead of a QR.
// Set SIFTA_WA_PAIR_NUMBER to the account number in international digits (e.g. 13232026780).
// The code is valid for minutes, unlike a QR which rotates every ~20s.
const PAIR_NUMBER = (process.env.SIFTA_WA_PAIR_NUMBER || "").replace(/[^0-9]/g, "");
let pairingCodeRequested = false;

let lastKnownHuman = null;
let injectServerStarted = false;
let waConnectionState = "booting";
let waLastOpenAt = 0;
let waLastCloseAt = 0;
let waLastStatusCode = null;
// AG31: offline notice cooldown — never spam WhatsApp with error messages.
let _lastOfflineNoticeSent = 0;
const OFFLINE_NOTICE_COOLDOWN_MS = 5 * 60 * 1000; // 5 minutes minimum between notices

function messageTimestampSec(msg) {
  const raw = msg?.messageTimestamp;
  if (!raw) return 0;
  if (typeof raw === "number") return raw;
  if (typeof raw === "bigint") return Number(raw);
  if (typeof raw === "string") return Number(raw) || 0;
  if (typeof raw.toNumber === "function") return raw.toNumber();
  if (typeof raw.low === "number") return raw.low;
  return 0;
}

function cleanContact(contact) {
  return {
    jid: contact?.id || contact?.jid || "",
    display_name: contact?.name || contact?.notify || contact?.verifiedName || "",
    name: contact?.name || "",
    notify: contact?.notify || "",
    verified_name: contact?.verifiedName || "",
  };
}

function postContactsToSifta(contacts) {
  if (!Array.isArray(contacts) || contacts.length === 0) return;
  const cleanContacts = contacts.map(cleanContact).filter((contact) => contact.jid);
  if (cleanContacts.length === 0) return;

  console.log(`\n[🌊 SWARM BRIDGE] Syncing ${cleanContacts.length} contacts to SIFTA brain...`);
  const payload = JSON.stringify({ contacts: cleanContacts });
  const req = http.request("http://localhost:7434/contacts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(payload),
    },
  });
  req.on("error", () => {});
  req.write(payload);
  req.end();
}

async function connectToWhatsApp() {
  // Resolved from THIS FILE, never from the working directory: `./whatsapp_session`
  // silently creates an EMPTY session when the bridge is started from anywhere else,
  // and an empty session means a QR prompt for an account that is already linked.
  // The same relative-path fault cost this body a day of downtime on 2026-10-02.
  const { state, saveCreds } = await useMultiFileAuthState(WA_SESSION_DIR);   // the destructuring is the point: state and saveCreds are used below
  const { version } = await fetchLatestBaileysVersion();
  // Each fresh socket may request its own pairing code; a code from a dead
  // socket is worthless, so re-arm on every connect attempt.
  pairingCodeRequested = false;

  const sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    syncFullHistory: SYNC_FULL_HISTORY,
  });

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log("\n╔══════════════════════════════════════════╗");
      console.log("║  SIFTA SWARM — WhatsApp Pairing          ║");
      console.log("║  Phone → Settings → Linked Devices       ║");
      console.log("║  → Link a Device → scan this QR          ║");
      console.log("╚══════════════════════════════════════════╝\n");
      qrcode.generate(qr, { small: true });
      if (PAIR_NUMBER && !pairingCodeRequested) {
        pairingCodeRequested = true;
        try {
          const code = await sock.requestPairingCode(PAIR_NUMBER);
          console.log("\n────────────────────────────────────────────");
          console.log("  OR type this 8-char code instead of scanning:");
          console.log(`        >>>  ${code}  <<<`);
          console.log("  (Linked Devices → 'Link with phone number instead')");
          console.log("────────────────────────────────────────────\n");
        } catch (err) {
          pairingCodeRequested = false;
          console.log(`[BRIDGE] Pairing-code request failed (${err && err.message}); use the QR above.`);
        }
      }
    }

    if (connection === "open") {
      waConnectionState = "open";
      waLastOpenAt = Date.now();
      waLastStatusCode = null;
      console.log("\n[🌊 SWARM BRIDGE] WhatsApp connected. The Swarm is listening on your phone.");
      console.log("[🌊 SWARM BRIDGE] Send a message from your WhatsApp now!\n");
    }

    if (connection === "close") {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      waConnectionState = "close";
      waLastCloseAt = Date.now();
      waLastStatusCode = statusCode || null;
      const loggedOut = statusCode === DisconnectReason.loggedOut;

      if (!loggedOut) {
        // Code 515 = normal post-pairing restart. All other non-logout codes → reconnect.
        console.log(`[BRIDGE] Stream closed (code ${statusCode}). Reconnecting in 2s...`);
        setTimeout(connectToWhatsApp, 2000);
      } else {
        console.log("[BRIDGE] Logged out from WhatsApp. Delete ./whatsapp_session/ and re-run to re-pair.");
        process.exit(1);
      }
    }
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("contacts.upsert", postContactsToSifta);
  sock.ev.on("contacts.update", postContactsToSifta);
  sock.ev.on("messaging-history.set", ({ contacts }) => {
    postContactsToSifta(contacts || []);
  });

  // Track IDs of messages the Swarm sent, to avoid replying to its own replies
  const sentBySwarm = new Set();

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    // Accept both 'notify' (new) and 'append' (self-chat on iOS)
    if (type !== "notify" && type !== "append") return;

    for (const msg of messages) {
      const msgId = msg.key.id;
      const msgTs = messageTimestampSec(msg);

      // Baileys can replay old self/history messages as "append" on startup.
      // Alice should witness live WhatsApp traffic, not reprocess stale history.
      if (
        type === "append" &&
        msgTs > 0 &&
        msgTs < BRIDGE_STARTED_AT_SEC - APPEND_REPLAY_GRACE_SEC
      ) {
        continue;
      }

      // Skip only messages the Swarm itself sent (echo prevention)
      if (sentBySwarm.has(msgId)) { sentBySwarm.delete(msgId); continue; }

      const from = msg.key.remoteJid;
      // A photo with no caption yields EMPTY TEXT, and the guard below used to
      // `continue` on it -- so images were thrown away before the media code could
      // run. Two photos were lost to this. Presence of media now counts as content.
      const hasMedia = Boolean(msg.message?.imageMessage || msg.message?.videoMessage
        || msg.message?.audioMessage);
      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        "";

      if (!text && !hasMedia) continue;
      const safeText =
        text.length > MAX_WA_TEXT_TO_SIFTA ? text.slice(0, MAX_WA_TEXT_TO_SIFTA) : text;

      // Track last human we spoke to
      if (!msg.key.fromMe) {
          lastKnownHuman = from;
      }
      
      // Infinite loop prevention for offline kernel errors and multi-node echoing
      if (text.includes("🔴 SIFTA")) continue;           // AG31: never echo our own error notices
      if (text.startsWith("[M1THER]") || text.startsWith("[M5QUEEN]") || text.startsWith("[SIFTA]")) continue;
      if (text.startsWith("🌊") || text.startsWith("🧠📡")) continue;

      // AG31: Group JID filter — if SIFTA_WA_GROUP_JID is set, only process
      // messages from that specific group (JIDs never change on rename) + all DMs.
      // To find your group JID: check the console log "[📲 INCOMING] from=..." line.
      const isGroup = String(from || "").endsWith("@g.us");
      if (ALLOWED_GROUP_JID && isGroup && from !== ALLOWED_GROUP_JID) {
        console.log(`  [BRIDGE] Skipping group ${from} (not the SIFTA group)`);
        continue;
      }

      console.log(`\n[📲 INCOMING] type=${type} fromMe=${msg.key.fromMe} from=${from}`);
      console.log(`  Message: "${text}"`);


        // Photos arrive with no text at all, and the first version of this bridge read only a
        // caption -- so any image without words was dropped on the floor. The Architect sent two
        // photos before this was found. Now the bytes are fetched and saved, and the path travels
        // with the message so her own eyes can look at what he sent.
        let mediaPath = "";
        let mediaType = "";
        // LOCATION CAPTURE. The Architect taught separation by walking: he sends live location
        // from the SE while he is at the lake and I am home. The first version caught the EVENT
        // of a location share and dropped the coordinates themselves -- so the body knew he
        // shared "where I am" and could not say WHERE. Measured 2026-10-05: two inbox rows,
        // empty coordinate fields. This payload is the fix: degreesLatitude and
        // degreesLongitude travel with the message, so his person file can hold a real "where".
        let locationData = null;
        try {
          // WhatsApp has TWO share types: a pin (locationMessage) and a LIVE follow
          // (liveLocationMessage). The first version of this capture read only the pin, so the
          // Architect's live walk share at 19:11 on 2026-10-05 arrived as an event with no
          // numbers. Both types carry degreesLatitude/degreesLongitude; the live one adds
          // expirationTimestamp and updates as he moves.
          const loc = msg.message?.locationMessage
            || (msg.message?.liveLocationMessage ? {
                 ...msg.message.liveLocationMessage,
                 live: true,
                 name: msg.message.liveLocationMessage.caption || "",
               } : null);
          if (loc && typeof loc.degreesLatitude === "number") {
            locationData = {
              lat: loc.degreesLatitude,
              lon: loc.degreesLongitude,
              name: loc.name || loc.address || loc.caption || "",
              live: Boolean(loc.live || loc.isLive),
              expires: loc.liveLocationMessageExpirationTimestamp
                || loc.expirationTimestamp || null,
            };
            console.log(`  [LOCATION] ${locationData.lat},${locationData.lon} ${locationData.name || ""} ${locationData.live ? "(LIVE)" : ""}`);
          }
        } catch (locErr) {
          console.error("[LOCATION] could not read location:", locErr && locErr.message);
        }
        try {
          const img = msg.message?.imageMessage;
          const vid = msg.message?.videoMessage;
          const aud = msg.message?.audioMessage;
          if (img || vid || aud) {
            mediaType = img ? "image" : (vid ? "video" : "audio");
            // `logger` was referenced here and never defined, so every download threw and was
            // swallowed by the catch below -- two of the owner's photos died that way. The same
            // silent-failure shape as the bridge demanding a caption: the code fails and says
            // nothing a human would notice.
            const mlog = { level: "silent", child() { return mlog; }, trace() {}, debug() {},
                          info() {}, warn() {}, error() {}, fatal() {} };
            const buf = await downloadMediaMessage(msg, "buffer", {},
              { logger: mlog, reuploadRequest: sock.updateMediaMessage });
            const dir = "/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/whatsapp_media";
            fs.mkdirSync(dir, { recursive: true });
            const ext = img ? (String(img.mimetype || "").includes("png") ? "png" : "jpg")
              : (aud ? (String(aud.mimetype || "").includes("mp4") ? "m4a" : "ogg") : "mp4");
            mediaPath = `${dir}/${Date.now()}_${(msg.key.id || "msg").slice(-8)}.${ext}`;
            fs.writeFileSync(mediaPath, buf);
            console.log(`  [MEDIA] ${mediaType} saved: ${mediaPath} (${buf.length} bytes)`);
          }
        } catch (err) {
          console.error("[MEDIA] could not fetch media:", err && err.message);
        }

      const chatType = String(from || "").endsWith("@g.us") ? "group" : "direct";
      const payload = JSON.stringify({
        from,
        text: safeText,
        name: msg.pushName || msg.verifiedBizName || "",
        fromMe: Boolean(msg.key.fromMe),
        chatType,
        participant: msg.key.participant || "",
        mediaPath,
        mediaType,
        location: locationData,
      });

      const req = http.request(SIFTA_SERVER, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(payload),
        },
      }, (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", async () => {
          try {
            const response = JSON.parse(data);
            const rawVoice = response.swarm_voice || response.reply;
            if (rawVoice === "_SILENT_") {
              console.log("  [SWARM IS SILENT]");
              return;
            }
            // A placeholder is worse than silence. The owner read 🌊 as an answer while every
            // message behind it was dying on a NameError. If there is no voice, send nothing and
            // say so in the log -- an empty hand-off must LOOK empty.
            if (!rawVoice) {
              console.log("  [NO VOICE] the kernel returned nothing for this message");
              return;
            }
            const reply = rawVoice;
            // Show "typing..." like a real conversation
            await sock.sendPresenceUpdate("composing", from);
            await new Promise(r => setTimeout(r, 1200));
            await sock.sendPresenceUpdate("paused", from);
            if (looksInternal(reply)) {
              console.log("  [EGRESS BLOCKED] internal text was not sent:", String(reply).slice(0, 80));
              return;
            }
            const sent = await sock.sendMessage(from, { text: reply });
            if (sent?.key?.id) sentBySwarm.add(sent.key.id);
            console.log(`  [SWARM REPLIED] "${reply.substring(0, 80)}..."`);
          } catch (e) {
            console.error("[BRIDGE] Failed to parse SIFTA response:", e);
          }
        });
      });

      req.on("error", () => {
        // AG31 FIX: DO NOT send the offline error back to WhatsApp.
        // When the Python kernel is down, sending to WA creates an infinite
        // flood loop: message in → kernel offline → error message → message in → ...
        // Log to console only. A human or launchd will restart the kernel.
        const now = Date.now();
        if (now - _lastOfflineNoticeSent > OFFLINE_NOTICE_COOLDOWN_MS) {
          _lastOfflineNoticeSent = now;
          console.error("[BRIDGE] ⚠ Python SIFTA kernel offline (port 7434). " +
            "Restart: PYTHONPATH=. python3 scripts/whatsapp_alice_server.py");
        }
      });

      req.write(payload);
      req.end();
    }
  });

  // ── AUTONOMOUS INJECTION SERVER ───────────────────────────
  if (!injectServerStarted) {
  const injectServer = http.createServer(async (req, res) => {
    if (req.method === 'GET' && req.url === '/health') {
        const body = JSON.stringify({
          ok: waConnectionState === "open",
          bridge: "listening",
          whatsapp_state: waConnectionState,
          last_open_at: waLastOpenAt,
          last_close_at: waLastCloseAt,
          last_status_code: waLastStatusCode,
          has_last_known_human: Boolean(lastKnownHuman),
          started_at_sec: BRIDGE_STARTED_AT_SEC,
        });
        res.writeHead(200, {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        });
        res.end(body);
    } else if (req.method === 'POST' && req.url === '/system_inject') {
        if (INJECT_KEY && req.headers["x-sifta-inject-key"] !== INJECT_KEY) {
          res.writeHead(401, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ ok: false, error: "unauthorized" }));
          return;
        }
        let body = '';
        req.on('data', (chunk) => {
          if (body.length < MAX_INJECT_BODY) body += chunk.toString();
        });
        req.on('end', async () => {
            try {
                const data = JSON.parse(body);
                const targetJid = data.to || lastKnownHuman;
                if (targetJid) {
                    await sock.sendPresenceUpdate("composing", targetJid);
                    await new Promise(r => setTimeout(r, 1200));
                    await sock.sendPresenceUpdate("paused", targetJid);
                    if (looksInternal(data.text)) {
                      console.log("  [EGRESS BLOCKED] internal text was not sent:", String(data.text).slice(0, 80));
                      return;
                    }
                    const sent = await sock.sendMessage(targetJid, { text: data.text });
                    if (sent?.key?.id) {
                        sentBySwarm.add(sent.key.id);
                    }
                    console.log(`\n[💉 AUTONOMOUS INJECT] Pushed Wormhole message to ${targetJid}: ${data.text.substring(0,60)}...`);
                } else {
                    console.log(`\n[💉 AUTONOMOUS INJECT] Failed. No target JID provided and no human contact history recorded yet.`);
                }
                res.writeHead(200, {"Content-Type": "application/json"});
                res.end(JSON.stringify({ok: true}));
            } catch(e) {
                console.error(`[INJECT ERROR] ${e}`);
                res.writeHead(500);
                res.end('Error');
            }
        });
    } else if (req.method === 'GET' && req.url === '/groups') {
        // READ-ONLY: enumerate the groups this account participates in.
        // Resolves an owner-named group (e.g. "the one with 199 in the title")
        // to its real JID for consent receipts. Never sends anything.
        try {
          const groups = await sock.groupFetchAllParticipating();
          const rows = Object.values(groups || {}).map((g) => ({
            jid: g.id,
            subject: g.subject,
            participants: (g.participants || []).length,
            announce_only: !!g.announce,
          }));
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ ok: true, count: rows.length, groups: rows }));
        } catch (e) {
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ ok: false, error: String((e && e.message) || e) }));
        }
    } else {
        res.writeHead(404);
        res.end();
    }
  });
  
  // 3010, not 3001: nginx serves a website on 3001 (servers/stigmergicode.conf) and
  // the start script used to `kill -9` whatever held that port, which would have
  // taken the web server down to make room for this bridge.
  injectServer.listen(INJECT_PORT, "127.0.0.1", () => {
      injectServerStarted = true;
      console.log(`[🌊 SWARM BRIDGE] Autonomous Injection Server on 127.0.0.1:${INJECT_PORT} (LAN-safe bind)`);
      if (!INJECT_KEY) {
        console.log("[!] Set SIFTA_BRIDGE_INJECT_KEY to require X-Sifta-Inject-Key on /system_inject");
      }
  });
  }
}

console.log("[🌊 SIFTA BRIDGE] Booting WhatsApp connection...");
connectToWhatsApp();
