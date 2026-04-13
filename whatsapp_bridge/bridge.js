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

import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion
} from "@whiskeysockets/baileys";
import qrcode from "qrcode-terminal";
import http from "http";

const SIFTA_SERVER = "http://localhost:7434/swarm_message";
let lastKnownHuman = null;

async function connectToWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState("./whatsapp_session");
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
  });

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log("\n╔══════════════════════════════════════════╗");
      console.log("║  SIFTA SWARM — WhatsApp Pairing QR Code  ║");
      console.log("║  Open WhatsApp → Linked Devices → Scan  ║");
      console.log("╚══════════════════════════════════════════╝\n");
      qrcode.generate(qr, { small: true });
    }

    if (connection === "open") {
      console.log("\n[🌊 SWARM BRIDGE] WhatsApp connected. The Swarm is listening on your phone.");
      console.log("[🌊 SWARM BRIDGE] Send a message from your WhatsApp now!\n");
    }

    if (connection === "close") {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
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

  // Track IDs of messages the Swarm sent, to avoid replying to its own replies
  const sentBySwarm = new Set();

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    // Accept both 'notify' (new) and 'append' (self-chat on iOS)
    if (type !== "notify" && type !== "append") return;

    for (const msg of messages) {
      const msgId = msg.key.id;

      // Skip only messages the Swarm itself sent (echo prevention)
      if (sentBySwarm.has(msgId)) { sentBySwarm.delete(msgId); continue; }

      const from = msg.key.remoteJid;
      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        "";

      if (!text) continue;
      
      // Track last human we spoke to
      if (!msg.key.fromMe) {
          lastKnownHuman = from;
      }
      
      // Infinite loop prevention for offline kernel errors and multi-node echoing
      if (text.includes("🔴 SIFTA kernel is offline")) continue;
      if (text.startsWith("[M1THER]") || text.startsWith("[M5QUEEN]") || text.startsWith("[SIFTA]")) continue;
      if (text.startsWith("🌊") || text.startsWith("🧠📡")) continue;

      console.log(`\n[📲 INCOMING] type=${type} fromMe=${msg.key.fromMe} from=${from}`);
      console.log(`  Message: "${text}"`);

      const payload = JSON.stringify({ from, text });

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
            const reply = rawVoice || "🌊";
            // Show "typing..." like a real conversation
            await sock.sendPresenceUpdate("composing", from);
            await new Promise(r => setTimeout(r, 1200));
            await sock.sendPresenceUpdate("paused", from);
            const sent = await sock.sendMessage(from, { text: reply });
            if (sent?.key?.id) sentBySwarm.add(sent.key.id);
            console.log(`  [SWARM REPLIED] "${reply.substring(0, 80)}..."`);
          } catch (e) {
            console.error("[BRIDGE] Failed to parse SIFTA response:", e);
          }
        });
      });

      req.on("error", () => {
        sock.sendMessage(from, {
          text: "🔴 SIFTA kernel is offline. Restart whatsapp_swarm.py.",
        });
      });

      req.write(payload);
      req.end();
    }
  });

  // ── AUTONOMOUS INJECTION SERVER ───────────────────────────
  const injectServer = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/system_inject') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const data = JSON.parse(body);
                if (lastKnownHuman) {
                    await sock.sendPresenceUpdate("composing", lastKnownHuman);
                    await new Promise(r => setTimeout(r, 1200));
                    await sock.sendPresenceUpdate("paused", lastKnownHuman);
                    const sent = await sock.sendMessage(lastKnownHuman, { text: data.text });
                    if (sent?.key?.id) {
                        sentBySwarm.add(sent.key.id);
                    }
                    console.log(`\n[💉 AUTONOMOUS INJECT] Pushed Wormhole message to WhatsApp: ${data.text.substring(0,60)}...`);
                } else {
                    console.log(`\n[💉 AUTONOMOUS INJECT] Failed. No human contact history recorded yet.`);
                }
                res.writeHead(200, {"Content-Type": "application/json"});
                res.end(JSON.stringify({ok: true}));
            } catch(e) {
                console.error(`[INJECT ERROR] ${e}`);
                res.writeHead(500);
                res.end('Error');
            }
        });
    } else {
        res.writeHead(404);
        res.end();
    }
  });
  
  injectServer.listen(3001, () => {
      console.log("[🌊 SWARM BRIDGE] Autonomous Injection Server listening on port 3001");
  });
}

console.log("[🌊 SIFTA BRIDGE] Booting WhatsApp connection...");
connectToWhatsApp();
