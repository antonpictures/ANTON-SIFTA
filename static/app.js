// ═══════════════════════════════════════════════════
//  ANTON-SIFTA // COMMAND INTERFACE — app.js
// ═══════════════════════════════════════════════════

// ─── Background particle canvas ──────────────────────
(function initBgCanvas() {
    const canvas = document.getElementById('bg-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    function resize() {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const particles = Array.from({ length: 60 }, () => ({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        r: Math.random() * 1.2 + 0.3,
        vx: (Math.random() - 0.5) * 0.18,
        vy: (Math.random() - 0.5) * 0.18,
        alpha: Math.random() * 0.5 + 0.1,
    }));

    function drawFrame() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        for (const p of particles) {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0) p.x = canvas.width;
            if (p.x > canvas.width)  p.x = 0;
            if (p.y < 0) p.y = canvas.height;
            if (p.y > canvas.height) p.y = 0;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(0, 229, 255, ${p.alpha})`;
            ctx.fill();
        }
        requestAnimationFrame(drawFrame);
    }
    drawFrame();
})();


// ─── Utility ──────────────────────────────────────────
function formatTime(secs) {
    if (secs <= 0) return 'EXPIRED';
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
    return `${String(h).padStart(2,'0')}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`;
}

function getEnergyColor(energy) {
    if (energy > 50) return 'var(--health-high)';
    if (energy > 20) return 'var(--health-med)';
    return 'var(--health-low)';
}

function parseStyleBadge(style) {
    return `style-${(style || 'NOMINAL').toLowerCase()}`;
}

/** Colorize a terminal output line by keyword */
function colorizeTerminalLine(txt) {
    if (!txt || txt.trim() === '') return null;

    const div = document.createElement('div');
    div.textContent = txt;

    if (/\[✅\]|\[FIX\]|Stitched and written|SWIM COMPLETE|Fixed:/i.test(txt))
        div.className = 't-fix';
    else if (/\[FAULT\]|\[ERROR\]|\[FAIL\]|invalid syntax|SyntaxError/i.test(txt))
        div.className = 't-fail';
    else if (/\[BITE\]/i.test(txt))
        div.className = 't-bite';
    else if (/\[LLM\]/i.test(txt))
        div.className = 't-llm';
    else if (/PREVIOUS SWIM TERMINATED|TERMINATED|killed/i.test(txt))
        div.className = 't-warn';
    else if (/PROCESS EXITED|CONNECTION CLOSED|== CONNECTION CLOSED ==/i.test(txt))
        div.className = 't-exit';
    else if (/Initializing swim|Swimming into/i.test(txt))
        div.className = 't-boot';

    return div;
}


// ─── Global state ─────────────────────────────────────
let dispatchSource = null;
let liveAgentCount = 0;


// ─── 1. Roster Update ─────────────────────────────────
async function fetchAgents() {
    try {
        const res = await fetch('/api/agents');
        const agents = await res.json();
        liveAgentCount = agents.length;
        document.getElementById('stat-agents-val').textContent = liveAgentCount || '0';
        updateRoster(agents);
    } catch (e) {
        console.error('Agents fetch error', e);
    }
}

function updateRoster(agents) {
    const grid = document.getElementById('roster-grid');

    if (agents.length === 0) {
        grid.innerHTML = '<div class="placeholder-card"><span class="blink">▋</span> No agents in state dir.</div>';
        return;
    }

    // Preserve existing cards to avoid full redraw flicker
    const existingIds = new Set([...grid.querySelectorAll('.agent-card')].map(c => c.dataset.id));
    const incomingIds = new Set(agents.map(a => a.id));

    // Remove stale cards
    existingIds.forEach(id => {
        if (!incomingIds.has(id)) {
            const old = grid.querySelector(`[data-id="${id}"]`);
            if (old) old.remove();
        }
    });

    agents.forEach(agent => {
        const isDead = agent.style === 'DEAD' || agent.ttl_remaining <= 0;
        let card = grid.querySelector(`[data-id="${agent.id}"]`);

        if (!card) {
            card = document.createElement('div');
            card.dataset.id = agent.id;
            grid.appendChild(card);
        }

        const energyPct = Math.min(100, Math.max(0, agent.energy));
        card.className = `agent-card${isDead ? ' dead' : ''}`;

        card.innerHTML = `
            <div class="agent-header">
                <span class="agent-face">${agent.face}</span>
                <span class="agent-id">${agent.id}</span>
                <span class="agent-style ${parseStyleBadge(agent.style)}">${agent.style}</span>
            </div>
            <div class="agent-stats">
                <span>SEQ: ${agent.seq}</span>
                <span>TTL: ${formatTime(agent.ttl_remaining)}</span>
            </div>
            <div class="energy-bar-bg">
                <div class="energy-fill" style="width:${energyPct}%; background: linear-gradient(90deg, ${getEnergyColor(energyPct)}, ${getEnergyColor(Math.max(0, energyPct - 20))});"></div>
            </div>
            ${!isDead ? `<button class="btn" onclick="openDispatchModal('${agent.id}')">▶ DISPATCH</button>` : ''}
        `;
    });
}


// ─── 2. Logs Polling ──────────────────────────────────
async function fetchLogs() {
    try {
        const res = await fetch('/api/logs?tail=100');
        const logs = await res.json();
        updateLogs(logs);
    } catch (e) {
        console.error('Logs fetch error', e);
    }
}

function updateLogs(logs) {
    const tbody = document.getElementById('logs-body');
    tbody.innerHTML = '';

    logs.forEach(log => {
        const ev = log.event || 'msg';
        let rowClass = 'log-row-default';
        if (ev === 'fix')                     rowClass = 'log-row-fix';
        else if (ev === 'fail' || ev === 'reject') rowClass = 'log-row-fail';
        else if (ev === 'scout')              rowClass = 'log-row-scout';

        const row = document.createElement('tr');
        row.className = rowClass;

        const ts = new Date(log.ts).toLocaleTimeString('en-US', { hour12: false });
        const hash = log.after_hash || log.hash || log.before_hash || '—';
        const file = log.file || log.target || '—';

        row.innerHTML = `
            <td>${ts}</td>
            <td>[${ev.toUpperCase()}]</td>
            <td><span class="log-file" title="${file}">${file}</span></td>
            <td>${hash.substring(0, 8)}</td>
        `;
        tbody.appendChild(row);
    });
}


// ─── 3. Cemetery + Quorum ─────────────────────────────
async function fetchDashData() {
    try {
        const [cemRes, qRes] = await Promise.all([
            fetch('/api/cemetery'),
            fetch('/api/quorum'),
        ]);
        updateCemetery(await cemRes.json());
        updateQuorum(await qRes.json());
    } catch (e) { console.error('Dash fetch err', e); }
}

function updateCemetery(graves) {
    const list = document.getElementById('cemetery-list');
    list.innerHTML = '';
    if (!graves.length) {
        list.innerHTML = '<li class="list-item placeholder-item">No dead agents logged.</li>';
        return;
    }
    graves.forEach(g => {
        const li = document.createElement('li');
        li.className = 'list-item';
        const ts = g.timestamp ? g.timestamp.split('T')[1]?.replace('Z', '') || g.timestamp : '—';
        li.innerHTML = `
            <strong>${g.agent_id}</strong> &mdash; ${ts}
            <div class="grave-cause">CAUSE: ${g.cause} | ENERGY: ${g.final_energy}</div>
        `;
        list.appendChild(li);
    });
}

function updateQuorum(quorumStore) {
    const list = document.getElementById('quorum-list');
    list.innerHTML = '';
    if (!quorumStore.length) {
        list.innerHTML = '<li class="list-item placeholder-item">No quorum entries.</li>';
        return;
    }
    quorumStore.forEach(q => {
        const li = document.createElement('li');
        li.className = 'list-item';
        li.innerHTML = `
            <div class="quorum-hash">${q.payload_hash.substring(0, 24)}…</div>
            <div class="quorum-ratio">
                <span>Agents: ${q.count}</span>
                <span>Threshold: ${q.threshold}</span>
            </div>
        `;
        list.appendChild(li);
    });
}


// ─── Modal & Dispatch ─────────────────────────────────
const modal     = document.getElementById('dispatch-modal');
const closeBtn  = document.getElementById('close-modal-btn');
const form      = document.getElementById('dispatch-form');
const terminal  = document.getElementById('terminal-output');

function openDispatchModal(agentId) {
    document.getElementById('modal-title').textContent = `DISPATCH AGENT [${agentId}]`;
    document.getElementById('dispatch-agent-id').value = agentId;
    terminal.innerHTML = '<div class="placeholder">&gt; Waiting for dispatch command...</div>';
    document.getElementById('target-dir').disabled     = false;
    document.getElementById('write-mode').disabled     = false;
    document.getElementById('send-swimmer-btn').disabled = false;
    modal.showModal();
}

closeBtn.onclick = () => {
    if (dispatchSource) { dispatchSource.close(); dispatchSource = null; }
    modal.close();
};


// ─── Kill Swimmer ─────────────────────────────────────
document.getElementById('kill-swimmer-btn').addEventListener('click', async () => {
    try {
        const res = await fetch('/api/dispatch/kill', { method: 'POST' });
        const data = await res.json();
        // If dispatch modal is open, append to terminal
        const termEl = document.getElementById('terminal-output');
        if (termEl) {
            const div = document.createElement('div');
            div.className = 't-warn';
            div.textContent = `[KILL] ${data.message || 'Signal sent.'}`;
            termEl.appendChild(div);
            termEl.scrollTop = termEl.scrollHeight;
        }
    } catch (e) {
        console.error('Kill failed', e);
    }
});


// ─── Settings Modal ───────────────────────────────────
const settingsModal         = document.getElementById('settings-modal');
const openSettingsBtn       = document.getElementById('open-settings-btn');
const closeSettingsModalBtn = document.getElementById('close-settings-modal');
const settingsForm          = document.getElementById('settings-form');

const providerSettings = {
    provider: localStorage.getItem('llm_provider') || 'ollama',
    model:    localStorage.getItem('llm_model')    || 'qwen3.5:0.8b',
    baseUrl:  localStorage.getItem('llm_base_url') || '',
    apiKey:   localStorage.getItem('llm_api_key')  || '',
};

let ollamaModels = [];

async function fetchOllamaModels() {
    try {
        const res  = await fetch('/api/ollama-models');
        const data = await res.json();
        ollamaModels = data.models || [];
        const sel = document.getElementById('llm-model-select');
        sel.innerHTML = '';
        if (ollamaModels.length === 0) {
            sel.innerHTML = '<option value="">No local models found</option>';
        } else {
            ollamaModels.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                if (m === providerSettings.model) opt.selected = true;
                sel.appendChild(opt);
            });
        }
    } catch (e) {
        console.error('Could not fetch Ollama models', e);
    }
}

function updateModelUI(provider) {
    const selectGroup = document.getElementById('model-select-group');
    const textGroup   = document.getElementById('model-text-group');
    if (provider === 'ollama') {
        selectGroup.style.display = '';
        textGroup.style.display   = 'none';
        fetchOllamaModels();
    } else {
        selectGroup.style.display = 'none';
        textGroup.style.display   = '';
        const textInput = document.getElementById('llm-model-text');
        if (!ollamaModels.includes(providerSettings.model)) {
            textInput.value = providerSettings.model;
        }
    }
}

// Populate settings UI on load
document.getElementById('llm-provider').value  = providerSettings.provider;
document.getElementById('llm-base-url').value  = providerSettings.baseUrl;
document.getElementById('llm-api-key').value   = providerSettings.apiKey;
updateModelUI(providerSettings.provider);

document.getElementById('llm-provider').addEventListener('change', e => updateModelUI(e.target.value));

openSettingsBtn.addEventListener('click', () => {
    updateModelUI(document.getElementById('llm-provider').value);
    settingsModal.showModal();
});
closeSettingsModalBtn.addEventListener('click', () => settingsModal.close());

settingsForm.addEventListener('submit', e => {
    e.preventDefault();
    providerSettings.provider = document.getElementById('llm-provider').value;
    providerSettings.baseUrl  = document.getElementById('llm-base-url').value;
    providerSettings.apiKey   = document.getElementById('llm-api-key').value;
    providerSettings.model    = providerSettings.provider === 'ollama'
        ? document.getElementById('llm-model-select').value
        : document.getElementById('llm-model-text').value;

    localStorage.setItem('llm_provider', providerSettings.provider);
    localStorage.setItem('llm_model',    providerSettings.model);
    localStorage.setItem('llm_base_url', providerSettings.baseUrl);
    localStorage.setItem('llm_api_key',  providerSettings.apiKey);

    settingsModal.close();
});


// ─── Dispatch Form ────────────────────────────────────
form.addEventListener('submit', async e => {
    e.preventDefault();

    const agentId  = document.getElementById('dispatch-agent-id').value;
    const targetDir = document.getElementById('target-dir').value;
    const isWrite  = document.getElementById('write-mode').checked;

    document.getElementById('target-dir').disabled      = true;
    document.getElementById('write-mode').disabled      = true;
    document.getElementById('send-swimmer-btn').disabled = true;
    terminal.innerHTML = '';

    if (dispatchSource) dispatchSource.close();

    try {
        const payload = {
            agent_id:   agentId,
            target_dir: targetDir,
            write:      isWrite,
            provider:   providerSettings.provider,
            model_name: providerSettings.model,
            base_url:   providerSettings.baseUrl,
            api_key:    providerSettings.apiKey,
        };

        const res = await fetch('/api/dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const reader  = res.body.getReader();
        const decoder = new TextDecoder('utf-8');

        let currentStreamLine = null;

        function processChunk(chunk) {
            const lines = chunk.split('\n');
            for (const l of lines) {
                if (l.startsWith('data: ')) {
                    const txt = l.substring(6);
                    
                    if (txt.startsWith('[TOKEN] ')) {
                        if (!currentStreamLine) {
                            currentStreamLine = document.createElement('div');
                            currentStreamLine.className = 't-llm';
                            terminal.appendChild(currentStreamLine);
                        }
                        currentStreamLine.textContent += txt.substring(8);
                        terminal.scrollTop = terminal.scrollHeight;
                        continue;
                    }
                    if (txt.startsWith('[THINK] ')) {
                        if (!currentStreamLine) {
                            currentStreamLine = document.createElement('div');
                            currentStreamLine.className = 't-scout';
                            terminal.appendChild(currentStreamLine);
                        }
                        currentStreamLine.textContent += txt.substring(8);
                        terminal.scrollTop = terminal.scrollHeight;
                        continue;
                    }

                    // For any normal line, clear the current streaming buffer
                    currentStreamLine = null;
                    const el  = colorizeTerminalLine(txt);
                    if (el) {
                        terminal.appendChild(el);
                        terminal.scrollTop = terminal.scrollHeight;
                    }
                }
            }
        }

        async function readStream() {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                processChunk(decoder.decode(value, { stream: true }));
            }
            const div = document.createElement('div');
            div.className = 't-exit';
            div.textContent = '— CONNECTION CLOSED —';
            terminal.appendChild(div);
            terminal.scrollTop = terminal.scrollHeight;

            // Re-enable form
            document.getElementById('target-dir').disabled      = false;
            document.getElementById('write-mode').disabled      = false;
            document.getElementById('send-swimmer-btn').disabled = false;
        }

        readStream();

    } catch (err) {
        const div = document.createElement('div');
        div.className = 't-fail';
        div.textContent = `Error initiating dispatch: ${err}`;
        terminal.appendChild(div);

        document.getElementById('target-dir').disabled      = false;
        document.getElementById('write-mode').disabled      = false;
        document.getElementById('send-swimmer-btn').disabled = false;
    }
});


// ─── Main polling loop ────────────────────────────────
async function loop() {
    fetchAgents();
    fetchDashData();
    fetchLogs();

    try {
        const r = await fetch('/api/dispatch/status');
        const s = await r.json();
        const statusEl = document.getElementById('sys-status-text');
        const killBtn  = document.getElementById('kill-swimmer-btn');

        if (s.active) {
            statusEl.textContent = 'SWIM ACTIVE';
            statusEl.classList.add('active');
            killBtn.disabled = false;
            document.querySelectorAll('.agent-card:not(.dead) .btn').forEach(b => b.disabled = true);
            // Pulse active cards
            document.querySelectorAll('.agent-card:not(.dead)').forEach(c => c.classList.add('active-swim'));
        } else {
            statusEl.textContent = 'NOMINAL';
            statusEl.classList.remove('active');
            killBtn.disabled = true;
            document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active-swim'));
            document.querySelectorAll('.agent-card:not(.dead) .btn').forEach(b => b.disabled = false);
        }
    } catch (e) { /* ignore */ }
}

// Boot
setInterval(loop, 2000);
loop();

// ─── Ledger Modal Logic ───────────────────────────────
const openLedgerBtn = document.getElementById('open-ledger-btn');
const closeLedgerBtn = document.getElementById('close-ledger-modal');
const refreshLedgerBtn = document.getElementById('refresh-ledger-btn');
const ledgerModal = document.getElementById('ledger-modal');
const fullLedgerBody = document.getElementById('full-ledger-body');

function rowClassForEvent(evt) {
    if (evt === 'fix') return 'log-row-fix';
    if (evt === 'fail' || evt === 'reject') return 'log-row-fail';
    if (evt === 'scout') return 'log-row-scout';
    if (evt === 'sos') return 'log-row-sos';
    return 'log-row-default';
}

async function fetchFullLedger() {
    try {
        const res = await fetch('/api/ledger?tail=500');
        const data = await res.json();
        
        fullLedgerBody.innerHTML = '';
        data.forEach(item => {
            const tr = document.createElement('tr');
            tr.className = rowClassForEvent(item.event);
            
            const tsDiv = document.createElement('td');
            const d = new Date(item.ts);
            tsDiv.textContent = d.toLocaleString();
            
            const evtTbody = document.createElement('td');
            evtTbody.textContent = (item.event || 'update').toUpperCase();
            
            const agentTbody = document.createElement('td');
            agentTbody.textContent = item.agent_id ? `${item.agent_id} // ${item.model||'N/A'}` : (item.model || 'SYSTEM');
            
            const fileTbody = document.createElement('td');
            fileTbody.textContent = item.file || item.target || 'N/A';
            
            const metaTbody = document.createElement('td');
            let metaTxt = '';
            if (item.hash) metaTxt += `HASH: ${item.hash} `;
            if (item.after_hash) metaTxt += `${item.before_hash.substring(0,8)} → ${item.after_hash.substring(0,8)}`;
            if (item.reason) metaTxt += `ERR: ${item.reason}`;
            if (item.status) metaTxt += `STATUS: ${item.status}`;
            metaTbody.textContent = metaTxt;
            
            tr.appendChild(tsDiv);
            tr.appendChild(evtTbody);
            tr.appendChild(agentTbody);
            tr.appendChild(fileTbody);
            tr.appendChild(metaTbody);
            fullLedgerBody.appendChild(tr);
        });
    } catch(err) {
        fullLedgerBody.innerHTML = `<tr><td colspan="5" style="color:var(--health-low);">Error loading ledger: ${err}</td></tr>`;
    }
}

openLedgerBtn.addEventListener('click', () => {
    ledgerModal.showModal();
    fetchFullLedger();
});

closeLedgerBtn.addEventListener('click', () => {
    ledgerModal.close();
});

refreshLedgerBtn.addEventListener('click', () => {
    fullLedgerBody.innerHTML = `<tr><td colspan="5" style="color:var(--text-muted); text-align:center;">Polling ledger data...</td></tr>`;
    fetchFullLedger();
});

loop();
