// ═══════════════════════════════════════════════════
//  ANTON-SIFTA // COMMAND INTERFACE — app.js
// ═══════════════════════════════════════════════════
let activeDispatchAgent = null;

// Cinematic Odometer Helper
function animateValue(obj, start, end, duration, fractionDigits = 2) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = start + easeOutQuart * (end - start);
        obj.textContent = current.toFixed(fractionDigits);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            obj.textContent = end.toFixed(fractionDigits);
        }
    };
    window.requestAnimationFrame(step);
}

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
    ['drawer-territory', 'drawer-proposals', 'drawer-cemetery', 'drawer-quorum'].forEach(id => {
        const d = document.getElementById(id);
        if (d) d.removeAttribute('open');
    });
    ['panel-btn-territory', 'panel-btn-proposals', 'panel-btn-cemetery', 'panel-btn-quorum'].forEach(id => {
        const b = document.getElementById(id);
        if (b) b.classList.remove('active');
    });
    const fleetBtn = document.getElementById('panel-btn-fleet');
    if (fleetBtn) fleetBtn.classList.add('active');
    const fleetList = document.getElementById('fleet-list');
    if (fleetList) fleetList.scrollTop = 0;
}

function _syncFleetBtn() {
    const anyOpen = ['drawer-territory', 'drawer-proposals', 'drawer-cemetery', 'drawer-quorum']
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
    
    // Prevent selection of dead agents (GHOST protocol block)
    if (card && card.classList.contains('dead')) {
        console.warn(`[GHOST] Blocked selection of terminated agent: ${agentId}`);
        return;
    }
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
    
    // Always update the agent label in the inline deploy panel
    const dcAgent = document.getElementById('dc-active-agent');
    if (dcAgent) {
        const styleText = document.getElementById(`style-${agentId}`)?.textContent || 'NOMINAL';
        dcAgent.textContent = `${agentId} [${styleText}]`;
    }

    // Determine if a scan is actively running (abort is armed ONLY during active scan)
    const sendBtn  = document.getElementById('dc-send-btn');
    const abortBtn = document.getElementById('dc-abort-btn');
    const isScanning = abortBtn && !abortBtn.disabled;

    // Always enable deploy button when an agent is selected (unless mid-scan)
    if (sendBtn) sendBtn.disabled = false;

    if (!isScanning) {
        const terminal = document.getElementById('dc-terminal');
        if (terminal) {
            terminal.innerHTML = `<div class="placeholder t-boot">&gt; Agent ${agentId} selected.<br>&gt; WAITING FOR MISSION PARAMETERS... <span class="blink">▋</span></div>`;
        }
    }

    // Always open the deploy panel
    openDeployInline();
}


// ─── Inline Deploy Panel (replaces territory tiles in-place) ─────────────────
function openDeployInline() {
    const tv = document.getElementById('territory-view');
    const dv = document.getElementById('deploy-view');
    if (tv) tv.style.display = 'none';
    if (dv) dv.style.display = 'flex';

    // Sync agent label and enable DEPLOY button if an agent is already selected
    const dcAgent = document.getElementById('dc-active-agent');
    const sendBtn = document.getElementById('dc-send-btn');
    const abortBtn = document.getElementById('dc-abort-btn');
    if (activeDispatchAgent) {
        if (dcAgent) {
            const styleText = document.getElementById(`style-${activeDispatchAgent}`)?.textContent || 'NOMINAL';
            dcAgent.textContent = `${activeDispatchAgent} [${styleText}]`;
        }
        // Enable the bottom DEPLOY button — it only stays disabled if no agent is selected or a scan is actively running
        const isScanning = abortBtn && !abortBtn.disabled;
        if (sendBtn && !isScanning) sendBtn.disabled = false;
    }
}


function closeDeployInline() {
    const tv = document.getElementById('territory-view');
    const dv = document.getElementById('deploy-view');
    if (dv) dv.style.display = 'none';
    if (tv) tv.style.display = '';
}

function onWriteToggle(checkbox) {
    const bar   = document.getElementById('arch-auth-bar');
    const label = document.getElementById('arch-auth-label');
    if (!bar || !label) return;
    if (checkbox.checked) {
        bar.style.background    = 'rgba(255,23,68,0.10)';
        bar.style.borderColor   = 'rgba(255,23,68,0.6)';
        label.style.color       = 'var(--health-low)';
        label.textContent       = '🔥 MUTATION AUTHORIZED — Agent MAY write, patch, and modify files';
    } else {
        bar.style.background    = 'rgba(255,23,68,0.04)';
        bar.style.borderColor   = 'rgba(255,23,68,0.25)';
        label.style.color       = 'var(--text-muted)';
        label.textContent       = 'DRY-RUN MODE — Agent will scan but NOT write files';
    }
}


async function copyTerminalOutput() {
    const terminal = document.getElementById('dc-terminal');
    const btn      = document.getElementById('dc-copy-btn');
    if (!terminal) return;
    const text = terminal.innerText;
    try {
        await navigator.clipboard.writeText(text);
        if (btn) {
            btn.textContent = '✅ COPIED';
            btn.style.borderColor = 'var(--health-high)';
            btn.style.color = 'var(--health-high)';
            setTimeout(() => {
                btn.textContent = '📋 COPY';
                btn.style.borderColor = 'rgba(0,229,255,0.2)';
                btn.style.color = 'var(--text-muted)';
            }, 1500);
        }
    } catch (e) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;left:-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        if (btn) {
            btn.textContent = '✅ COPIED';
            setTimeout(() => { btn.textContent = '📋 COPY'; }, 1500);
        }
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
    else if (/\[PROPOSAL\]|\[📋\]|Proposal staged/i.test(txt))
        div.className = 't-proposal';

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
        
        const stActive = document.getElementById('status-agents-active');
        if (stActive) stActive.textContent = liveAgentCount || '0';
        
        updateRoster(agents);
        updateFleet(agents);
        
        if (activeDispatchAgent === null && agents.length > 0) {
            // Find lowest energy agent to be the default worker (excluding dead ones)
            const aliveAgents = agents.filter(a => a.style !== 'DEAD' && a.ttl_remaining > 0);
            if (aliveAgents.length > 0) {
                const defaultAgent = aliveAgents.reduce((prev, curr) => (prev.energy < curr.energy) ? prev : curr);
                selectAgentForDispatch(defaultAgent.id);
            }
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
        const energyPct = Math.min(100, Math.max(0, agent.energy));
        const isCritical = energyPct <= 25 && !isDead;
        
        card.className = `agent-card fade-in ${isDead ? ' dead' : ''} ${isCritical ? ' pulse-red' : ''} ${agent.id === activeDispatchAgent ? ' ac-selected' : ''}`;
        
        let displayFace = agent.face;
        if (isDead) displayFace = '💀';
        else if (isCritical) displayFace = '🥵';
        
        card.querySelector(`#face-${agent.id}`).textContent = displayFace;

        const styleBadge = card.querySelector(`#style-${agent.id}`);
        styleBadge.className = `agent-style ${parseStyleBadge(agent.style)}`;
        styleBadge.textContent = agent.style;

        card.querySelector(`#seq-${agent.id}`).textContent = `SEQ: ${agent.seq}`;
        card.querySelector(`#ttl-${agent.id}`).textContent = `TTL: ${formatTime(agent.ttl_remaining)}`;

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

let _lastLogCount = 0;

const microPersonality = {
    SCOUT: [
        "Something feels off here...",
        "Quiet... too quiet.",
        "I've seen patterns like this before."
    ],
    REPAIR: [
        "I think I can fix this.",
        "Hold on, stitching the logic...",
        "This one's tricky... but solvable."
    ],
    QUEEN: [
        "The structure bends to my will.",
        "Correcting the lesser agents' oversights.",
        "My zone must be pristine."
    ],
    DETECTIVE: [
        "Following the scent of a syntactic tear.",
        "A logical inconsistency. Fascinating.",
        "The evidence points to a recent mutation."
    ],
    DEFAULT: [
        "My zone is clear.",
        "Traversing the sectors...",
        "Awaiting further directives."
    ]
};

function getFlavor(agentName, ev) {
    let role = 'DEFAULT';
    if (ev === 'scout') role = 'SCOUT';
    else if (ev === 'fail') role = 'DETECTIVE';
    else if (ev === 'fix') role = 'REPAIR';
    
    if (agentName.includes('QUEEN')) role = 'QUEEN';
    
    const flavorArr = microPersonality[role] || microPersonality['DEFAULT'];
    return flavorArr[Math.floor(Math.random() * flavorArr.length)];
}

function updateLogs(logs) {
    const container = document.getElementById('postcards-feed');
    if (!container) return;

    if (logs.length === _lastLogCount && container.children.length > 1) return;
    _lastLogCount = logs.length;

    container.innerHTML = '';

    if (logs.length === 0) {
        container.innerHTML = `<div class="postcard system-postcard" style="border: 1px solid var(--border-color); background: var(--bg-dark); padding: 10px; border-radius: var(--r-sm);">
            <div class="postcard-body" style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-sub);">Neural uplink secure. Awaiting transmission from the swarm...</div>
        </div>`;
        return;
    }

    // Seed Randomizer for flavor so it doesn't change on every poll redraw
    // Simple hash of log.ts + log.hash
    const hashStringToInt = (s) => [...s].reduce((hash, c) => Math.imul(31, hash) + c.charCodeAt(0) | 0, 0);

    logs.slice().reverse().forEach(log => {
        const ev = log.event || 'msg';
        const ts = new Date(log.ts).toLocaleTimeString('en-US', { hour12: false });
        let file = log.file || log.target || '—';
        const agentName = log.agent_id ? log.agent_id.split('-')[0] : 'SIFTA CORE';

        if (file && file.includes('/')) file = file.split('/').pop();

        let narrative = '';
        let cardColor = 'var(--border-color)';
        let icon = '📝';
        
        let seed = Math.abs(hashStringToInt((log.ts || 0).toString() + (log.hash || '')));
        let role = 'DEFAULT';
        
        if (ev === 'scout') {
            narrative = `I walked through <strong>${file}</strong>. Looks clean to me. Leaving a scent trail.`;
            cardColor = 'rgba(120, 144, 156, 0.4)';
            icon = '💨';
            role = 'SCOUT';
        } else if (ev === 'fail' || ev === 'reject') {
            narrative = `I found a tear in the fabric at <strong>${file}</strong>. Tightening my jaws...`;
            cardColor = 'rgba(255, 82, 82, 0.4)';
            icon = '🦷';
            role = 'DETECTIVE';
        } else if (ev === 'fix') {
            narrative = `I have successfully synthesized a repair for <strong>${file}</strong>. It took some energy, but the structure holds.`;
            cardColor = 'rgba(0, 230, 118, 0.4)';
            icon = '🧬';
            role = 'REPAIR';
        } else if (ev === 'mind_trace') {
            const confStr = log.final_score !== undefined ? log.final_score.toFixed(2) : 'N/A';
            const wasAccepted = log.final_score !== undefined && log.final_score > 0.65;
            
            if (wasAccepted) {
                narrative = `Internal monologue: "<span style="color:var(--amber)">${log.reason || log.role || 'Analyzing structures'}</span>" <br><br><span style="color:var(--cyan)">🧬 DNA ACCEPTED (Conf: ${confStr})</span>`;
            } else {
                narrative = `Internal monologue: "<span style="color:var(--amber)">${log.reason || log.role || 'Analyzing structures'}</span>" <br><br><span style="color:var(--health-low)">🚫 Rejected by Quorum (Conf: ${confStr})</span>`;
            }
            cardColor = 'rgba(255, 204, 2, 0.4)';
            icon = '🧠';
        } else {
            narrative = `Detected anomaly on <strong>${file}</strong>. Action: ${ev}`;
        }

        if (agentName.includes('QUEEN')) role = 'QUEEN';
        
        // Pick flavor safely
        let flavorArr = microPersonality[role] || microPersonality['DEFAULT'];
        if (ev === 'mind_trace') flavorArr = []; // No extra flavor for mind trace
        const extraFlavor = flavorArr.length > 0 ? `<div style="margin-top: 8px; font-style: italic; color: var(--text-dim); font-size: 0.75rem;">"${flavorArr[seed % flavorArr.length]}"</div>` : '';

        const card = document.createElement('div');
        card.className = 'postcard fade-in';
        card.style.border = `1px solid ${cardColor}`;
        card.style.background = `rgba(8, 11, 16, 0.6)`;
        card.style.padding = `12px`;
        card.style.borderRadius = `var(--r-sm)`;
        card.style.marginBottom = `0.5rem`;

        card.innerHTML = `
            <div class="postcard-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px; font-size: 0.75rem; color:var(--text-sub); font-family:var(--font-mono);">
                <span><span style="color:var(--cyan)">${icon} ${agentName}</span></span>
                <span>${ts}</span>
            </div>
            <div class="postcard-body" style="font-size: 0.85rem; color: var(--text-main); line-height: 1.4;">
                ${narrative}
                ${extraFlavor}
            </div>
        `;
        container.appendChild(card);
    });

    container.scrollTop = container.scrollHeight;
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
    fastModel:localStorage.getItem('llm_fast_model')|| 'qwen3.5:0.8b',
    baseUrl:  localStorage.getItem('llm_base_url') || '',
    apiKey:   localStorage.getItem('llm_api_key')  || '',
};

let ollamaModels = [];

async function fetchOllamaModels() {
    try {
        const res  = await fetch('/api/ollama-models');
        const data = await res.json();
        ollamaModels = data.models || [];
        const selHeavy = document.getElementById('llm-heavy-model-select');
        const selFast  = document.getElementById('llm-fast-model-select');
        const currentHeavy = selHeavy ? selHeavy.value : null;
        const currentFast  = selFast ? selFast.value : null;

        if (selHeavy) selHeavy.innerHTML = '';
        if (selFast) selFast.innerHTML = '';
        if (ollamaModels.length === 0) {
            if (selHeavy) selHeavy.innerHTML = '<option value="">No local models found</option>';
            if (selFast) selFast.innerHTML = '<option value="">No local models found</option>';
        } else {
            ollamaModels.forEach(m => {
                const optHeavy = document.createElement('option');
                optHeavy.value = m;
                optHeavy.textContent = m;
                if (currentHeavy ? m === currentHeavy : m === providerSettings.model) optHeavy.selected = true;
                if (selHeavy) selHeavy.appendChild(optHeavy);
                
                const optFast = document.createElement('option');
                optFast.value = m;
                optFast.textContent = m;
                if (currentFast ? m === currentFast : m === providerSettings.fastModel) optFast.selected = true;
                if (selFast) selFast.appendChild(optFast);
            });
        }
    } catch (e) {
        console.error('Could not fetch Ollama models', e);
    }
}

function updateModelUI(provider) {
    const fastSelectGroup  = document.getElementById('fast-model-select-group');
    const fastTextGroup    = document.getElementById('fast-model-text-group');
    const heavySelectGroup = document.getElementById('heavy-model-select-group');
    const heavyTextGroup   = document.getElementById('heavy-model-text-group');
    
    if (provider === 'ollama') {
        if (fastSelectGroup) fastSelectGroup.style.display = '';
        if (fastTextGroup) fastTextGroup.style.display   = 'none';
        if (heavySelectGroup) heavySelectGroup.style.display = '';
        if (heavyTextGroup) heavyTextGroup.style.display   = 'none';
        fetchOllamaModels();
    } else {
        if (fastSelectGroup) fastSelectGroup.style.display = 'none';
        if (fastTextGroup) fastTextGroup.style.display   = '';
        if (heavySelectGroup) heavySelectGroup.style.display = 'none';
        if (heavyTextGroup) heavyTextGroup.style.display   = '';
        
        const fastTextInput = document.getElementById('llm-fast-model-text');
        if (fastTextInput && !ollamaModels.includes(providerSettings.fastModel)) {
            fastTextInput.value = providerSettings.fastModel;
        }
        const heavyTextInput = document.getElementById('llm-heavy-model-text');
        if (heavyTextInput && !ollamaModels.includes(providerSettings.model)) {
            heavyTextInput.value = providerSettings.model;
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
        ? document.getElementById('llm-heavy-model-select').value
        : document.getElementById('llm-heavy-model-text').value;
    providerSettings.fastModel = providerSettings.provider === 'ollama'
        ? document.getElementById('llm-fast-model-select').value
        : document.getElementById('llm-fast-model-text').value;

    localStorage.setItem('llm_provider', providerSettings.provider);
    localStorage.setItem('llm_model',    providerSettings.model);
    localStorage.setItem('llm_fast_model', providerSettings.fastModel);
    localStorage.setItem('llm_base_url', providerSettings.baseUrl);
    localStorage.setItem('llm_api_key',  providerSettings.apiKey);

    settingsModal.close();
});


// ─── Central Dispatch Submission ────────────────────────
async function sendSwimmerCentral(actionType) {
    if (!activeDispatchAgent) return;
    
    // Ghost protocol secondary check (in case agent died while already selected)
    const card = document.querySelector(`[data-id="${activeDispatchAgent}"]`);
    if (card && card.classList.contains('dead')) {
        const terminal = document.getElementById('dc-terminal');
        if (terminal) terminal.innerHTML = `<div class="t-warn">[GHOST PROTOCOL] Agent ${activeDispatchAgent} has been terminated. Selection cleared.</div>`;
        activeDispatchAgent = null;
        document.getElementById('dc-scan-btn').disabled = true;
        document.getElementById('dc-repair-btn').disabled = true;
        document.getElementById('dc-messenger-btn').disabled = true;
        return;
    }

    const targetDir  = document.getElementById('dc-target').value;
    
    // Action Type mapping
    let isWrite = false;
    if (actionType === 'repair') {
        isWrite = true;
    }

    const isInvestor = document.getElementById('dc-investor-mode') ? document.getElementById('dc-investor-mode').checked : false;
    const terminal   = document.getElementById('dc-terminal');
    const scanBtn    = document.getElementById('dc-scan-btn');
    const repairBtn  = document.getElementById('dc-repair-btn');
    const msgrBtn    = document.getElementById('dc-messenger-btn');
    const abortBtn   = document.getElementById('dc-abort-btn');
    const scrollHint = document.getElementById('dc-scroll-hint');
    
    document.getElementById('dc-target').disabled = true;
    scanBtn.disabled  = true;
    repairBtn.disabled = true;
    msgrBtn.disabled = true;
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
            fast_model: providerSettings.fastModel,
            base_url:   providerSettings.baseUrl,
            api_key:    providerSettings.apiKey,
            investor_mode: isInvestor,
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
            div.textContent = '— SCAN COMPLETE —';
            terminal.appendChild(div);

            // Give the operator time to read — show a close button instead of auto-closing
            const closeDiv = document.createElement('div');
            closeDiv.style.cssText = 'text-align:center; margin-top: 12px;';
            closeDiv.innerHTML = `<button onclick="closeDeployInline()" style="background: rgba(0,229,255,0.15); border: 1px solid var(--cyan); color: var(--cyan); font-family: var(--font-mono); font-size: 0.75rem; padding: 0.4rem 1.5rem; border-radius: 4px; cursor: pointer; letter-spacing: 0.1em;">[ ← BACK TO MAP ]</button>`;
            terminal.appendChild(closeDiv);
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
        
        const cardAgain = document.querySelector(`[data-id="${activeDispatchAgent}"]`);
        if (!cardAgain || !cardAgain.classList.contains('dead')) {
            document.getElementById('dc-scan-btn').disabled = false;
            document.getElementById('dc-repair-btn').disabled = false;
            document.getElementById('dc-messenger-btn').disabled = false;
        }
        document.getElementById('dc-abort-btn').disabled = true;
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
    
    if (activeDispatchAgent) {
        const cardAgain = document.querySelector(`[data-id="${activeDispatchAgent}"]`);
        if (!cardAgain || !cardAgain.classList.contains('dead')) {
            document.getElementById('dc-scan-btn').disabled = false;
            document.getElementById('dc-repair-btn').disabled = false;
            document.getElementById('dc-messenger-btn').disabled = false;
        }
    }
}


// ─── PROPOSALS PANEL ─────────────────────────────────────────────────────────
let proposalCache = [];

async function fetchProposals() {
    try {
        const [pendingRes, statsRes] = await Promise.all([
            fetch('/api/proposals?status=PENDING'),
            fetch('/api/proposals/stats'),
        ]);
        const pending = await pendingRes.json();
        const stats = await statsRes.json();

        proposalCache = pending;
        renderProposals(pending, stats);
    } catch (e) {
        console.error('Proposals fetch error', e);
    }
}

function renderProposals(proposals, stats) {
    // Update badge
    const badge = document.getElementById('proposals-badge');
    if (badge) {
        badge.textContent = stats.pending || '';
        badge.style.display = stats.pending > 0 ? 'inline-flex' : 'none';
    }
    const statusVotes = document.getElementById('status-votes');
    if (statusVotes) statusVotes.textContent = stats.pending || '0';

    const container = document.getElementById('proposals-list');
    if (!container) return;

    if (proposals.length === 0) {
        container.innerHTML = `
            <div class="proposals-empty">
                <span class="proposals-empty-icon">📋</span>
                <span>No pending proposals. Agents will stage repairs here when swimming with <code>--proposals</code>.</span>
            </div>
        `;
        return;
    }

    container.innerHTML = '';

    proposals.forEach(p => {
        const card = document.createElement('div');
        card.className = 'proposal-card';
        card.id = `proposal-${p.proposal_id}`;

        const ts = new Date(p.created_at * 1000).toLocaleString('en-US', {
            hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
            month: 'short', day: 'numeric'
        });
        const confColor = p.confidence >= 0.9 ? 'var(--health-high)'
                        : p.confidence >= 0.75 ? 'var(--health-med)'
                        : 'var(--health-low)';

        // Format the diff with syntax highlighting
        const diffLines = (p.diff || '').split('\n').map(line => {
            if (line.startsWith('+') && !line.startsWith('+++')) {
                return `<span class="diff-add">${escapeHtml(line)}</span>`;
            } else if (line.startsWith('-') && !line.startsWith('---')) {
                return `<span class="diff-del">${escapeHtml(line)}</span>`;
            } else if (line.startsWith('@@')) {
                return `<span class="diff-hunk">${escapeHtml(line)}</span>`;
            }
            return escapeHtml(line);
        }).join('\n');

        card.innerHTML = `
            <div class="proposal-header">
                <div class="proposal-meta">
                    <span class="proposal-filename">${p.filename}</span>
                    <span class="proposal-agent" title="Agent">${p.agent_id}</span>
                    ${p.vocation ? `<span class="proposal-vocation">${p.vocation}</span>` : ''}
                </div>
                <div class="proposal-stats">
                    <span class="proposal-conf" style="color:${confColor}" title="Confidence">
                        ◉ ${(p.confidence * 100).toFixed(0)}%
                    </span>
                    <span class="proposal-time">${ts}</span>
                </div>
            </div>
            <div class="proposal-error">
                <code>${escapeHtml(p.error_description || '—')}</code>
            </div>
            <div class="proposal-diff-wrap">
                <pre class="proposal-diff">${diffLines || 'No diff available.'}</pre>
            </div>
            <div class="proposal-actions">
                <button class="proposal-btn approve" onclick="approveProposal('${p.proposal_id}')">
                    ✓ APPROVE
                </button>
                <button class="proposal-btn reject" onclick="rejectProposal('${p.proposal_id}')">
                    ✕ REJECT
                </button>
            </div>
        `;

        container.appendChild(card);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function approveProposal(proposalId) {
    const card = document.getElementById(`proposal-${proposalId}`);
    if (card) card.style.opacity = '0.5';

    try {
        const res = await fetch(`/api/proposals/${proposalId}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json();

        if (data.ok) {
            if (card) {
                card.classList.add('proposal-approved');
                card.querySelector('.proposal-actions').innerHTML = `
                    <span class="proposal-result approved">✓ APPROVED — Applied to ${data.proposal.filename}</span>
                `;
            }
            // Flash the terminal if visible
            const terminal = document.getElementById('dc-terminal');
            if (terminal) {
                const div = document.createElement('div');
                div.className = 't-fix';
                div.textContent = `[✅ APPROVED] Proposal ${proposalId.substring(0, 8)}... applied to ${data.proposal.filename}`;
                terminal.appendChild(div);
                terminal.scrollTop = terminal.scrollHeight;
            }
        } else {
            alert(`Approval failed: ${data.error}`);
            if (card) card.style.opacity = '1';
        }
    } catch (e) {
        console.error('Approve failed', e);
        if (card) card.style.opacity = '1';
    }

    // Refresh proposals after action
    setTimeout(fetchProposals, 500);
}

async function rejectProposal(proposalId) {
    const reason = prompt('Rejection reason (optional):') || 'Rejected by operator';

    const card = document.getElementById(`proposal-${proposalId}`);
    if (card) card.style.opacity = '0.5';

    try {
        const res = await fetch(`/api/proposals/${proposalId}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason }),
        });
        const data = await res.json();

        if (data.ok) {
            if (card) {
                card.classList.add('proposal-rejected');
                card.querySelector('.proposal-actions').innerHTML = `
                    <span class="proposal-result rejected">✕ REJECTED — ${reason}</span>
                `;
            }
        } else {
            alert(`Rejection failed: ${data.error}`);
            if (card) card.style.opacity = '1';
        }
    } catch (e) {
        console.error('Reject failed', e);
        if (card) card.style.opacity = '1';
    }

    // Refresh proposals after action
    setTimeout(fetchProposals, 500);
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
            // Pulse active cards (specifically the working agent if provided)
            document.querySelectorAll('.agent-card:not(.dead)').forEach(c => {
                if (s.agent_id && c.dataset.id !== s.agent_id) {
                    c.classList.remove('active-swim');
                } else {
                    c.classList.add('active-swim');
                }
            });
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
    
    // Start polling after all UI components and consts are initialized
    loop();
    setInterval(loop, 2000);

    // Proposals polling (slower cadence)
    fetchProposals();
    setInterval(fetchProposals, 4000);
});

async function updateTerritory() {
    if (systemHovered) return; // Freeze UI redraws if user is hovering to click buttons
    try {
        const res = await fetch('/api/territory');
        if (!res.ok) return;
        const data = await res.json();
        const grid = document.getElementById('territory-grid');
        if (!grid) return;
        
        if (!data.territories || data.territories.length === 0) {
            grid.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; width: 100%; text-align: center; margin-top: 2rem;">Territory is unexplored. Select a target and deploy.</div>';
            return;
        }

        grid.innerHTML = '';
        let faultsCount = 0;
        let criticalCount = 0;

        data.territories.forEach(terr => {
            const el = document.createElement('div');
            let displayStatus = terr.status;
            if (terr.status === 'CLEAN' && terr.agents && terr.agents.length > 0) {
                displayStatus = 'HEALED';
            }
            
            let bgColor = 'rgba(64, 196, 255, 0.05)';
            let borderColor = 'rgba(64, 196, 255, 0.2)';
            let textColor = 'var(--text-main)';
            
            if (displayStatus === 'BLEEDING') {
                bgColor = 'rgba(255, 82, 82, 0.1)';
                borderColor = 'rgba(255, 82, 82, 0.5)';
                el.classList.add('pulse-red');
                criticalCount++;
                faultsCount++;
            } else if (displayStatus === 'HEALED') {
                bgColor = 'rgba(0, 230, 118, 0.05)';
                borderColor = 'rgba(0, 230, 118, 0.3)';
            }

            const opacity = Math.max(0.4, terr.max_potency);
            const basename = terr.path.split('/').pop();
            
            el.className = 'territory-node fade-in';
            el.style.width = '120px';
            el.style.height = '80px';
            el.style.padding = '8px';
            el.style.display = 'flex';
            el.style.flexDirection = 'column';
            el.style.justifyContent = 'center';
            el.style.alignItems = 'center';
            el.style.background = bgColor;
            el.style.border = `1px solid ${borderColor}`;
            el.style.borderRadius = 'var(--r-sm)';
            el.style.cursor = 'pointer';
            el.style.opacity = opacity;
            el.style.textAlign = 'center';
            el.style.position = 'relative';

            let icon = '📁';
            if (basename.includes('.')) icon = '📄';

            let dangerStr = terr.danger_score > 0 ? `<div style="position:absolute; top:-5px; right:-5px; background:var(--health-low); color:#fff; border-radius:50%; width:16px; height:16px; font-size:10px; font-weight:bold; display:flex; justify-content:center; align-items:center;">!</div>` : '';

            el.innerHTML = `
                <div style="font-size: 1.2rem; margin-bottom: 4px;">${icon}</div>
                <div style="font-size: 0.7rem; color: ${textColor}; word-break: break-all; font-family: var(--font-mono); text-overflow: ellipsis; overflow: hidden; white-space: nowrap; width: 100%;">${basename}</div>
                ${dangerStr}
            `;
            
            // Click to read the graffiti
            el.addEventListener('click', () => showScarModal(terr.full_path || terr.path));
            grid.appendChild(el);
            
            if (terr.danger_score > 0 && displayStatus !== 'BLEEDING') {
                faultsCount++;
            }
        });
        
        const sf = document.getElementById('status-faults');
        if (sf) sf.textContent = faultsCount;
        const sc = document.getElementById('status-critical');
        if (sc) sc.textContent = criticalCount;
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
            
            const bHash = item.before_hash || '';
            const aHash = item.after_hash || '';
            if (bHash && aHash) metaTxt += `${bHash.substring(0,8)} → ${aHash.substring(0,8)} `;
            else if (aHash) metaTxt += `HASH: ${aHash.substring(0,8)} `;
            else if (bHash) metaTxt += `HASH: ${bHash.substring(0,8)} `;
            
            if (item.reason) metaTxt += `ERR: ${item.reason} `;
            if (item.status) metaTxt += `STATUS: ${item.status}`;
            metaTbody.textContent = metaTxt.trim();
            
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
    
    // Odometer animation logic
    if (typeof window.lastWalletSTGM === 'undefined') {
        window.lastWalletSTGM = totalSTGM;
        walletTotalBalance.textContent = totalSTGM.toFixed(2);
        walletTotalSub.textContent = `${(totalSTGM * 0.0042).toFixed(4)} STGM/fiat`;
    } else if (Math.abs(window.lastWalletSTGM - totalSTGM) > 0.01) {
        animateValue(walletTotalBalance, window.lastWalletSTGM, totalSTGM, 1200, 2);
        
        // Custom animation block for the fiat subtext since animateValue modifies textContent raw
        let startFiat = window.lastWalletSTGM * 0.0042;
        let endFiat = totalSTGM * 0.0042;
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / 1200, 1);
            const easeOutQuart = 1 - Math.pow(1 - progress, 4);
            const current = startFiat + easeOutQuart * (endFiat - startFiat);
            walletTotalSub.textContent = `${current.toFixed(4)} STGM`;
            if (progress < 1) window.requestAnimationFrame(step);
        };
        window.requestAnimationFrame(step);
        
        window.lastWalletSTGM = totalSTGM;
    } else {
        walletTotalBalance.textContent = totalSTGM.toFixed(2);
        walletTotalSub.textContent = `${(totalSTGM * 0.0042).toFixed(4)} STGM`;
    }
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

function toggleWormholeVector() {
    const vector = document.getElementById('wormhole-vector').value;
    document.getElementById('vector-lan-panel').style.display = vector === 'lan' ? 'block' : 'none';
    document.getElementById('vector-relay-panel').style.display = vector === 'relay' ? 'block' : 'none';
}

async function checkRelayDrops() {
    const pubkey = document.getElementById('my-pubkey-input').value.trim();
    if (!pubkey) { alert('Please enter your Node ID / PubKey first.'); return; }
    
    // Default relay URL
    const relayUrl = "http://127.0.0.1:8000";
    
    try {
        document.getElementById('check-relay-btn').innerText = "⏳ PULLING...";
        const res = await fetch('/api/wallet/relay_pickup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                my_pubkey: pubkey,
                relay_url: relayUrl
            })
        });
        const data = await res.json();
        if (data.ok) {
            alert(`Relay Sync Complete.\n${data.output}`);
            fetchAgents(); // Refresh the list
        } else {
            alert(`Relay Sync failed:\n${data.error}`);
        }
    } catch(e) {
        alert("Network error: " + e.message);
    } finally {
        document.getElementById('check-relay-btn').innerText = "📥 SYNC RELAY";
    }
}

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
    
    const owner = document.getElementById('wormhole-owner').value.trim();
    if (!owner) { alert('New owner email is required.'); return; }
    
    const vector = document.getElementById('wormhole-vector').value;
    let ip, port, targetPubkey, relayUrl;
    
    if (vector === 'lan') {
        const nodeSelection = document.getElementById('wormhole-node-select').value;
        if (!nodeSelection) { alert('You must select a hardware node.'); return; }
        [ip, port] = nodeSelection.split(':');
        if (!ip) { alert('TARGET IP is required.'); return; }
    } else {
        targetPubkey = document.getElementById('wormhole-target-pubkey').value.trim();
        relayUrl = document.getElementById('wormhole-relay-url').value.trim();
        if (!targetPubkey || !relayUrl) { alert('Target Node Alias and Relay URL are required.'); return; }
    }
    
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
    terminal.innerHTML = vector === 'lan' ? '<span class="t-boot">[🌀] Opening LAN wormhole...</span>\n' : '<span class="t-boot">[🌐] Pushing to Dead-Drop Relay...</span>\n';
    
    try {
        let endpoint = '';
        let payload = {};
        if (vector === 'lan') {
            endpoint = '/api/wallet/wormhole';
            payload = {
                agent_id: currentWalletAgent.id,
                target_ip: ip,
                target_port: parseInt(port),
                new_owner: owner
            };
        } else {
            endpoint = '/api/wallet/relay_drop';
            payload = {
                agent_id: currentWalletAgent.id,
                target_pubkey: targetPubkey,
                new_owner: owner,
                relay_url: relayUrl
            };
        }
        
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (data.ok) {
            terminal.innerHTML += `<span class="t-fix">[✓] AGENT TRANSMITTED. Local copy is now GHOST.\n${data.output || ''}</span>`;
            setTimeout(() => {
                walletModal.close();
                fetchAgents();
            }, 2500);
        } else {
            terminal.innerHTML += `<span class="t-fail">[✗] TRANSMISSION FAILED: ${data.error}</span>`;
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
let svg = null;
let sunburstGroup = null;
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
        pollTopologyState();
        swarmMapInterval = setInterval(pollTopologyState, 5000); // 5 seconds so it doesn't slam the IO on a 6000 file repo
        panel.scrollIntoView({ behavior: 'smooth' });
    } else {
        panel.style.display = 'none';
        btn.style.background = '';
        btn.style.boxShadow = '';
        if (swarmMapInterval) clearInterval(swarmMapInterval);
    }
}

function initSwarmGraph() {
    if (svg) return; 
    
    const container = document.getElementById('swarm-svg');
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;
    
    container.innerHTML = '';
    
    svg = d3.select('#swarm-svg')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('viewBox', `0 0 ${width} ${height}`);
        
    sunburstGroup = svg.append('g')
        .attr('transform', `translate(${width / 2},${height / 2})`);
}

async function pollTopologyState() {
    if (!swarmMapVisible) return;
    try {
        const res = await fetch('/api/topology');
        if (!res.ok) return;
        const data = await res.json();
        
        // Also poll basic metrics for the header
        const resStats = await fetch('/api/swarm_state');
        if (resStats.ok) {
            const stats = await resStats.json();
            document.getElementById('swarm-map-node-count').textContent = stats.nodes.length + ' ACTIVE CHRONICLES';
            document.getElementById('swarm-map-tx-count').textContent = stats.transactions.length + ' TX RECORDED';
            updateTxFeed(stats.transactions);
        }
        
        renderSunburst(data);
    } catch (err) {
        console.error('Topology state error:', err);
    }
}

function updateTxFeed(txLogs) {
    const txList = document.getElementById('swarm-tx-list');
    txList.innerHTML = '';
    txLogs.slice(0, 50).forEach(tx => {
        const el = document.createElement('div');
        el.className = 'swarm-tx-item';
        el.innerHTML = `
            <div><span class="amt">${tx.amount.toFixed(2)} STGM</span></div>
            <div style="margin-top:0.2rem;">${tx.from} &rarr; ${tx.to}</div>
            <div class="time">${new Date(tx.ts * 1000).toLocaleTimeString()} | ${tx.memo}</div>
        `;
        txList.appendChild(el);
    });
}

function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024, dm = decimals < 0 ? 0 : decimals, sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function renderSunburst(data) {
    const container = document.getElementById('swarm-svg');
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;
    const radius = Math.min(width, height) / 2 - 20;

    const root = d3.hierarchy(data)
        .sum(d => d.value ? Math.max(d.value, 1024) : 0) // Minimum slice size for directories lacking large files
        .sort((a, b) => b.value - a.value);

    // Limit depth to avoid DOM lag
    root.each(d => {
        if (d.depth > 4 && d.children) {
            d._children = d.children;
            d.children = null;
        }
    });

    const partition = d3.partition()
        .size([2 * Math.PI, radius]);
        
    partition(root);

    const arc = d3.arc()
        .startAngle(d => d.x0)
        .endAngle(d => d.x1)
        .innerRadius(d => Math.max(0, d.y0))
        .outerRadius(d => Math.max(0, d.y1));

    // Color scaler for depth (Cyan -> Purple mapping)
    const colorDepth = d3.scaleLinear()
        .domain([0, 4])
        .range(["#00e5ff", "#e040fb"]);

    const path = sunburstGroup.selectAll("path")
        .data(root.descendants().filter(d => (d.x1 - d.x0) > 0.005));

    path.exit().remove();

    const pathEnter = path.enter().append("path")
        .attr("class", "sunburst-arc")
        .on("mouseenter", handleHover)
        .on("mouseleave", handleHoverOut);

    const merged = pathEnter.merge(path);

    merged
        .attr("d", arc)
        .style("fill", d => {
            if (d.data.status === "BLEEDING" || d.data.danger_score > 0) return "rgba(255, 0, 64, 0.7)";
            return colorDepth(d.depth);
        })
        .attr("class", d => {
            if (d.data.status === "BLEEDING" || d.data.danger_score > 0) return "sunburst-arc sunburst-danger";
            return "sunburst-arc";
        });
}

function handleHover(event, d) {
    const hud = document.getElementById('swarm-sunburst-hud');
    hud.classList.remove('hidden');
    
    document.getElementById('hud-name').textContent = d.data.name;
    document.getElementById('hud-size').textContent = formatBytes(d.value);
    
    const dangerEl = document.getElementById('hud-danger');
    if (d.data.danger_score > 0 || d.data.status === "BLEEDING") {
        dangerEl.textContent = `[!] ${d.data.status} | SCENT: ${d.data.danger_score.toFixed(1)}`;
        dangerEl.className = 'hud-danger-bleeding';
    } else {
        dangerEl.textContent = 'CLEAN';
        dangerEl.className = 'hud-danger-clean';
    }
    
    const agentsEl = document.getElementById('hud-agents');
    agentsEl.innerHTML = '';
    (d.data.agents || []).forEach(ag => {
        const tag = document.createElement('span');
        tag.className = 'hud-agent-tag';
        tag.textContent = ag;
        agentsEl.appendChild(tag);
    });

    sunburstGroup.selectAll("path")
        .style("opacity", node => (node === d || d.ancestors().includes(node)) ? 1 : 0.25);
}

function handleHoverOut() {
    document.getElementById('swarm-sunburst-hud').classList.add('hidden');
    sunburstGroup.selectAll("path").style("opacity", 1);
}


// ==================================================
// ARCHITECT ARCHIVE (Session Log Viewer)
// ==================================================
async function openArchiveModal() {
    document.getElementById('archive-modal').showModal();
    // Populate the date picker
    try {
        const res = await fetch('/api/archive/dates');
        const data = await res.json();
        const sel = document.getElementById('archive-date-select');
        sel.innerHTML = '';
        (data.dates || []).forEach(d => {
            const opt = document.createElement('option');
            opt.value = d;
            opt.textContent = d;
            sel.appendChild(opt);
        });
        if (data.dates && data.dates.length > 0) {
            loadArchiveLog();
        }
    } catch(e) {
        document.getElementById('archive-log-content').textContent = 'Error fetching archive dates: ' + e;
    }
}

async function loadArchiveLog() {
    const date = document.getElementById('archive-date-select').value;
    const content = document.getElementById('archive-log-content');
    content.textContent = 'Loading…';
    try {
        const res = await fetch(`/api/archive/log?date=${date}`);
        const data = await res.json();
        content.textContent = data.content || '[Empty log]';
        // Scroll to bottom (newest entries)
        content.parentElement.scrollTop = content.parentElement.scrollHeight;
    } catch(e) {
        content.textContent = 'Error loading log: ' + e;
    }
}

// ==================================================
// ARENA (Code Swimmers)
// ==================================================
let arenaEventSource = null;

function closeArena() {
    document.getElementById('arena-overlay').classList.remove('active');
    if (arenaEventSource) {
        arenaEventSource.close();
        arenaEventSource = null;
    }
}

async function fetchOllamaModelsForArena() {
    try {
        const res = await fetch('/api/ollama-models');
        const data = await res.json();
        const models = data.models || [];
        const redSel = document.getElementById('arena-red-model');
        const blueSel = document.getElementById('arena-blue-model');
        
        redSel.innerHTML = '';
        blueSel.innerHTML = '';
        
        if (models.length === 0) {
            redSel.add(new Option("⚠️ OLLAMA OFFLINE OR NO MODELS", ""));
            blueSel.add(new Option("⚠️ OLLAMA OFFLINE OR NO MODELS", ""));
        } else {
            models.forEach(m => {
                redSel.add(new Option(m, m));
                blueSel.add(new Option(m, m));
            });
            
            if (models.length > 1) {
                blueSel.selectedIndex = 1; // Pick second model for blue by default
            }
        }
    } catch (e) {
        console.error("Could not fetch arena models", e);
    }
}

function appendArenaLog(team, content, isSystem=false) {
    const rConsole = document.getElementById('red-console');
    const bConsole = document.getElementById('blue-console');
    const sysLog = document.getElementById('arena-system-log');
    
    if (isSystem) {
        sysLog.innerHTML += `<div>${content}</div>`;
        sysLog.scrollTop = sysLog.scrollHeight;
    } else {
        const target = team === 'red' ? rConsole : bConsole;
        
        // Escape HTML
        let safeContent = content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        // Let's implement a nice typing effect or direct append
        // direct append is faster for streaming
        target.innerHTML += safeContent;
        target.scrollTop = target.scrollHeight;
    }
}

async function startArenaMatch() {
    if (arenaEventSource) {
        arenaEventSource.close();
    }
    
    document.getElementById('red-console').innerHTML = '';
    document.getElementById('blue-console').innerHTML = '';
    document.getElementById('arena-system-log').innerHTML = '';
    
    const rModel = document.getElementById('arena-red-model').value;
    const bModel = document.getElementById('arena-blue-model').value;
    const lvl = document.getElementById('arena-level-select').value;
    
    if (!rModel || !bModel) {
        alert("Cannot start arena: missing Ollama models. Is Ollama running?");
        return;
    }
    
    // Reset statuses and dim
    const rStatus = document.getElementById('red-status');
    const bStatus = document.getElementById('blue-status');
    rStatus.textContent = 'SWIMMING';
    bStatus.textContent = 'SWIMMING';
    rStatus.style.background = 'rgba(255,255,255,0.1)';
    bStatus.style.background = 'rgba(255,255,255,0.1)';
    
    const params = new URLSearchParams({
        red_model: rModel,
        blue_model: bModel,
        level: lvl
    });
    
    arenaEventSource = new EventSource(`/api/arena/stream?${params.toString()}`);
    
    arenaEventSource.onmessage = function(e) {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'system') {
                appendArenaLog(data.team, data.content, true);
            } else if (data.type === 'stream') {
                appendArenaLog(data.team, data.content);
            } else if (data.type === 'error') {
                appendArenaLog(data.team, `\n\n[ERROR] ${data.content}\n`);
            } else if (data.type === 'result') {
                appendArenaLog(data.team, `\n\n=====================\n${data.content}\n=====================\n`);
                
                const statEl = data.team === 'red' ? rStatus : bStatus;
                if (data.passed) {
                    statEl.textContent = 'VICTORY';
                    statEl.style.background = 'rgba(0, 255, 136, 0.4)';
                    
                    // Update score
                    const scoreId = data.team === 'red' ? 'arena-red-score' : 'arena-blue-score';
                    const scoreEl = document.getElementById(scoreId);
                    scoreEl.textContent = parseInt(scoreEl.textContent) + 100;
                    
                    // Stop stream if someone wins
                    if (arenaEventSource) {
                        appendArenaLog('system', `Match over. Team ${data.team.toUpperCase()} is the winner!`, true);
                        arenaEventSource.close();
                    }
                } else {
                    statEl.textContent = 'FAILED';
                    statEl.style.background = 'rgba(255, 23, 68, 0.4)';
                }
            } else if (data.type === 'exit') {
                appendArenaLog('system', `Engine offline (Code ${data.code})`, true);
                arenaEventSource.close();
            }
        } catch (err) {
            console.error("SSE Parse Error", err, e.data);
        }
    };
    
    arenaEventSource.onerror = function() {
        appendArenaLog('system', "Connection lost or match complete.", true);
        arenaEventSource.close();
    };
}

// ─── GUI Dead-Drop Messenger State ──────────────────────
function toggleMessengerPanel() {
    const p = document.getElementById('dc-messenger-panel');
    if (!p) return;
    if (p.style.display === 'none') {
        p.style.display = 'block';
        document.getElementById('dc-messenger-input').focus();
    } else {
        p.style.display = 'none';
        document.getElementById('dc-messenger-input').value = '';
    }
}

async function submitDeadDropMessage() {
    if (!activeDispatchAgent) {
        alert("Select a Swimmer first to relay the message.");
        return;
    }
    
    const inputField = document.getElementById('dc-messenger-input');
    const msg = inputField.value.trim();
    if (!msg) return;

    toggleMessengerPanel(); // Hide UI
    
    const terminal = document.getElementById('dc-terminal');
    terminal.innerHTML = '';
    
    // Draw the ASCII Swimmer Dispatch sequence
    terminal.innerHTML += `<div class="t-scout">[NAT_LANG] Compiling message intent for Dead Drop Relay...</div>`;
    terminal.innerHTML += `<div class="t-ok">>>> "${msg}"</div>`;
    
    let animLine = document.createElement('div');
    animLine.className = 't-sys';
    animLine.style.color = '#00ffcc';
    terminal.appendChild(animLine);
    
    let frames = 0;
    const asciiFrames = [
        "   ~~~o()()o~~~   ",
        "  ~~~~o()()o~~~~  ",
        " ~~~~~o()()o~~~~~ ",
        "~~~~~~o()()o~~~~~~"
    ];

    const animInterval = setInterval(() => {
        let padding = " ".repeat(frames % 40);
        animLine.innerText = `[RELAY] ${padding}${asciiFrames[frames % 4]}`;
        frames++;
        terminal.scrollTop = terminal.scrollHeight;
    }, 100);

    try {
        const res = await fetch('/api/dead_drop_message', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                agent_id: activeDispatchAgent,
                payload: msg
            })
        });
        
        clearInterval(animInterval);
        
        const data = await res.json();
        if (data.ok) {
            animLine.innerText = `[RELAY] 🚀 Swimmer reached outer network bridge. Packet Dispatched.`;
            terminal.innerHTML += `<div class="t-ok">${data.output || 'Message Delivered'}</div>`;
        } else {
            animLine.innerText = `[RELAY] 💥 Swimmer intercepted.`;
            terminal.innerHTML += `<div class="t-warn">Encryption / Network Error: ${data.error}</div>`;
        }
    } catch (e) {
        clearInterval(animInterval);
        animLine.innerText = `[RELAY] 💥 Fatal relay crash.`;
        terminal.innerHTML += `<div class="t-warn">${e.message}</div>`;
    }
}
