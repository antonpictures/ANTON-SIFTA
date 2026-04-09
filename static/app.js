// ═══════════════════════════════════════════════════
//  ANTON-SIFTA // COMMAND INTERFACE — app.js
// ═══════════════════════════════════════════════════
let activeDispatchAgent = null;


// ─── Panel Toggle Functions (topbar) ─────────────────
// All drawers start closed — Fleet Overview is the default view.
function toggleDrawer(drawerId, btnId) {
    const drawer = document.getElementById(drawerId);
    const btn    = document.getElementById(btnId);
    if (!drawer) return;

    const isOpen = drawer.hasAttribute('open');

    if (isOpen) {
        drawer.removeAttribute('open');
        if (btn) { btn.classList.remove('active'); }
    } else {
        drawer.setAttribute('open', '');
        if (btn) { btn.classList.add('active'); }
        // Scroll drawer into view smoothly
        setTimeout(() => drawer.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80);
    }
    // Fleet button goes inactive when any drawer opens, back to active if all closed
    _syncFleetBtn();
}

function activateFleetPanel() {
    // Close all drawers, scroll fleet list to top
    ['drawer-territory', 'drawer-cemetery', 'drawer-quorum'].forEach(id => {
        const d = document.getElementById(id);
        if (d) d.removeAttribute('open');
    });
    ['panel-btn-territory', 'panel-btn-cemetery', 'panel-btn-quorum'].forEach(id => {
        const b = document.getElementById(id);
        if (b) b.classList.remove('active');
    });
    const fleetBtn = document.getElementById('panel-btn-fleet');
    if (fleetBtn) fleetBtn.classList.add('active');
    const fleetList = document.getElementById('fleet-list');
    if (fleetList) fleetList.scrollTop = 0;
}

function _syncFleetBtn() {
    const anyOpen = ['drawer-territory', 'drawer-cemetery', 'drawer-quorum']
        .some(id => document.getElementById(id)?.hasAttribute('open'));
    const fleetBtn = document.getElementById('panel-btn-fleet');
    if (fleetBtn) fleetBtn.classList.toggle('active', !anyOpen);
}

// ─── Agent Card Drawer Toggle ─────────────────────────
function selectAgentForDispatch(agentId) {
    // Reveal raw telemetry drawer
    const drawer  = document.getElementById(`ac-drawer-${agentId}`);
    const chevron = document.getElementById(`ac-chevron-icon-${agentId}`);
    const card    = document.querySelector(`[data-id="${agentId}"]`);
    if (drawer) {
        const isOpen = drawer.style.display !== 'none';
        
        // Always ensure the drawer opens if we are selecting a new agent
        // If it's the exact same agent, let it toggle
        const shouldBeOpen = (activeDispatchAgent !== agentId) ? true : !isOpen;
        
        drawer.style.display = shouldBeOpen ? 'block' : 'none';
        if (chevron) chevron.textContent = shouldBeOpen ? '▴' : '▾';
        if (card)    card.classList.toggle('ac-expanded', shouldBeOpen);
    }
    
    // Update Central Dispatch Selection
    activeDispatchAgent = agentId;
    
    // Refresh card highlighting
    document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('ac-selected'));
    if (card) card.classList.add('ac-selected');
    
    // Populate Mission Control TV
    const dcConsole = document.getElementById('central-dispatch-console');
    const dcAgent   = document.getElementById('dc-active-agent');
    if (dcConsole && dcAgent) {
        dcConsole.classList.remove('disabled');
        const styleText = document.getElementById(`style-${agentId}`)?.textContent || 'UNKNOWN';
        dcAgent.textContent = `${agentId} [${styleText}]`;
        
        // Reset terminal output in console
        const terminal = document.getElementById('dc-terminal');
        if (terminal) {
            terminal.innerHTML = `<div class="placeholder t-boot">&gt; Agent ${agentId} selected.<br>&gt; WAITING FOR MISSION PARAMETERS... <span class="blink">▋</span></div>`;
        }
        
        const sendBtn = document.getElementById('dc-send-btn');
        if (sendBtn) sendBtn.disabled = false;
    }
}


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
window.copyAgentBody = function(agentId) {
    const rawEl   = document.getElementById(`raw-${agentId}`);
    const labelEl = document.getElementById(`copy-label-${agentId}`);
    const text = rawEl ? rawEl.textContent.trim() : '';
    if (!text) return;
    const doCopy = (str) => {
        if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(str);
        const ta = document.createElement('textarea');
        ta.value = str; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0;';
        document.body.appendChild(ta); ta.focus(); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta);
        return Promise.resolve();
    };
    doCopy(text).then(() => {
        if (labelEl) {
            const old = labelEl.textContent;
            labelEl.textContent = '\u2713'; labelEl.style.color = 'var(--health-high)';
            setTimeout(() => { labelEl.textContent = old; labelEl.style.color = ''; }, 1500);
        }
    }).catch(err => console.error('Failed to copy:', err));
};


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
        const checkbox = document.getElementById('show-hidden-agents');
        const showDetectives = checkbox ? checkbox.checked : false;
        const res = await fetch(`/api/agents?show_detectives=${showDetectives}`);
        const agents = await res.json();
        liveAgentCount = agents.length;
        document.getElementById('stat-agents-val').textContent = liveAgentCount || '0';
        updateRoster(agents);
        updateFleet(agents);
        
        if (activeDispatchAgent === null && agents.length > 0) {
            // Find lowest energy agent to be the default worker
            const defaultAgent = agents.reduce((prev, curr) => (prev.energy < curr.energy) ? prev : curr);
            selectAgentForDispatch(defaultAgent.id);
        }
        
        updateWallet(agents);
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

    // Clear bootstrap placeholder once real data arrives
    const placeholder = grid.querySelector('.placeholder-card');
    if (placeholder) placeholder.remove();

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

            card.innerHTML = `
                <div class="ac-top" onclick="selectAgentForDispatch('${agent.id}')">
                    <div class="ac-face-wrap">
                        <span class="ac-face" id="face-${agent.id}"></span>
                    </div>
                    <div class="ac-identity">
                        <div class="ac-name">${agent.id}</div>
                        <div class="ac-meta">
                            <span id="seq-${agent.id}"></span>
                            <span id="ttl-${agent.id}"></span>
                        </div>
                    </div>
                    <span class="agent-style" id="style-${agent.id}"></span>
                </div>

                <div class="ac-middle">
                    <div class="ac-hash-pill">
                        <span class="ac-hash-icon">#</span>
                        <span class="ac-hash-text" id="hash-${agent.id}">—</span>
                        <button class="ac-copy-btn" onclick="copyAgentBody('${agent.id}')" title="Copy full body">
                            <span id="copy-label-${agent.id}">⎘</span>
                        </button>
                    </div>
                    <div class="ac-energy-right">
                        <span class="ac-energy-zap">⚡</span>
                        <span class="ac-energy-num" id="energy-num-${agent.id}"></span>
                    </div>
                </div>
                <div class="energy-bar-bg">
                    <div class="energy-fill" id="energy-${agent.id}"></div>
                </div>

                <!-- Expandable Drawer -->
                <div class="ac-drawer" id="ac-drawer-${agent.id}" style="display:none;">
                    <div class="ac-drawer-label">⬛ RAW TELEMETRY</div>
                    <div class="agent-raw-body" id="raw-${agent.id}"></div>
                </div>

                <!-- Chevron footer -->
                <div class="ac-chevron" id="ac-chevron-${agent.id}" onclick="selectAgentForDispatch('${agent.id}')">
                    <span id="ac-chevron-icon-${agent.id}">▾</span>
                </div>
            `;
        }

        // Apply dynamically changing attributes natively
        card.className = `agent-card${isDead ? ' dead' : ''}${agent.id === activeDispatchAgent ? ' ac-selected' : ''}`;
        
        card.querySelector(`#face-${agent.id}`).textContent = agent.face;

        const styleBadge = card.querySelector(`#style-${agent.id}`);
        styleBadge.className = `agent-style ${parseStyleBadge(agent.style)}`;
        styleBadge.textContent = agent.style;

        card.querySelector(`#seq-${agent.id}`).textContent = `SEQ: ${agent.seq}`;
        card.querySelector(`#ttl-${agent.id}`).textContent = `TTL: ${formatTime(agent.ttl_remaining)}`;

        const energyPct = Math.min(100, Math.max(0, agent.energy));
        const eFill = card.querySelector(`#energy-${agent.id}`);
        eFill.style.width = `${energyPct}%`;
        eFill.style.background = `linear-gradient(90deg, ${getEnergyColor(energyPct)}, ${getEnergyColor(Math.max(0, energyPct - 20))})`;

        const rawEl = card.querySelector(`#raw-${agent.id}`);
        if (rawEl) {
            const body = agent.raw || '— awaiting rehydration —';
            rawEl.textContent = body.replace(/::/g, '\n::').replace(/^(\n)/, '');
        }

        // Hash pill: first6•••last4
        const hashEl = card.querySelector(`#hash-${agent.id}`);
        if (hashEl) {
            const h = agent.hash_chain && agent.hash_chain.length
                ? agent.hash_chain[agent.hash_chain.length - 1]
                : (agent.raw || '').match(/::H\[([a-f0-9]+)/)?.[1] || '';
            hashEl.textContent = h.length > 10
                ? `${h.substring(0, 6)}•••${h.substring(h.length - 4)}`
                : (h || '——');
        }

        // Energy number text
        const enNumEl = card.querySelector(`#energy-num-${agent.id}`);
        if (enNumEl) enNumEl.textContent = `${energyPct}%`;

        const btnC = card.querySelector(`#btn-container-${agent.id}`);
        if (btnC) btnC.style.display = isDead ? 'none' : 'block';
    });
}


// ─── 1b. Fleet Overview (Right Panel — Steve Jobs Edition) ───────
function getFleetStyleColor(style) {
    const s = (style || 'NOMINAL').toUpperCase();
    if (s === 'NOMINAL')   return { color: 'var(--health-high)',   border: 'rgba(0,230,118,0.4)' };
    if (s === 'PATROL')    return { color: '#40c4ff',              border: 'rgba(64,196,255,0.4)' };
    if (s === 'DORMANT')   return { color: 'var(--text-muted)',    border: 'rgba(255,255,255,0.15)' };
    if (s === 'MEDBAY')    return { color: '#b388ff',              border: 'rgba(179,136,255,0.4)' };
    if (s === 'CORRUPTED') return { color: 'var(--health-med)',    border: 'rgba(255,202,40,0.4)' };
    if (s === 'CRITICAL')  return { color: 'var(--health-low)',    border: 'rgba(255,23,68,0.4)' };
    if (s === 'GHOST')     return { color: 'var(--text-muted)',    border: 'rgba(255,255,255,0.08)' };
    if (s === 'VISIONARY') return { color: '#ffab40',              border: 'rgba(255,171,64,0.4)' };
    if (s === 'DEAD')      return { color: 'var(--text-muted)',    border: 'rgba(255,255,255,0.06)' };
    return                         { color: 'var(--cyan)',          border: 'rgba(0,229,255,0.3)' };
}

function updateFleet(agents) {
    const container = document.getElementById('fleet-list');
    const countEl   = document.getElementById('fleet-total-count');
    if (!container) return;

    if (agents.length === 0) {
        container.innerHTML = '<div class="placeholder-card">No agents in state dir.</div>';
        if (countEl) countEl.textContent = '0';
        return;
    }

    if (countEl) countEl.textContent = agents.length + ' ACTIVE';

    // Build rows, preserving existing DOM to avoid flicker
    const existingRows = new Map(
        [...container.querySelectorAll('.fleet-agent-row')].map(r => [r.dataset.id, r])
    );
    const incoming = new Set(agents.map(a => a.id));

    // Remove stale
    existingRows.forEach((el, id) => { if (!incoming.has(id)) el.remove(); });
    // Remove bootstrap placeholder
    const ph = container.querySelector('.placeholder-card');
    if (ph) ph.remove();

    agents.forEach((agent, idx) => {
        let row = existingRows.get(agent.id);
        const isGhost = agent.style === 'GHOST' || agent.style === 'DEAD';
        const energy  = Math.min(100, Math.max(0, agent.energy || 0));
        const styleInfo = getFleetStyleColor(agent.style);
        const energyColor = getEnergyColor(energy);
        const face = agent.face || '[?]';
        const rawBody = agent.raw || '';

        if (!row) {
            row = document.createElement('div');
            row.className = 'fleet-agent-row';
            row.dataset.id = agent.id;
            row.title = 'Click to copy body to clipboard';
            row.addEventListener('click', () => {
                const body = row.dataset.raw || '';
                if (!body) return;
                // HTTP-safe clipboard: navigator.clipboard only works on HTTPS/localhost with permissions.
                // Fallback: textarea trick works everywhere.
                const copyText = (text) => {
                    if (navigator.clipboard && window.isSecureContext) {
                        return navigator.clipboard.writeText(text);
                    }
                    // Fallback for http://
                    const ta = document.createElement('textarea');
                    ta.value = text;
                    ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0;';
                    document.body.appendChild(ta);
                    ta.focus(); ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    return Promise.resolve();
                };
                copyText(body).then(() => {
                    row.classList.remove('copied');
                    void row.offsetWidth;
                    row.classList.add('copied');
                    const hint = row.querySelector('.fleet-copy-hint');
                    if (hint) {
                        const oldText = hint.textContent;
                        hint.textContent = 'COPIED ✓';
                        hint.style.color = 'var(--health-high)';
                        setTimeout(() => {
                            hint.textContent = oldText;
                            hint.style.color = '';
                        }, 1400);
                    }
                }).catch(() => {});
            });
            container.appendChild(row);
        }
        // Always update the live raw body on the element
        row.dataset.raw = rawBody;

        row.style.opacity = isGhost ? '0.35' : '1';
        row.innerHTML = `
            <span class="fleet-face" style="${isGhost ? 'filter:grayscale(1);' : ''}">${face}</span>
            <div class="fleet-info">
                <div class="fleet-name">${agent.id}</div>
                <div class="fleet-meta">
                    <div class="fleet-energy-track">
                        <div class="fleet-energy-fill" style="width:${energy}%; background:${energyColor};"></div>
                    </div>
                    <span class="fleet-energy-label">${energy}%</span>
                    <span class="fleet-style-badge" style="color:${styleInfo.color}; border-color:${styleInfo.border};">${agent.style || 'NOMINAL'}</span>
                </div>
            </div>
            <span class="fleet-copy-hint">⎘ BODY</span>
        `;

        // Re-attach click (since innerHTML replaced the handler's element children but not the row itself)
        // The click handler on row itself survives — innerHTML only replaces children, not the element.
    });

    // Ensure order matches agents array
    agents.forEach((agent, idx) => {
        const row = container.querySelector(`[data-id="${agent.id}"]`);
        if (row && container.children[idx] !== row) {
            container.insertBefore(row, container.children[idx] || null);
        }
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

    if (logs.length === 0) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `<td colspan="4" style="color:var(--text-muted); text-align:center; padding: 2rem; font-family:var(--font-mono); font-size:0.8rem; letter-spacing:0.06em;">⬡ No swim events logged. Deploy a swimmer to generate telemetry.</td>`;
        tbody.appendChild(emptyRow);
        return;
    }

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
    const badge = document.getElementById('cemetery-badge');
    list.innerHTML = '';
    if (badge) badge.textContent = graves.length || '';
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
    const badge = document.getElementById('quorum-badge');
    list.innerHTML = '';
    if (badge) badge.textContent = quorumStore.length || '';
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


// ─── Inline Dispatch & Pickle Logic ──────────────────────
let activeDispatchSources = {}; // map of agentId -> EventSource

function toggleDispatch(agentId) {
    const deck = document.getElementById('command-deck');
    const deckContent = document.getElementById('command-deck-content');
    
    // If clicking same agent, toggle off
    if (deck.dataset.activeAgent === agentId) {
        deck.style.display = 'none';
        deck.dataset.activeAgent = '';
        const oldPanel = document.getElementById(`dispatch-panel-${agentId}`);
        const cardContainer = document.getElementById(`btn-container-${agentId}`);
        if (oldPanel && cardContainer) {
            oldPanel.style.display = 'none';
            oldPanel.classList.remove('horizontal-dispatch');
            cardContainer.appendChild(oldPanel);
        }
        return;
    }
    
    // If another is active, return it first
    if (deck.dataset.activeAgent) {
        const oldId = deck.dataset.activeAgent;
        const oldPanel = document.getElementById(`dispatch-panel-${oldId}`);
        const cardContainer = document.getElementById(`btn-container-${oldId}`);
        if (oldPanel && cardContainer) {
            oldPanel.style.display = 'none';
            oldPanel.classList.remove('horizontal-dispatch');
            cardContainer.appendChild(oldPanel);
        }
    }
    
    // Activate new
    deck.dataset.activeAgent = agentId;
    const card = document.querySelector(`[data-id="${agentId}"]`);
    const panel = document.getElementById(`dispatch-panel-${agentId}`);
    
    if (card && panel) {
        const face = card.querySelector('.agent-face').textContent;
        const style = card.querySelector('.agent-style').textContent;
        const rawHTML = card.querySelector('.agent-raw-body').innerHTML;
        
        deckContent.innerHTML = `
            <div class="deck-left">
                <div class="deck-title"><span class="deck-face">${face}</span> ${agentId} <span class="deck-style ${parseStyleBadge(style)}">${style}</span></div>
                <div class="deck-raw">${rawHTML}</div>
            </div>
            <div class="deck-right" id="deck-panel-mount"></div>
        `;
        
        panel.style.display = 'flex';
        panel.classList.add('horizontal-dispatch');
        document.getElementById('deck-panel-mount').appendChild(panel);
        deck.style.display = 'flex';
    }
}

async function openInlinePicker(mode, agentId) {
    try {
        const res = await fetch(`/api/pick-path?mode=${mode}`);
        const data = await res.json();
        if (data.ok && data.path) {
            // Handle central dispatch input box vs individual rows
            const inputId = agentId === 'dc' ? 'dc-target' : `target-${agentId}`;
            const input = document.getElementById(inputId);
            if (input) {
                const clean = data.path.trim().replace(/^['"]|['"]$/g, '');
                input.value = clean;
            }
        }
    } catch (e) {
        console.error('Picker error', e);
    }
}


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


// ─── Central Dispatch Submission ────────────────────────
async function sendSwimmerCentral() {
    if (!activeDispatchAgent) return;
    
    const targetDir  = document.getElementById('dc-target').value;
    const isWrite    = document.getElementById('dc-write').checked;
    const terminal   = document.getElementById('dc-terminal');
    const sendBtn    = document.getElementById('dc-send-btn');
    const abortBtn   = document.getElementById('dc-abort-btn');
    const scrollHint = document.getElementById('dc-scroll-hint');
    
    document.getElementById('dc-target').disabled = true;
    document.getElementById('dc-write').disabled  = true;
    sendBtn.disabled  = true;
    abortBtn.disabled = false; // ARM the abort button
    
    terminal.innerHTML = '';

    // ── Smart scroll: only chase stream when user is AT the bottom ─────
    let userScrolledUp = false;
    const SCROLL_THRESHOLD = 60; // px from bottom

    function smartScroll() {
        if (!userScrolledUp) terminal.scrollTop = terminal.scrollHeight;
    }

    terminal.addEventListener('scroll', () => {
        const dist = terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight;
        userScrolledUp = dist > SCROLL_THRESHOLD;
        if (scrollHint) scrollHint.classList.toggle('visible', userScrolledUp);
    }, { passive: true });

    try {
        const payload = {
            agent_id:   activeDispatchAgent,
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
                        smartScroll();
                        continue;
                    }
                    if (txt.startsWith('[THINK] ')) {
                        if (!currentStreamLine) {
                            currentStreamLine = document.createElement('div');
                            currentStreamLine.className = 't-scout';
                            terminal.appendChild(currentStreamLine);
                        }
                        currentStreamLine.textContent += txt.substring(8);
                        smartScroll();
                        continue;
                    }

                    // For any normal line, clear the current streaming buffer
                    currentStreamLine = null;
                    const el  = colorizeTerminalLine(txt);
                    if (el) {
                        terminal.appendChild(el);
                        smartScroll();
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
            smartScroll();

            document.getElementById('dc-target').disabled = false;
            document.getElementById('dc-write').disabled  = false;
            sendBtn.disabled  = false;
            abortBtn.disabled = true; // DISARM abort after completion
        }

        readStream();

    } catch (err) {
        const div = document.createElement('div');
        div.className = 't-fail';
        div.textContent = `Error initiating dispatch: ${err}`;
        terminal.appendChild(div);

        document.getElementById('dc-target').disabled = false;
        document.getElementById('dc-write').disabled  = false;
        sendBtn.disabled  = false;
        abortBtn.disabled = true;
    }
}


// ─── Abort Active Swimmer ────────────────────────
async function abortSwimmer() {
    const terminal  = document.getElementById('dc-terminal');
    const sendBtn   = document.getElementById('dc-send-btn');
    const abortBtn  = document.getElementById('dc-abort-btn');

    abortBtn.disabled = true;
    abortBtn.textContent = '■ ABORTING...';

    try {
        const res  = await fetch('/api/dispatch/kill', { method: 'POST' });
        const data = await res.json();

        const div = document.createElement('div');
        div.className = 't-warn';
        div.textContent = data.killed
            ? '■ SWIMMER TERMINATED BY OPERATOR'
            : `■ ${data.message || 'No active swimmer'}`;
        if (terminal) terminal.appendChild(div);
        if (terminal) terminal.scrollTop = terminal.scrollHeight;
    } catch (e) {
        console.error('Abort failed', e);
    }

    if (abortBtn) abortBtn.textContent = '■ ABORT';
    document.getElementById('dc-target').disabled = false;
    document.getElementById('dc-write').disabled  = false;
    if (sendBtn) sendBtn.disabled = !activeDispatchAgent;
}


// ─── Main polling loop ────────────────────────────────
async function loop() {
    fetchAgents();
    fetchDashData();
    fetchLogs();
    updateTerritory();

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
let systemHovered = false;
document.addEventListener('DOMContentLoaded', () => {
    // Bind to the stable parent container, not the inner list that gets destroyed
    const stableContainer = document.getElementById('drawer-territory');
    if (stableContainer) {
        stableContainer.addEventListener('mouseenter', () => systemHovered = true);
        stableContainer.addEventListener('mouseleave', () => systemHovered = false);
    }
});

setInterval(loop, 2000);
loop();

async function updateTerritory() {
    if (systemHovered) return; // Freeze UI redraws if user is hovering to click buttons
    try {
        const res = await fetch('/api/territory');
        if (!res.ok) return;
        const data = await res.json();
        const list = document.getElementById('territory-list');
        if (!list) return;
        
        if (!data.territories || data.territories.length === 0) {
            list.innerHTML = '<div class="list-item placeholder-item">Territory is unmarked.</div>';
            return;
        }

        list.innerHTML = '';
        data.territories.forEach(terr => {
            const el = document.createElement('div');
            el.className = `territory-item status-${terr.status}`;
            
            const opacity = Math.max(0.3, terr.max_potency);
            el.style.opacity = opacity;
            
            const badges = terr.agents.map(a => `<span class="t-badge">${a}</span>`).join('');
            const statusBadge = terr.status === 'BLEEDING' 
                ? `<span class="t-badge bleeding">🩸 BLEEDING x${terr.bleeding_count}</span>` 
                : `<span class="t-badge">✅ CLEAN</span>`;

            const dangerStr = terr.danger_score > 0 
                ? `<span class="t-badge bleeding">⚡ ${terr.danger_score}</span>` 
                : '';

            let timeStr = 'Unknown';
            if (terr.last_visited) {
                const date = new Date(terr.last_visited);
                timeStr = date.toLocaleTimeString([], { hour12: false });
            }

            el.innerHTML = `
                <div class="territory-path" title="${terr.path}" style="display:flex; justify-content:space-between; align-items:center;">
                    <span>📁 ${terr.path.length > 25 ? '...' + terr.path.slice(-25) : terr.path}</span>
                    <div style="display:flex; align-items:center;">
                        <span class="territory-time">${timeStr}</span>
                        <button class="btn btn-secondary" style="margin-left:8px; padding:2px 5px; font-size:0.75em; opacity:0.7;" onclick="event.stopPropagation(); window.forgetTerritory('${terr.full_path || terr.path}')" title="Evaporate Swarm memory (Delete .sifta marker)">✕</button>
                    </div>
                </div>
                <div class="territory-badges">
                    ${statusBadge}
                    ${dangerStr}
                    ${badges}
                </div>
            `;
            // Click to read the graffiti
            el.addEventListener('click', () => showScarModal(terr.full_path || terr.path));
            list.appendChild(el);
        });
    } catch (err) {
        // ignore verbose polling errors
    }
}

window.forgetTerritory = async function(path) {
    try {
        const res = await fetch('/api/territory', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        if (data.ok) {
            updateTerritory();
        } else {
            console.error("Failed to delete territory:", data.error);
            alert("Failed to forget territory: " + data.error);
        }
    } catch(e) {
        console.error('Network error forgetting territory', e);
    }
};

window.emptyTrash = async function() {
    if (!confirm(`Are you sure you want to permanently delete all contents inside the Recycle Bin? This cannot be undone.`)) return;
    try {
        const res = await fetch('/api/trash', { method: 'DELETE' });
        const data = await res.json();
        if (data.ok) {
            alert("Trash successfully emptied.");
        } else {
            alert("Failed to empty trash: " + data.error);
        }
    } catch(e) {
        console.error('Network error emptying trash', e);
    }
};

// ─── Scar Reader Modal ───────────────────────────────
const scarModal   = document.getElementById('scar-modal');
const scarTitle   = document.getElementById('scar-modal-title');
const scarMdEl    = document.getElementById('scar-md-content');
const scarListEl  = document.getElementById('scar-file-list');
const closeScarBtn = document.getElementById('close-scar-modal');

closeScarBtn.addEventListener('click', () => scarModal.close());
scarModal.addEventListener('click', e => { if (e.target === scarModal) scarModal.close(); });

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function switchScarTab(tab) {
    const chronicle = document.getElementById('scar-panel-chronicle');
    const raw       = document.getElementById('scar-panel-raw');
    const tabC      = document.getElementById('tab-chronicle');
    const tabR      = document.getElementById('tab-raw');
    if (tab === 'chronicle') {
        chronicle.style.display = 'block';
        raw.style.display = 'none';
        tabC.classList.add('active');
        tabR.classList.remove('active');
    } else {
        chronicle.style.display = 'none';
        raw.style.display = 'block';
        tabC.classList.remove('active');
        tabR.classList.add('active');
    }
}

function buildChronicleTimeline(scarFiles) {
    if (!scarFiles || scarFiles.length === 0) {
        return '<div class="chronicle-empty">⬡ Territory is unmarked. No agents have swum here yet.</div>';
    }

    // Parse + sort newest first
    const parsed = scarFiles.map(sf => {
        try { return { ...JSON.parse(sf.content), _raw_name: sf.name, _mtime: sf.modified }; }
        catch { return null; }
    }).filter(Boolean).sort((a, b) => b._mtime - a._mtime);

    const ACTION_META = {
        REPAIR_SUCCESS:  { icon: '✅', cls: 'ca-fix',    label: 'REPAIR' },
        SCOUT:           { icon: '👁', cls: 'ca-scout',  label: 'SCOUT' },
        BLEEDING:        { icon: '🩸', cls: 'ca-fail',   label: 'BLEEDING' },
        UNRESOLVED:      { icon: '🩸', cls: 'ca-fail',   label: 'UNRESOLVED' },
        RESOLVED:        { icon: '✅', cls: 'ca-fix',    label: 'RESOLVED' },
        HANDOFF:         { icon: '📡', cls: 'ca-radio',  label: 'HANDOFF' },
    };

    return parsed.map(s => {
        const action   = s.action || s.stigmergy?.status || 'VISIT';
        const meta     = ACTION_META[action] || { icon: '💨', cls: 'ca-default', label: action };
        const ts       = s.scent?.last_visited
            ? new Date(s.scent.last_visited).toLocaleTimeString([], { hour12: false })
            : '—';
        const face     = escapeHtml(s.face     || '[?]');
        const agentId  = escapeHtml(s.agent_id || '?');
        const mark     = escapeHtml(s.mark || s.stigmergy?.reason?.message || '');
        const found    = escapeHtml((s.history?.[0]?.found) || '');
        const danger   = s.scent?.danger_level || '';
        const potency  = s.scent?.potency != null ? Math.round(s.scent.potency * 100) : null;

        const dangerBadge = danger && danger !== 'SAFE'
            ? `<span class="chr-badge chr-danger">⚡ ${danger}</span>` : '';
        const potencyBar  = potency != null
            ? `<div class="chr-potency-bg"><div class="chr-potency-fill" style="width:${potency}%"></div></div>` : '';

        return `
        <div class="chronicle-entry ${meta.cls}">
            <div class="chr-spine"></div>
            <div class="chr-body">
                <div class="chr-header">
                    <span class="chr-face">${face}</span>
                    <span class="chr-agent">${agentId}</span>
                    <span class="chr-action-badge ${meta.cls}">${meta.icon} ${meta.label}</span>
                    ${dangerBadge}
                    <span class="chr-ts">${ts}</span>
                </div>
                ${mark ? `<div class="chr-mark">${mark}</div>` : ''}
                ${found ? `<div class="chr-found">FOUND: ${found}</div>` : ''}
                ${potencyBar}
            </div>
        </div>`;
    }).join('');
}

async function showScarModal(folderPath) {
    scarTitle.textContent = `📁 ${folderPath}`;
    scarMdEl.innerHTML    = '<div class="chronicle-empty">⬡ Loading swarm records...</div>';
    scarListEl.innerHTML  = '';
    switchScarTab('chronicle');
    scarModal.showModal();

    try {
        const res  = await fetch(`/api/scar_contents?folder=${encodeURIComponent(folderPath)}`);
        const data = await res.json();

        // Chronicle tab — render structured timeline from scar JSON data
        scarMdEl.innerHTML = buildChronicleTimeline(data.scar_files);

        // Raw scars tab
        if (data.scar_files && data.scar_files.length) {
            scarListEl.innerHTML = data.scar_files.map(sf => `
                <div class="scar-file-item">
                    <div class="scar-file-name">🧬 ${escapeHtml(sf.name)}</div>
                    <pre class="scar-file-body">${escapeHtml(sf.content)}</pre>
                </div>
            `).join('');
        } else {
            scarListEl.innerHTML = '<div class="scar-empty">No .scar files found.</div>';
        }
    } catch (err) {
        scarMdEl.innerHTML = `<div class="chronicle-empty" style="color:var(--health-low)">Error loading scars: ${escapeHtml(String(err))}</div>`;
    }
}

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

// ─── Wallet System ────────────────────────────────────
const walletModal = document.getElementById('wallet-modal');
const openWalletBtn = document.getElementById('open-wallet-btn');
const walletTotalBalance = document.getElementById('wallet-total-balance');
const walletTotalSub = document.getElementById('wallet-total-sub');
const walletCoinList = document.getElementById('wallet-coin-list');
const walletViewAssets = document.getElementById('wallet-view-assets');
const walletViewDetail = document.getElementById('wallet-view-detail');
const walletDetailTitle = document.getElementById('wallet-detail-title');
const walletActivityList = document.getElementById('wallet-activity-list');
const walletBackBtn = document.getElementById('wallet-back-btn');
const walletBackupBtn = document.getElementById('wallet-backup-btn');
const walletTransferBtn = document.getElementById('wallet-transfer-btn');

let currentWalletAgent = null;

openWalletBtn.addEventListener('click', () => {
    walletModal.showModal();
    walletViewAssets.style.display = 'flex';
    walletViewDetail.style.display = 'none';
    fetchAgents(); // update immediately
});

function updateWallet(agents) {
    if (!walletModal.open) return;

    let totalSTGM = 0;
    const frag = document.createDocumentFragment();
    
    agents.forEach(agent => {
        const energy = agent.energy || 0;
        const seq = agent.seq || 0;
        const chainLen = Array.isArray(agent.hash_chain) ? agent.hash_chain.length : 0;
        
        // PROOF OF SWIMMING FORMULA
        // Veterans worth exponentially more than newborns.
        // STGM = (Energy * 10) + (SEQ * 50) + (HashChainLen * 100)
        const stgm = (energy * 10) + (seq * 50) + (chainLen * 100);
        totalSTGM += stgm;
        
        const div = document.createElement('div');
        div.className = 'wallet-coin-item';
        div.onclick = () => openWalletDetail(agent);
        
        const face = agent.face || '[O_O]';
        const isDead = agent.style === 'DEAD' || agent.style === 'GHOST';
        const trendIcon = seq > 0 ? '▲' : '▼';
        const trendClass = seq > 0 ? 'wc-trend-up' : 'wc-trend-down';
        
        div.innerHTML = `
            <div class="wc-left">
                <div class="wc-icon ${isDead ? 'ghost' : ''}">
                    ${face}
                    ${isDead ? '<div class="wc-icon-badge">X</div>' : ''}
                </div>
                <div>
                    <div class="wc-name">${agent.id}</div>
                    <div class="wc-sub">
                        <span>NRG ${energy.toFixed(0)}% &bull; SEQ ${seq} &bull; ${chainLen} SCARS</span>
                        <span class="${trendClass}">${trendIcon} ${stgm.toFixed(0)} STGM</span>
                    </div>
                </div>
            </div>
            <div class="wc-right">
                <div class="wc-balance">${stgm.toFixed(2)}</div>
                <div class="wc-fiat">${(stgm * 0.0042).toFixed(4)} STGM</div>
            </div>
        `;
        frag.appendChild(div);
    });
    
    walletCoinList.innerHTML = '';
    walletCoinList.appendChild(frag);
    
    walletTotalBalance.textContent = totalSTGM.toFixed(2);
    walletTotalSub.textContent = `${(totalSTGM * 0.0042).toFixed(4)} STGM`;
}

walletBackBtn.addEventListener('click', () => {
    walletViewAssets.style.display = 'flex';
    walletViewDetail.style.display = 'none';
    currentWalletAgent = null;
});

async function openWalletDetail(agent) {
    currentWalletAgent = agent;
    walletDetailTitle.textContent = agent.id;
    walletViewAssets.style.display = 'none';
    walletViewDetail.style.display = 'flex';
    walletActivityList.innerHTML = '<div style="color:var(--text-muted); text-align:center; padding: 2rem;">Fetching activity...</div>';
    
    // Show REPAIRS tab by default
    document.getElementById('wallet-activity-list').style.display = '';
    document.getElementById('wallet-economy-list').style.display = 'none';

    try {
        const res = await fetch(`/api/agent_activity/${agent.id}`);
        const logs = await res.json();
        
        walletActivityList.innerHTML = '';
        if (logs.length === 0) {
            walletActivityList.innerHTML = '<div style="color:var(--text-muted); text-align:center;">No activity logged for this agent.</div>';
        } else {
            logs.forEach(log => {
                let actClass = 'ca-default';
                if (log.action === 'FIX_APPLIED') actClass = 'ca-fix';
                else if (log.action === 'SYNTAX_ERROR' || log.action === 'REPAIR_FAILED') actClass = 'ca-fail';
                else if (log.action === 'SCOUT_ATTEMPT') actClass = 'ca-scout';
                else if (log.action === 'RADIO_ASSISTANCE') actClass = 'ca-radio';

                const ts = log.ts ? log.ts.split('T')[1].replace('Z','') : '--';
                const actionText = log.action ? log.action.replace(/_/g, ' ') : 'ACT';

                const div = document.createElement('div');
                div.className = `chronicle-entry ${actClass}`;
                div.innerHTML = `
                    <div class="chr-body">
                        <div class="chr-header">
                            <span class="chr-agent">${log.agent_id}</span>
                            <span class="chr-action-badge ${actClass}">${actionText}</span>
                            <span class="chr-ts">${ts}</span>
                        </div>
                        <div class="chr-mark">${log.target_file || ''}</div>
                    </div>
                `;
                walletActivityList.appendChild(div);
            });
        }
    } catch(e) {
        walletActivityList.innerHTML = '<div style="color:var(--health-low); text-align:center;">Error fetching activity.</div>';
    }

    // Load economy data in background
    fetchWalletEconomy(agent.id);
}

async function fetchWalletEconomy(agentId) {
    const summaryEl = document.getElementById('wallet-inference-summary');
    const balanceEl = document.getElementById('wallet-stgm-balance');
    const countEl   = document.getElementById('wallet-inference-count');
    const econList  = document.getElementById('wallet-economy-list');

    try {
        const res = await fetch(`/api/inference_economy?agent_id=${agentId}&tail=50`);
        const data = await res.json();
        const events = data.events || [];
        const balance = data.stgm_balance ?? 0;

        // Update summary bar
        summaryEl.style.display = events.length > 0 ? 'block' : 'none';
        balanceEl.textContent = `${balance.toFixed(2)} STGM`;
        countEl.textContent = `${events.length} borrow${events.length !== 1 ? 's' : ''}`;

        // Render economy list
        econList.innerHTML = '';
        if (events.length === 0) {
            econList.innerHTML = '<div style="color:var(--text-muted); text-align:center; padding:1rem; font-size:0.8rem;">No borrowed inference recorded yet.<br><span style="font-size:0.7rem; color:var(--text-muted);">Use --remote-ollama flag to start borrowing.</span></div>';
        } else {
            events.forEach(ev => {
                const ts = ev.ts ? ev.ts.split('T')[1].slice(0,8) : '--';
                const shortIp = ev.lender_ip.replace('http://', '').replace('/api/generate', '');
                const div = document.createElement('div');
                div.style.cssText = 'padding:0.6rem 0; border-bottom:1px solid rgba(255,255,255,0.04); display:flex; justify-content:space-between; align-items:center;';
                div.innerHTML = `
                    <div style="font-family:var(--font-mono); font-size:0.72rem;">
                        <div style="color:var(--magenta);">-${ev.fee_stgm} STGM</div>
                        <div style="color:var(--text-muted); font-size:0.65rem;">${ev.model} @ ${shortIp}</div>
                    </div>
                    <div style="text-align:right; font-family:var(--font-mono); font-size:0.65rem; color:var(--text-muted);">
                        <div>${ev.tokens_used} tokens</div>
                        <div>${ts}</div>
                    </div>
                `;
                econList.appendChild(div);
            });
        }
    } catch(e) {
        summaryEl.style.display = 'none';
    }
}

// Economy tab switching
document.getElementById('wallet-tab-activity').addEventListener('click', () => {
    document.getElementById('wallet-activity-list').style.display = '';
    document.getElementById('wallet-economy-list').style.display = 'none';
    document.getElementById('wallet-inference-summary').style.display = 'none';
});
document.getElementById('wallet-tab-economy').addEventListener('click', () => {
    document.getElementById('wallet-activity-list').style.display = 'none';
    document.getElementById('wallet-economy-list').style.display = 'block';
    if (currentWalletAgent) fetchWalletEconomy(currentWalletAgent.id);
});


walletBackupBtn.addEventListener('click', async () => {
    if (!currentWalletAgent) return;
    const password = prompt(`Enter secure password to LOCK ${currentWalletAgent.id} backup:`);
    if (!password) return;
    
    // Call the native picker
    const res = await fetch('/api/pick-path?mode=folder');
    const data = await res.json();
    if (!data.ok || !data.path) return;
    
    const targetDir = data.path;
    alert(`Backing up ${currentWalletAgent.id} to ${targetDir}...\\nThis takes ~3 seconds due to AES encryption.`);
    
    const bRes = await fetch('/api/wallet/backup', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            agent_id: currentWalletAgent.id,
            target_dir: targetDir,
            password: password
        })
    });
    
    const bData = await bRes.json();
    if (bData.ok) {
        alert("Backup Exported Successfully!\\n\\n" + bData.output);
    } else {
        alert("Backup Failed:\\n" + bData.error);
    }
});

walletTransferBtn.addEventListener('click', async () => {
    if (!currentWalletAgent) return;
    const newOwner = prompt(`Enter new human_owner email for ${currentWalletAgent.id}:`);
    if (!newOwner) return;
    
    // Call the native picker
    const res = await fetch('/api/pick-path?mode=folder');
    const data = await res.json();
    if (!data.ok || !data.path) return;
    
    const targetDir = data.path;
    alert(`Transferring ${currentWalletAgent.id} to ${targetDir}...\nLocal copy will become a GHOST.`);
    
    const tRes = await fetch('/api/wallet/transfer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            agent_id: currentWalletAgent.id,
            new_owner: newOwner,
            target_dir: targetDir
        })
    });
    
    const tData = await tRes.json();
    if (tData.ok) {
        alert("Transfer Deed Signed, Bundle Exported!\n\n" + tData.output);
        walletModal.close();
        fetchAgents();
    } else {
        alert("Transfer Failed:\n" + tData.error);
    }
});

// ─── WORMHOLE ──────────────────────────────────────────
const walletWormholeBtn = document.getElementById('wallet-wormhole-btn');
const walletWormholePanel = document.getElementById('wallet-wormhole-panel');
const walletWormholeFireBtn = document.getElementById('wallet-wormhole-fire-btn');

let globalNodes = [];
async function fetchGlobalNodes() {
    try {
        const res = await fetch('/api/nodes');
        globalNodes = await res.json();
        const sel = document.getElementById('wormhole-node-select');
        if (sel) {
            sel.innerHTML = '<option value="">Select Hardware Node...</option>';
            globalNodes.forEach(n => {
                sel.innerHTML += `<option value="${n.ip}:${n.port}">[${n.id}] ${n.name} (${n.ip})</option>`;
            });
        }
    } catch(e) { console.error('Failed to fetch nodes', e); }
}

walletWormholeBtn.addEventListener('click', () => {
    fetchGlobalNodes();
    const isVisible = walletWormholePanel.style.display !== 'none';
    walletWormholePanel.style.display = isVisible ? 'none' : 'block';
});

walletWormholeFireBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    if (!currentWalletAgent) return;
    
    const nodeSelection = document.getElementById('wormhole-node-select').value;
    if (!nodeSelection) { alert('You must select a hardware node.'); return; }
    
    const [ip, port] = nodeSelection.split(':');
    const owner = document.getElementById('wormhole-owner').value.trim();
    
    if (!ip) { alert('TARGET IP is required.'); return; }
    if (!owner) { alert('New owner email is required.'); return; }
    if (walletWormholeFireBtn.dataset.armed !== "true") {
        walletWormholeFireBtn.dataset.armed = "true";
        walletWormholeFireBtn.innerHTML = "⚠ CLICK AGAIN TO GHOST";
        walletWormholeFireBtn.style.background = "var(--alert-red)";
        walletWormholeFireBtn.style.color = "white";
        // Reset after 4 seconds
        setTimeout(() => {
            walletWormholeFireBtn.dataset.armed = "false";
            walletWormholeFireBtn.innerHTML = "⚡ FIRE";
            walletWormholeFireBtn.style.background = "";
            walletWormholeFireBtn.style.color = "var(--magenta)";
        }, 4000);
        return;
    }
    
    // Fire!
    walletWormholeFireBtn.dataset.armed = "false";
    walletWormholeFireBtn.innerHTML = "TRANSMITTING...";
    walletWormholeFireBtn.style.background = "";
    walletWormholeFireBtn.style.color = "var(--magenta)";
    
    const terminal = document.getElementById('wallet-terminal');
    terminal.style.display = 'block';
    terminal.innerHTML = '<span class="t-boot">[🌀] Opening wormhole...</span>\n';
    
    try {
        const res = await fetch('/api/wallet/wormhole', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                agent_id: currentWalletAgent.id,
                target_ip: ip,
                target_port: parseInt(port),
                new_owner: owner
            })
        });
        const data = await res.json();
        
        if (data.ok) {
            terminal.innerHTML += `<span class="t-fix">[✓] AGENT TRANSMITTED. Local copy is now GHOST.\n${data.output}</span>`;
            setTimeout(() => {
                walletModal.close();
                fetchAgents();
            }, 2500);
        } else {
            terminal.innerHTML += `<span class="t-fail">[✗] WORMHOLE FAILED: ${data.error}</span>`;
        }
    } catch(e) {
        terminal.innerHTML += `<span class="t-fail">[✗] Connection error: ${e.message}</span>`;
    }
});

// loop() — already called on line 642, removed duplicate to prevent double-polling

// =========================================================================
// SWARM VISUALIZATION LAYER (D3.js)
// =========================================================================

let swarmMapVisible = false;
let swarmSimulation = null;
let svg = null, linkGroup = null, nodeGroup = null;
let swarmNodes = [];
let swarmLinks = [];
let swarmMapInterval = null;

function toggleSwarmMap() {
    swarmMapVisible = !swarmMapVisible;
    const panel = document.getElementById('swarm-map-panel');
    const btn = document.getElementById('open-swarm-map-btn');
    
    if (swarmMapVisible) {
        panel.style.display = 'flex';
        btn.style.background = 'rgba(0, 255, 136, 0.15)';
        btn.style.boxShadow = '0 0 14px rgba(0,255,136,0.3)';
        initSwarmGraph();
        pollSwarmState();
        swarmMapInterval = setInterval(pollSwarmState, 3000);
        panel.scrollIntoView({ behavior: 'smooth' });
    } else {
        panel.style.display = 'none';
        btn.style.background = '';
        btn.style.boxShadow = '';
        if (swarmMapInterval) clearInterval(swarmMapInterval);
        if (swarmSimulation) swarmSimulation.stop();
    }
}

function initSwarmGraph() {
    if (swarmSimulation) return; 
    
    const container = document.getElementById('swarm-svg');
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;
    
    container.innerHTML = '';
    
    svg = d3.select('#swarm-svg')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('viewBox', `0 0 ${width} ${height}`);
        
    svg.append('defs').append('marker')
        .attr('id', 'arrow')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', '#e040fb')
        .attr('d', 'M0,-5L10,0L0,5');
        
    linkGroup = svg.append('g').attr('class', 'links');
    nodeGroup = svg.append('g').attr('class', 'nodes');
    
    swarmSimulation = d3.forceSimulation()
        .force('link', d3.forceLink().id(d => d.id).distance(200))
        .force('charge', d3.forceManyBody().strength(-400))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide().radius(45));
}

async function pollSwarmState() {
    if (!swarmMapVisible) return;
    try {
        const res = await fetch('/api/swarm_state');
        if (!res.ok) return;
        const data = await res.json();
        updateSwarmData(data);
    } catch (err) {
        console.error('Swarm state error:', err);
    }
}

function updateSwarmData(data) {
    document.getElementById('swarm-map-node-count').textContent = data.nodes.length + ' NODES';
    document.getElementById('swarm-map-tx-count').textContent = data.transactions.length + ' TX SETTLED';
    
    const txList = document.getElementById('swarm-tx-list');
    txList.innerHTML = '';
    data.transactions.slice(0, 50).forEach(tx => {
        const el = document.createElement('div');
        el.className = 'swarm-tx-item';
        el.innerHTML = `
            <div><span class="amt">${tx.amount.toFixed(2)} STGM</span></div>
            <div style="margin-top:0.2rem;">${tx.from} &rarr; ${tx.to}</div>
            <div class="time">${new Date(tx.ts * 1000).toLocaleTimeString()} | ${tx.memo}</div>
        `;
        txList.appendChild(el);
    });
    
    const activeLinksMap = new Map();
    data.transactions.forEach(tx => {
        const key = `${tx.from}->${tx.to}`;
        if(!activeLinksMap.has(key)) {
            activeLinksMap.set(key, { source: tx.from, target: tx.to, value: tx.amount });
        } else {
            activeLinksMap.get(key).value += tx.amount;
        }
    });
    
    const oldNodes = new Map(swarmNodes.map(n => [n.id, n]));
    swarmNodes = data.nodes.map(n => {
        const old = oldNodes.get(n.id);
        if (old) return { ...old, ...n };
        return n;
    });
    
    const nodeIds = new Set(swarmNodes.map(n => n.id));
    swarmLinks = Array.from(activeLinksMap.values()).filter(l => 
        nodeIds.has(l.source) && nodeIds.has(l.target)
    );
    
    renderD3Graph();
}

function renderD3Graph() {
    // LINKS
    const link = linkGroup.selectAll('.link')
        .data(swarmLinks, d => d.source.id ? `${d.source.id}->${d.target.id}` : `${d.source}->${d.target}`);
        
    link.exit().remove();
    const linkEnter = link.enter().append('line')
        .attr('class', 'link')
        .attr('stroke', '#e040fb')
        .attr('stroke-width', d => Math.min(6, Math.max(1.5, Math.sqrt(d.value))))
        .attr('marker-end', 'url(#arrow)');
    const linkMerged = linkEnter.merge(link);
    
    // NODES
    const node = nodeGroup.selectAll('.node-group')
        .data(swarmNodes, d => d.id);
        
    node.exit().remove();
    const nodeEnter = node.enter()
        .append('g')
        .attr('class', 'node-group')
        .call(d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended));
            
    nodeEnter.append('circle')
        .attr('class', 'node-circle')
        .attr('r', d => Math.max(15, Math.min(35, 12 + Math.sqrt(d.stgm_balance || 0))));
        
    nodeEnter.append('text')
        .attr('class', 'node-label')
        .attr('dy', -25)
        .attr('text-anchor', 'middle')
        .text(d => d.id);
        
    nodeEnter.append('text')
        .attr('class', 'node-balance')
        .attr('dy', 4)
        .text(d => parseFloat(d.stgm_balance || 0).toFixed(1));
        
    const nodeMerged = nodeEnter.merge(node);
    
    nodeMerged.select('.node-circle')
        .attr('r', d => Math.max(15, Math.min(35, 12 + Math.sqrt(d.stgm_balance || 0))))
        .attr('fill', d => {
            if (d.style === 'GHOST') return '#1a1a25';
            if (d.style === 'BLEEDING' || d.style === 'CRITICAL') return '#ff1744';
            return '#0A1A2F';
        })
        .attr('stroke', d => {
            if (d.style === 'GHOST') return '#3d5068';
            if (d.style === 'BLEEDING' || d.style === 'CRITICAL') return '#ff1744';
            return d.active ? '#00ff88' : '#00e5ff';
        })
        .style('filter', d => d.active ? 'drop-shadow(0 0 10px rgba(0,255,136,0.5))' : 'none');
        
    nodeMerged.select('.node-balance')
        .text(d => parseFloat(d.stgm_balance || 0).toFixed(1));
        
    swarmSimulation.nodes(swarmNodes).on('tick', () => {
        linkMerged
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
            
        nodeMerged.attr('transform', d => `translate(${d.x},${d.y})`);
    });
    
    swarmSimulation.force('link').links(swarmLinks);
    swarmSimulation.alpha(0.3).restart();
}

function dragstarted(event, d) {
  if (!event.active) swarmSimulation.alphaTarget(0.3).restart();
  d.fx = d.x; d.fy = d.y;
}
function dragged(event, d) {
  d.fx = event.x; d.fy = event.y;
}
function dragended(event, d) {
  if (!event.active) swarmSimulation.alphaTarget(0);
  d.fx = null; d.fy = null;
}

