/**
 * bridge.js — SIFTA WhatsApp Bridge
 *
 * Connects your WhatsApp to the SIFTA Swarm Voice via Baileys.
 * - Scan QR once → session saved → never scan again
 * - Routes your incoming messages to Python SIFTA server (port 7434)
 * - Sends Swarm Voice replies back to your WhatsApp
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

// ─── Session persistence (scan once, saved forever) ───────────────────────
const { state, saveCreds } = await useMultiFileAuthState("./whatsapp_session");
const { version } = await fetchLatestBaileysVersion();

const sock = makeWASocket({
  version,
  auth: state,
  printQRInTerminal: false, // We handle QR ourselves for styling
});

// ─── QR Code ──────────────────────────────────────────────────────────────
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
    console.log("\n[🌊 SWARM BRIDGE] WhatsApp connected. The Swarm is listening.");
  }

  if (connection === "close") {
    const shouldReconnect =
      lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
    console.log("[BRIDGE] Connection closed. Reconnecting:", shouldReconnect);
    if (shouldReconnect) {
      // Restart the process to reconnect
      process.exit(0);
    }
  }
});

sock.ev.on("creds.update", saveCreds);

// ─── Incoming Message Handler ──────────────────────────────────────────────
sock.ev.on("messages.upsert", async ({ messages, type }) => {
  if (type !== "notify") return;

  for (const msg of messages) {
    if (msg.key.fromMe) continue; // Don't reply to own messages

    const from = msg.key.remoteJid;
    const text =
      msg.message?.conversation ||
      msg.message?.extendedTextMessage?.text ||
      "";

    if (!text) continue;

    console.log(`\n[📲 INCOMING] From: ${from}`);
    console.log(`  Message: "${text}"`);

    // Forward to SIFTA Python server
    const payload = JSON.stringify({ from, text });

    const req = http.request(SIFTA_SERVER, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) },
    }, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", async () => {
        try {
          const response = JSON.parse(data);
          const reply = response.swarm_voice || response.reply || "🌊";
          await sock.sendMessage(from, { text: reply });
          console.log(`  [SWARM REPLIED] "${reply.substring(0, 80)}..."`);
        } catch (e) {
          console.error("[BRIDGE] Failed to parse SIFTA response:", e);
        }
      });
    });

    req.on("error", (e) => {
      console.error("[BRIDGE] SIFTA server not reachable:", e.message);
      sock.sendMessage(from, {
        text: "🔴 SIFTA kernel is offline. Start whatsapp_swarm.py first.",
      });
    });

    req.write(payload);
    req.end();
  }
});

console.log("[🌊 SIFTA BRIDGE] Booting WhatsApp connection...");
