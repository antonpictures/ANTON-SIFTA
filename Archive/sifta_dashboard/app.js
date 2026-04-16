/**
 * SIFTA Dashboard Application Logic
 * Polls API dynamically and updates the DOM using Vanilla JS.
 */

const API_BASE = "http://127.0.0.1:8000";

// --- STATE ---
let lastChatId = 0;
let isFirstLoad = true;

// --- NPU ENERGY ROOF ---
async function fetchAgents() {
    try {
        const res = await fetch(`${API_BASE}/api/agents?show_detectives=true`);
        if (!res.ok) return;
        const agents = await res.json();
        
        const grid = document.getElementById('npu-grid');
        grid.innerHTML = ''; // clear
        
        let totalStgm = 0;

        agents.forEach(agent => {
            totalStgm += (agent.stgm_balance || 0);

            const card = document.createElement('div');
            card.className = 'agent-card';
            
            const e = agent.energy || 0;
            const styleLabel = agent.style || 'NOMINAL';
            
            card.innerHTML = `
                <div class="agent-head">
                    <span class="agent-id">${agent.id.replace('0X', '') || 'UNKNOWN'}</span>
                    <span class="agent-face">${agent.face || '[O_O]'}</span>
                </div>
                <div class="energy-bar-wrap">
                    <div class="energy-bar" style="width: ${e}%"></div>
                </div>
                <div class="agent-stats">
                    <span>${styleLabel}</span>
                    <span class="stgm-val">${(agent.stgm_balance || 0).toFixed(2)} STGM</span>
                </div>
            `;
            grid.appendChild(card);
        });

        document.getElementById('stgm-total').innerText = `${totalStgm.toFixed(3)} STGM POOL`;

    } catch (err) {
        console.error("Agent Sync Error:", err);
    }
}

// --- LIVE Q&A MATRIX ---
async function fetchChat() {
    try {
        // Polling existing messenger thread from ledger_db
        const res = await fetch(`${API_BASE}/messenger/thread?limit=50`);
        if (!res.ok) return;
        const data = await res.json();
        
        const viewport = document.getElementById('chat-viewport');
        let added = false;

        data.messages.forEach(msg => {
            if (msg.id > lastChatId) {
                lastChatId = msg.id;
                added = true;
                
                const isUser = msg.from === "ARCHITECT_DESKTOP" || msg.from.includes("IDE") || msg.from === "HUMAN";
                
                const d = new Date(msg.ts * 1000);
                const timeStr = d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

                const bub = document.createElement('div');
                bub.className = `chat-bubble ${isUser ? 'user' : 'bot'}`;
                
                bub.innerHTML = `
                    <div class="chat-meta">${msg.from} • ${timeStr}</div>
                    <div class="chat-text">${formatTextToHtml(msg.body)}</div>
                `;
                viewport.appendChild(bub);
            }
        });

        if (added && !isFirstLoad) {
            viewport.scrollTop = viewport.scrollHeight;
        } else if (isFirstLoad) {
            setTimeout(() => { viewport.scrollTop = viewport.scrollHeight; }, 100);
            isFirstLoad = false;
        }

    } catch (err) {
        console.warn("Chat sync warning:", err);
    }
}

function formatTextToHtml(text) {
    if (!text) return "";
    let clean = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    clean = clean.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    clean = clean.replace(/```(.*?)```/gs, "<pre style='background:rgba(0,0,0,0.4); padding:10px; border-radius:8px; overflow-x:auto; margin-top:5px; font-family:var(--font-mono); color:#c0caf5;'>$1</pre>");
    return clean;
}

async function transmitMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;
    
    input.value = '';
    
    // We send payload to messenger/send. This simulates the architectural input.
    const payload = {
        from_id: "[ARCHITECT::IF:WEB]",
        to_id: "SWARM",
        body: text
    };
    
    try {
        await fetch(`${API_BASE}/messenger/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        fetchChat(); // Instant poll
    } catch (e) {
        console.error("Transmission failed", e);
    }
}

document.getElementById('send-btn').addEventListener('click', transmitMessage);
document.getElementById('chat-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') transmitMessage();
});

// --- GENETICS & BOUNTIES LOG ---
async function fetchLedger() {
    try {
        const res = await fetch(`${API_BASE}/api/ledger?tail=15`);
        if (!res.ok) return;
        const logs = await res.json();
        
        const viewport = document.getElementById('ledger-viewport');
        viewport.innerHTML = '';
        
        logs.forEach(log => {
            const d = new Date(log.timestamp * 1000);
            const timeStr = d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
            
            const r = document.createElement('div');
            r.className = 'ledger-row';
            
            const amt = log.amount ? `+${log.amount.toFixed(2)}` : '0.00';
            const reason = log.reason || log.tx_type || 'Unknown';
            
            r.innerHTML = `
                <div class="l-time">${timeStr}</div>
                <div class="l-agent">${log.agent_id || 'SYS'}</div>
                <div class="l-reason">${reason}</div>
                <div class="l-amount">${amt}</div>
            `;
            viewport.appendChild(r);
        });
        
    } catch (err) {
        console.warn("Ledger sync warning", err);
    }
}

// --- BOOT ---
async function bootSequence() {
    fetchAgents();
    fetchChat();
    fetchLedger();
    
    setInterval(fetchAgents, 5000); // 5 sec
    setInterval(fetchChat, 2000);   // 2 sec
    setInterval(fetchLedger, 5000); // 5 sec
}

bootSequence();
