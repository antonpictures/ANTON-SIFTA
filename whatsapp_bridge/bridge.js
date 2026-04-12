/**
 * bridge.js — SIFTA WhatsApp Bridge
 *
 * Connects your WhatsApp to the SIFTA Swarm Voice via Baileys.
 * - Scan QR once → session saved → never scan again
 * - Routes your incoming messages to Python SIFTA server (port 7434)
 * - Auto-reconnects after normal stream resets (code 515 post-pairing)
 *
 * No OpenClaw. No framework. Just the raw Baileys wire.
 */

import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion
} from "@whiskeysockets/baileys";
import qrcode from "qrcode-terminal";
import http from "http";

const SIFTA_SERVER = "http://localhost:7434/swarm_message";

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
            const reply = response.swarm_voice || response.reply || "🌊";
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
}

console.log("[🌊 SIFTA BRIDGE] Booting WhatsApp connection...");
connectToWhatsApp();
