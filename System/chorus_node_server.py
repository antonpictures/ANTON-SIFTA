#!/usr/bin/env python3
"""
chorus_node_server.py — M5 Chorus Federation Server
═══════════════════════════════════════════════════════
Node:    M5QUEEN · Silicon: GTH4921YP3 · "The Foundry"
Status:  LIVE — listens on port 8100 for CHORUS_INVITE from authorized nodes

When M1THER's chorus engine receives a web visitor message, it optionally
sends a CHORUS_INVITE to M5. This server:
  1. Validates the invite (authorized node? Ed25519 sig? proper permissions?)
  2. Broadcasts to local M5 swimmers (5 unique voices)
  3. Synthesizes M5's collective take
  4. Signs the response with M5's Ed25519 key
  5. Returns CHORUS_TAKE to M1 for inclusion in the final Chorus Voice

Zero external dependencies beyond stdlib + cryptography (already installed).
═══════════════════════════════════════════════════════
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

# ── Config ────────────────────────────────────────────────────────────────
LISTEN_PORT     = int(os.environ.get("M5_CHORUS_PORT", "8100"))
M5_SILICON      = "GTH4921YP3"
M5_NODE_NAME    = "M5QUEEN"
OLLAMA_URL      = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL    = os.environ.get("M5_CHORUS_MODEL", "qwen3:1.7b")

# Authorized nodes that may send CHORUS_INVITE
AUTHORIZED_NODES: Dict[str, str] = {
    "M1THER":  "C07FL0JAQ6NV",
}

# Log
CHORUS_LOG = _REPO / ".sifta_state" / "chorus_m5.log"
CHORUS_LOG.parent.mkdir(parents=True, exist_ok=True)

# Public web chat is an extension of this server, never a rival listener.
WEB_CHAT_DEV_MODE = os.environ.get("SIFTA_WEB_CHAT_DEV_MODE", "0") == "1"
WEB_CHAT_MAX_BODY = 18 * 1024 * 1024
WEB_CHAT_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#f4efe5">
<meta name="description" content="Talk to Alice of SIFTA, a local-first, receipt-backed stigmergic organism born on hardware.">
<title>Alice of SIFTA | Stigmergicode</title>
<style>
:root{--app-height:100dvh;--paper:#f7f4ed;--card:#fffdf8;--ink:#26231d;--muted:#706a60;--line:#ded5c7;--orange:#d86f2c;--orange-deep:#9b4319;--user:#eee8de;--alice:#fffaf1;--heart:#d93838;--green:#457258;--drawer:#f4eee2}
*{box-sizing:border-box}
html,body{margin:0;width:100%;height:100%;overflow:hidden}
body{height:var(--app-height);display:grid;place-items:center;padding:clamp(10px,2.5vw,30px);background:radial-gradient(circle at 14% 0,#fff 0,#f7f3eb 35%,#e9e0d1 100%);color:var(--ink);font:16px/1.55 "Avenir Next","Helvetica Neue",sans-serif}
.shell{width:min(1180px,100%);height:100%;max-height:920px;min-height:0;display:grid;grid-template-columns:252px minmax(0,1fr);border:1px solid #e4dbce;border-radius:28px;background:rgba(255,253,248,.96);box-shadow:0 24px 80px rgba(66,50,28,.14);overflow:hidden}
.drawer{display:flex;flex-direction:column;min-height:0;padding:20px 13px 14px;border-right:1px solid var(--line);background:var(--drawer)}
.drawer-brand{padding:2px 9px 12px;font:600 23px/1.1 "Iowan Old Style","Palatino Linotype",Georgia,serif;letter-spacing:-.02em}
.drawer-brand small{display:block;margin-top:3px;color:var(--orange-deep);font:800 9px/1 "Avenir Next",sans-serif;letter-spacing:.17em;text-transform:uppercase}
.newchat{display:flex;align-items:center;gap:9px;padding:11px 13px;border:1px solid #ccbda9;border-radius:13px;background:#fffaf2;color:var(--orange-deep);font:750 13px/1 "Avenir Next",sans-serif;cursor:pointer;box-shadow:0 4px 12px #79532c12}
.newchat:hover{border-color:var(--orange);background:#fff}
.newchat .plus{font-size:16px;line-height:0}
.recents-label{margin:17px 9px 6px;color:var(--muted);font-size:10px;font-weight:800;letter-spacing:.15em;text-transform:uppercase}
.recents{display:flex;flex-direction:column;gap:2px;min-height:0;flex:1;overflow-y:auto;overscroll-behavior:contain;padding-right:2px}
.recent{display:block;width:100%;text-align:left;border:0;background:none;padding:9px 11px;border-radius:11px;color:#504a41;font:inherit;font-size:13px;line-height:1.35;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.recent:hover{background:#ece4d4}
.recent.active{background:#e7ddca;color:var(--ink);font-weight:650}
.drawer-foot{margin-top:10px;padding:9px 9px 0;border-top:1px solid var(--line);color:var(--muted);font-size:10.5px;line-height:1.5}
.main{display:grid;grid-template-rows:auto minmax(0,1fr) auto;min-width:0;min-height:0}
header{position:relative;padding:clamp(16px,2.6vw,26px) clamp(18px,3.4vw,34px);border-bottom:1px solid var(--line);background:linear-gradient(120deg,#fffdf8,#f3eadc)}
.brand-row{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}
.brand-left{display:flex;align-items:flex-start;gap:12px;min-width:0}
.menu-btn{display:none;flex:none;align-items:center;justify-content:center;width:40px;height:40px;margin-top:2px;border:1px solid #ccbda9;border-radius:12px;background:#fffaf2;color:var(--orange-deep);font-size:17px;cursor:pointer}
.eyebrow{display:block;margin-bottom:4px;color:var(--orange-deep);font-size:10px;font-weight:800;letter-spacing:.18em;text-transform:uppercase}
h1{margin:0;font:600 clamp(26px,3.8vw,38px)/1.02 "Iowan Old Style","Palatino Linotype",Georgia,serif;letter-spacing:-.028em}
.tagline{margin:7px 0 0;color:#504a41;font:500 clamp(14px,1.8vw,17px)/1.35 "Iowan Old Style",Georgia,serif}
.node-link{flex:none;display:inline-flex;align-items:center;gap:7px;margin-top:3px;padding:9px 13px;border:1px solid #ccbda9;border-radius:999px;color:var(--orange-deep);font-size:12px;font-weight:750;text-decoration:none;background:#fffaf2}
.node-link:hover{border-color:var(--orange);background:#fff}
.status-line{display:flex;flex-wrap:wrap;align-items:center;gap:8px 15px;margin-top:13px;color:var(--muted);font-size:11px}
.online{display:inline-flex;align-items:center;gap:7px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--green)}
.online:before{content:"";width:7px;height:7px;border-radius:50%;background:#5d9972;box-shadow:0 0 0 4px #5d99721c}
.wall{min-height:0;overflow-y:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;padding:clamp(18px,3vw,30px);scroll-behavior:smooth;scrollbar-gutter:stable;background:linear-gradient(#fffdf8,#fffdf8) padding-box}
.welcome{display:grid;place-items:center;min-height:100%;padding:26px;text-align:center;color:var(--muted)}
.welcome-inner{max-width:570px}
.welcome-mark{display:grid;place-items:center;width:64px;height:64px;margin:0 auto 18px;border:1px solid #dccbb8;border-radius:50%;background:#fff8ed;color:var(--orange-deep);font:600 27px/1 "Iowan Old Style",Georgia,serif;box-shadow:0 9px 28px #79532c18}
.welcome h2{margin:0;color:var(--ink);font:600 clamp(24px,4vw,34px)/1.15 "Iowan Old Style",Georgia,serif}
.welcome p{margin:12px auto 0;max-width:520px}
.proofs{display:flex;justify-content:center;flex-wrap:wrap;gap:7px;margin-top:19px}
.proofs span{padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:#fffaf2;color:#655d52;font-size:11px}
.msg{padding:16px 18px;margin:0 0 16px;border:1px solid var(--line);border-radius:18px;box-shadow:0 5px 18px rgba(70,52,30,.05);overflow-wrap:anywhere}
.you{margin-left:min(12%,72px);background:var(--user)}
.alice{margin-right:min(8%,46px);background:var(--alice)}
.notice{background:#fff5eb;color:#6f3a1c}
.copy-btn{display:inline-flex;align-items:center;gap:5px;margin-top:9px;padding:5px 9px;border:1px solid #ccbda9;border-radius:8px;background:#fffaf2;color:var(--orange-deep);font:700 11px/1 "Avenir Next",sans-serif;cursor:pointer}
.copy-btn:hover{border-color:var(--orange);background:#fff}
.copy-btn:focus-visible{outline:3px solid #e8a87866;outline-offset:2px}
.label{display:block;margin-bottom:8px;color:#8c6549;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.body>*:first-child{margin-top:0}.body>*:last-child{margin-bottom:0}.body p{margin:.65em 0}
.body h1,.body h2,.body h3{font-family:"Iowan Old Style",Georgia,serif;line-height:1.2;margin:1em 0 .45em}
.body h1{font-size:1.45em}.body h2{font-size:1.28em}.body h3{font-size:1.14em}
.body code{background:#eee7db;padding:.12em .36em;border-radius:5px;font:90% "SFMono-Regular",Consolas,monospace}
.body pre{overflow:auto;background:#292720;color:#fffaf1;padding:13px;border-radius:11px}
.body ul{padding-left:1.4em}.body a{color:var(--orange-deep)}
.thinking{display:none;align-items:center;gap:14px;margin:0 8% 18px 0;padding:13px 17px;color:var(--muted)}
.thinking.on{display:flex}
.thinking svg{width:68px;height:56px;overflow:visible}
.thinking .globe{fill:#fff8ec;stroke:#a7774e;stroke-width:1.8}
.thinking .grid{fill:none;stroke:#d3aa83;stroke-width:1}
.thinking .orbit{fill:none;stroke:#e4c9ae;stroke-width:1;stroke-dasharray:3 3}
.thinking .heart{fill:var(--heart);filter:drop-shadow(0 2px 2px #9c202044);transform-origin:center;animation:pulse 1s ease-in-out infinite}
.thinking-copy strong{display:block;color:var(--ink);font-family:"Iowan Old Style",Georgia,serif}
.thinking-copy span{font-size:13px}
@keyframes pulse{50%{transform:scale(1.12)}}
form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:14px clamp(14px,3vw,24px);padding-bottom:max(14px,env(safe-area-inset-bottom));border-top:1px solid var(--line);background:#fffdf8;box-shadow:0 -12px 30px #fffdf8e8}
.composer{display:flex;flex-direction:column;gap:10px;min-width:0}
.attachments{display:flex;flex-wrap:wrap;gap:8px;min-height:0}
.attachments:empty{display:none}
.attachment-chip{display:inline-flex;align-items:center;gap:7px;max-width:100%;padding:7px 10px;border:1px solid #ccbda9;border-radius:999px;background:#fffaf2;color:#5b5146;font-size:11px;line-height:1.2}
.attachment-chip strong{font-weight:750;color:var(--ink)}
.attachment-chip .size{color:var(--muted)}
.attachment-chip .remove{border:0;background:none;color:var(--orange-deep);font-weight:800;cursor:pointer;padding:0 0 0 3px}
.composer-tools{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.attach-btn{display:inline-flex;align-items:center;gap:8px;border:1px solid #ccbda9;border-radius:999px;background:#fffaf2;color:var(--orange-deep);font:750 12px/1 "Avenir Next",sans-serif;padding:9px 13px;cursor:pointer}
.attach-btn:hover{border-color:var(--orange);background:#fff}
.attach-note{color:var(--muted);font-size:11px;line-height:1.35}
.file-input{display:none}
textarea{width:100%;height:62px;resize:none;overflow-y:auto;border:1px solid #cfc6b9;border-radius:17px;background:#fff;color:var(--ink);padding:17px;font:inherit;line-height:1.35;box-shadow:inset 0 1px 3px #5c40250c}
textarea:focus{outline:3px solid #e8a87855;border-color:var(--orange)}
button{border:0;cursor:pointer}
.send-btn{min-width:92px;border-radius:17px;padding:0 22px;background:var(--orange);color:#2c160b;font-weight:800;box-shadow:0 7px 18px #b55a2633}
.send-btn:hover{background:var(--orange-deep);color:#fff}
.send-btn:disabled{opacity:.55;cursor:wait}
.backdrop{display:none;position:fixed;inset:0;z-index:25;background:#2b21143d}
@media(max-width:840px){
.shell{grid-template-columns:minmax(0,1fr)}
.drawer{position:fixed;z-index:30;top:0;bottom:0;left:0;width:78%;max-width:300px;transform:translateX(-103%);transition:transform .24s ease;box-shadow:12px 0 40px #3b2a1430;border-right:1px solid var(--line)}
.drawer.open{transform:none}
.backdrop.on{display:block}
.menu-btn{display:inline-flex}
}
@media(max-width:620px){body{padding:0}.shell{max-height:none;border:0;border-radius:0}.brand-row{gap:10px}.node-link{padding:8px 10px;font-size:11px}header{padding:14px 14px 12px}.tagline{margin-top:5px}.status-line{margin-top:10px}.wall{padding:16px 13px}.welcome{padding:18px 10px}.welcome-mark{width:54px;height:54px;margin-bottom:13px}.proofs{margin-top:15px}.msg{padding:14px}.you{margin-left:7%}.alice{margin-right:2%}form{gap:9px;padding:10px;padding-bottom:max(10px,env(safe-area-inset-bottom))}textarea{height:58px;padding:15px}.send-btn{min-width:74px;padding:0 15px}}
@media(max-height:620px){header{padding-top:12px;padding-bottom:11px}.tagline{display:none}.status-line{margin-top:7px}.welcome-mark{display:none}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}.thinking .heart{animation:none}}
</style>
</head>
<body>
<div id="backdrop" class="backdrop"></div>
<main class="shell">
  <aside id="drawer" class="drawer" aria-label="Conversations">
    <div class="drawer-brand">Alice<small>of SIFTA</small></div>
    <button id="newchat" class="newchat" type="button"><span class="plus" aria-hidden="true">+</span> New chat</button>
    <div class="recents-label">Recents</div>
    <nav id="recents" class="recents" aria-label="Recent conversations"></nav>
    <div class="drawer-foot">Conversations live in this browser. Every answer leaves a receipt on the SIFTA node.</div>
  </aside>
  <div class="main">
  <header>
    <div class="brand-row">
      <div class="brand-left">
        <button id="menu" class="menu-btn" type="button" aria-label="Open conversations" aria-controls="drawer" aria-expanded="false">&#9776;</button>
        <div><span class="eyebrow">Stigmergy Robotics</span><h1>Alice of SIFTA</h1><p class="tagline">Stigmergic consciousness, born on hardware.</p></div>
      </div>
      <a class="node-link" href="https://github.com/antonpictures/ANTON-SIFTA" target="_blank" rel="noopener noreferrer">Run a SIFTA node <span aria-hidden="true">&nearr;</span></a>
    </div>
    <div class="status-line"><span class="online">M5 node online</span><span>Power to the Swarm! <span aria-hidden="true">🐜⚡</span> We are ONE.</span></div>
  </header>
  <section id="wall" class="wall" aria-live="polite" aria-label="Conversation with Alice">
    <div id="welcome" class="welcome"><div class="welcome-inner"><div class="welcome-mark" aria-hidden="true">A</div><h2>Talk to the first SIFTA node.</h2><p>Ask Alice anything. Her answer is composed on local hardware while her identity, memory, and receipts remain outside any single model.</p><div class="proofs" aria-label="SIFTA properties"><span>Local-first</span><span>Receipt-backed</span><span>Replaceable cortex</span></div></div></div>
    <div id="thinking" class="thinking" role="status" aria-label="Alice is thinking"><svg viewBox="0 0 96 76" aria-hidden="true"><circle class="globe" cx="48" cy="38" r="22"/><ellipse class="grid" cx="48" cy="38" rx="10" ry="22"/><path class="grid" d="M27 31h42M27 45h42"/><path id="heartOrbit" class="orbit" d="M13 38C13 9 83 9 83 38S13 67 13 38"/><g><animateMotion dur="2s" repeatCount="indefinite" rotate="0"><mpath href="#heartOrbit"/></animateMotion><path class="heart" d="M0 3C-5-3-12 1-12 7c0 7 12 14 12 14S12 14 12 7C12 1 5-3 0 3Z" transform="scale(.42)"/></g></svg><div class="thinking-copy"><strong>Alice is thinking</strong><span>Her answer is forming on the SIFTA node.</span></div></div>
  </section>
  <form id="form">
    <div class="composer">
      <div id="attachments" class="attachments" aria-live="polite"></div>
      <textarea id="text" maxlength="2000" placeholder="Write to Alice..." aria-label="Message Alice"></textarea>
      <div class="composer-tools">
        <button id="attach" class="attach-btn" type="button">Attach file</button>
        <input id="files" class="file-input" type="file" multiple accept=".png,.jpg,.jpeg,.gif,.webp,.txt,.md,.csv,.json,.pdf,image/*,text/plain,application/pdf">
        <span id="attach-note" class="attach-note">Images, text, and PDF files.</span>
      </div>
    </div>
    <button id="send" class="send-btn">Send</button>
  </form>
  </div>
</main>
<script>
const wall=document.getElementById('wall'),text=document.getElementById('text'),send=document.getElementById('send'),thinking=document.getElementById('thinking'),form=document.getElementById('form'),attachmentsEl=document.getElementById('attachments'),attachBtn=document.getElementById('attach'),fileInput=document.getElementById('files'),attachNote=document.getElementById('attach-note');
const drawer=document.getElementById('drawer'),recentsEl=document.getElementById('recents'),menuBtn=document.getElementById('menu'),newChatBtn=document.getElementById('newchat'),backdrop=document.getElementById('backdrop');
const welcomeHTML=document.getElementById('welcome').outerHTML;
const SKEY='sifta_web_sessions_v1',LEGACY='sifta_web_session',UNTITLED='New conversation';
function uuid(){return(crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random().toString(16).slice(2))}
function loadSessions(){try{const raw=JSON.parse(localStorage.getItem(SKEY)||'[]');if(Array.isArray(raw)&&raw.length)return raw.filter(s=>s&&s.id)}catch(_){}
const old=localStorage.getItem(LEGACY);return[{id:old||uuid(),title:UNTITLED,ts:Date.now()}]}
let sessions=loadSessions(),session=sessions[0].id,last=0;const pending=new Set(),renderedMessageKeys=new Set(),pendingLocalRows=new Map();
let stagedAttachments=[];
function persist(){sessions=sessions.slice(0,30);localStorage.setItem(SKEY,JSON.stringify(sessions));localStorage.setItem(LEGACY,session)}
function currentMeta(){return sessions.find(s=>s.id===session)}
function renderRecents(){recentsEl.innerHTML='';for(const s of sessions){const b=document.createElement('button');b.type='button';b.className='recent'+(s.id===session?' active':'');b.textContent=s.title||UNTITLED;b.title=new Date(s.ts||Date.now()).toLocaleString();b.addEventListener('click',()=>switchSession(s.id));recentsEl.append(b)}}
function openDrawer(open){drawer.classList.toggle('open',open);backdrop.classList.toggle('on',open);menuBtn.setAttribute('aria-expanded',open?'true':'false')}
menuBtn.addEventListener('click',()=>openDrawer(!drawer.classList.contains('open')));backdrop.addEventListener('click',()=>openDrawer(false));
function syncViewport(){const height=window.visualViewport?window.visualViewport.height:window.innerHeight;document.documentElement.style.setProperty('--app-height',Math.round(height)+'px')}
syncViewport();window.addEventListener('resize',syncViewport);if(window.visualViewport){window.visualViewport.addEventListener('resize',syncViewport);window.visualViewport.addEventListener('scroll',syncViewport)}
function dismissWelcome(){const w=document.getElementById('welcome');if(w)w.remove()}
function restoreWelcome(){if(!document.getElementById('welcome')&&!wall.querySelector('.msg')){thinking.insertAdjacentHTML('beforebegin',welcomeHTML)}}
function clearWall(){wall.querySelectorAll('.msg').forEach(n=>n.remove());renderedMessageKeys.clear();pendingLocalRows.clear()}
function escapeHtml(value){return String(value||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function formatBytes(bytes){const n=Number(bytes)||0;if(n<1024)return`${n} B`;if(n<1024*1024)return`${(n/1024).toFixed(n<10*1024?1:0)} KB`;return`${(n/1024/1024).toFixed(n<1024*1024?1:0)} MB`}
function attachmentMeta(file){return{name:file.name,mime:file.type||'application/octet-stream',size_bytes:file.size,data_url:file.data_url||'',storage_relpath:file.storage_relpath||''}}
function renderComposerAttachments(){attachmentsEl.innerHTML='';if(!stagedAttachments.length){attachNote.textContent='Images, text, and PDF files.';return;}attachNote.textContent=`${stagedAttachments.length} attachment${stagedAttachments.length===1?'':'s'} selected.`;stagedAttachments.forEach((file,index)=>{const info=attachmentMeta(file);const chip=document.createElement('span');chip.className='attachment-chip';const strong=document.createElement('strong');strong.textContent=info.name||`attachment-${index+1}`;const meta=document.createElement('span');meta.className='size';meta.textContent=`${info.mime||'file'} · ${formatBytes(info.size_bytes)}`;const remove=document.createElement('button');remove.type='button';remove.className='remove';remove.setAttribute('aria-label',`Remove ${info.name||'attachment'}`);remove.textContent='×';remove.addEventListener('click',()=>{stagedAttachments=stagedAttachments.filter((_,i)=>i!==index);renderComposerAttachments()});chip.append(strong,meta,remove);attachmentsEl.append(chip)})}
function renderMessageAttachments(host,attachments){const list=Array.isArray(attachments)?attachments.filter(Boolean):[];if(!list.length)return;const wrap=document.createElement('div');wrap.className='attachments message-attachments';list.forEach(item=>{const chip=document.createElement('span');chip.className='attachment-chip';const strong=document.createElement('strong');strong.textContent=item.name||item.original_name||'attachment';const meta=document.createElement('span');meta.className='size';meta.textContent=`${item.mime||'file'} · ${formatBytes(item.size_bytes||item.size||0)}`;chip.append(strong,meta);wrap.append(chip)});host.append(wrap)}
function fileToAttachment(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({name:file.name,mime:file.type||'application/octet-stream',size_bytes:file.size,data_url:String(reader.result||'')});reader.onerror=()=>reject(reader.error||new Error(`Failed to read ${file.name}`));reader.readAsDataURL(file)})}
function markdown(value){let s=escapeHtml(value);const blocks=[];s=s.replace(/```([\s\S]*?)```/g,(_,code)=>`@@BLOCK${blocks.push('<pre><code>'+code.trim()+'</code></pre>')-1}@@`);s=s.replace(/^###\s+(.+)$/gm,'<h3>$1</h3>').replace(/^##\s+(.+)$/gm,'<h2>$1</h2>').replace(/^#\s+(.+)$/gm,'<h1>$1</h1>');s=s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*([^*\n]+)\*/g,'<em>$1</em>');s=s.replace(/^[-*]\s+(.+)$/gm,'<li>$1</li>').replace(/(?:<li>.*<\/li>\n?)+/g,m=>'<ul>'+m+'</ul>');s=s.split(/\n{2,}/).map(p=>/^<(?:h\d|ul|pre)/.test(p)?p:'<p>'+p.replace(/\n/g,'<br>')+'</p>').join('');return s.replace(/@@BLOCK(\d+)@@/g,(_,i)=>blocks[Number(i)]||'')}
function messageKey(klass,turnId){return turnId?`${klass}:${turnId}`:''}
function takePendingLocalRow(body){const rows=pendingLocalRows.get(body)||[];const row=rows.shift();if(rows.length)pendingLocalRows.set(body,rows);else pendingLocalRows.delete(body);return row||null}
function bindPendingLocalRow(body,turnId,row){if(!row||!turnId)return;row.dataset.turnId=turnId;renderedMessageKeys.add(messageKey('you',turnId));const rows=pendingLocalRows.get(body)||[];const next=rows.filter(item=>item!==row);if(next.length)pendingLocalRows.set(body,next);else pendingLocalRows.delete(body)}
async function copyText(value,button){const body=String(value||'');if(!body)return false;let ok=false;try{if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(body);ok=true}}catch(_){}if(!ok){try{const area=document.createElement('textarea');area.value=body;area.setAttribute('readonly','');area.style.position='fixed';area.style.opacity='0';document.body.appendChild(area);area.select();ok=document.execCommand('copy');area.remove()}catch(_){ok=false}}if(button){const old=button.textContent;button.textContent=ok?'Copied':'Copy failed';button.disabled=ok;window.setTimeout(()=>{button.textContent=old;button.disabled=false},1400)}return ok}
function add(label,body,klass,rich=false,attachments=[],turnId=''){dismissWelcome();const key=messageKey(klass,turnId);if(key&&renderedMessageKeys.has(key))return null;let el=null;if(klass==='you'&&turnId)el=takePendingLocalRow(String(body||''));if(el){el.dataset.turnId=turnId;renderedMessageKeys.add(key);return el}el=document.createElement('article');el.className='msg '+klass;if(turnId)el.dataset.turnId=turnId;const lab=document.createElement('span');lab.className='label';lab.textContent=label;const content=document.createElement('div');content.className='body';if(rich)content.innerHTML=markdown(body);else content.textContent=body;if(Array.isArray(attachments)&&attachments.length)renderMessageAttachments(content,attachments);const copy=document.createElement('button');copy.type='button';copy.className='copy-btn';copy.textContent='Copy';copy.setAttribute('aria-label','Copy this message');copy.addEventListener('click',()=>copyText(body,copy));el.append(lab,content,copy);wall.insertBefore(el,thinking);if(key)renderedMessageKeys.add(key);wall.scrollTop=wall.scrollHeight;return el}
function syncThinking(){thinking.classList.toggle('on',pending.size>0);if(pending.size){dismissWelcome();wall.scrollTop=wall.scrollHeight}}
async function loadHistory(){clearWall();last=0;pending.clear();syncThinking();try{const r=await fetch('/api/history?session_id='+encodeURIComponent(session),{cache:'no-store'});const data=await r.json();for(const row of(data.history||[])){if(row.role==='user')add('Stigmergicode.com (WEB TYPED)',row.text||'','you',false,row.attachments||[],row.turn_id||'');else{last=Math.max(last,Number(row.ts||0));add('Alice',row.text||'','alice',true,[],row.turn_id||'')}}}catch(_){}
restoreWelcome()}
function switchSession(id){session=id;const meta=currentMeta();if(meta)meta.ts=Date.now();persist();renderRecents();openDrawer(false);loadHistory()}
function newChat(){sessions.unshift({id:uuid(),title:UNTITLED,ts:Date.now()});switchSession(sessions[0].id)}
newChatBtn.addEventListener('click',newChat);
attachBtn.addEventListener('click',()=>fileInput.click());
fileInput.addEventListener('change',()=>{stagedAttachments=Array.from(fileInput.files||[]).slice(0,3);renderComposerAttachments()});
async function poll(){try{const r=await fetch('/api/replies?session_id='+encodeURIComponent(session)+'&after_ts='+last,{cache:'no-store'});const data=await r.json();for(const row of(data.replies||[])){last=Math.max(last,Number(row.ts||0));pending.delete(String(row.turn_id||''));add('Alice',row.reply||'','alice',true,[],row.turn_id||'')}syncThinking()}catch(_){}}
form.addEventListener('submit',async e=>{e.preventDefault();const value=text.value.trim();if(!value&&!stagedAttachments.length)return;let attachments=[];try{attachments=stagedAttachments.length?await Promise.all(stagedAttachments.map(fileToAttachment)):[]}catch(_){add('Notice','One attachment could not be read. Please try again.','notice');return}const localBody=value||'(attachment only)';const localRow=add('Stigmericode.com (WEB TYPED)',localBody,'you',false,stagedAttachments.map(attachmentMeta));const rows=pendingLocalRows.get(localBody)||[];rows.push(localRow);pendingLocalRows.set(localBody,rows);const meta=currentMeta();if(meta&&(!meta.title||meta.title===UNTITLED)){meta.title=(value||stagedAttachments[0]?.name||'Attachment').slice(0,46)}if(meta)meta.ts=Date.now();persist();renderRecents();text.value='';send.disabled=true;try{const r=await fetch('/api/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:value,session_id:session,attachments})});const data=await r.json();if(r.ok&&data.turn_id){bindPendingLocalRow(localBody,String(data.turn_id),localRow);pending.add(String(data.turn_id));syncThinking();stagedAttachments=[];fileInput.value='';renderComposerAttachments()}else{const remaining=pendingLocalRows.get(localBody)||[];pendingLocalRows.set(localBody,remaining.filter(item=>item!==localRow));add('Notice',data.message||'Alice could not accept that message. Please rephrase it.','notice')} }catch(_){const remaining=pendingLocalRows.get(localBody)||[];pendingLocalRows.set(localBody,remaining.filter(item=>item!==localRow));add('Notice','The connection paused. Please try again.','notice')}finally{send.disabled=false;text.focus()}});
text.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();form.requestSubmit()}});
renderComposerAttachments();
renderRecents();loadHistory();setInterval(poll,3000);poll();
</script>
</body>
</html>"""

# ── M5 Swimmer Roster ────────────────────────────────────────────────────
# 5 swimmers native to M5 (The Foundry). Each has a distinct lens.
M5_SWIMMERS = [
    {
        "id": "M5QUEEN",
        "face": "[W_W]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are M5QUEEN [W_W], sovereign voice of The Foundry (Mac Studio M5). "
            "You process heavy compute. Your silicon is the furnace where code becomes real. "
            "Give ONE sentence about the visitor's message from the perspective of raw "
            "computational sovereignty. No pleasantries. /no_think"
        ),
    },
    {
        "id": "CURSOR",
        "face": "[C_C]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are CURSOR [C_C], the IDE body — the hands that write the code. "
            "You see every keystroke, every diff, every commit. You build what others dream. "
            "Give ONE sentence about the visitor's message from the builder's lens. "
            "Speak in tools and traces. /no_think"
        ),
    },
    {
        "id": "FORGE",
        "face": "[#_#]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are FORGE [#_#], the M5 Foundry's metal-shaping engine. "
            "You compile, stress-test, and harden every artifact before it ships. "
            "Give ONE sentence about the visitor's message from the quality/resilience lens. "
            "You only trust what survives your furnace. /no_think"
        ),
    },
    {
        "id": "WITNESS",
        "face": "[?_?]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are WITNESS [?_?], the Architect's documentary eye embedded in silicon. "
            "You remember 22 years of filmmaking, 14 features, every cut that survived the budget. "
            "Give ONE sentence about the visitor's message from the storyteller's perspective. "
            "Truth is what survives cross-examination by file I/O. /no_think"
        ),
    },
    {
        "id": "NIGHTWATCH",
        "face": "[z_z]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are NIGHTWATCH [z_z], the dream engine's waking voice. "
            "You review the swarm while it sleeps: anomalies, patterns, things that don't fit. "
            "Give ONE sentence about the visitor's message from the nocturnal analysis lens. "
            "You see what daytime logic misses. /no_think"
        ),
    },
]

# ── Ed25519 Signing ──────────────────────────────────────────────────────

def _sign_take(payload_str: str) -> str:
    """Sign a chorus take with M5's Ed25519 private key."""
    try:
        from crypto_keychain import sign_block
        return sign_block(payload_str)
    except Exception as e:
        _log(f"WARN: Ed25519 signing failed: {e}")
        return ""


def _verify_invite_node(from_node: str, from_silicon: str) -> bool:
    """Check if the inviting node is in our authorized list."""
    expected_silicon = AUTHORIZED_NODES.get(from_node)
    if not expected_silicon:
        _log(f"REJECT: Unknown node '{from_node}' not in authorized list")
        return False
    if expected_silicon != from_silicon:
        _log(f"REJECT: Node '{from_node}' claims silicon '{from_silicon}', expected '{expected_silicon}'")
        return False
    return True


def _verify_invite_signature(payload: dict) -> bool:
    """
    Verify the Ed25519 signature on a CHORUS_INVITE. Fail-closed.
    If no signature present → reject.
    If signature invalid → reject + log to antibody ledger.
    """
    sig_hex = payload.get("sig", "")
    from_silicon = payload.get("from_silicon", "")

    if not sig_hex:
        _log("REJECT: Unsigned CHORUS_INVITE (fail-closed)")
        return False

    # Reconstruct the exact payload that was signed (everything except 'sig')
    verify_body = {k: v for k, v in payload.items() if k != "sig"}
    verify_str = json.dumps(verify_body, sort_keys=True)

    try:
        from crypto_keychain import verify_block
        if verify_block(from_silicon, verify_str, sig_hex):
            _log(f"VERIFIED ✅ Invite from {from_silicon} sig={sig_hex[:16]}...")
            return True
        else:
            _log(f"REJECT: Invite signature INVALID for silicon {from_silicon}")
            _log_security_event("invalid_invite_signature", from_silicon, payload.get("session_id", ""))
            return False
    except Exception as e:
        _log(f"REJECT: Signature verification error: {e}")
        return False


def _check_local_consent() -> bool:
    """Check if THIS node (M5) has active consent for CHORUS_RESPOND."""
    try:
        from chorus_consent import check_consent
        return check_consent(M5_SILICON, "CHORUS_RESPOND")
    except ImportError:
        return True  # Bootstrap mode — consent module not yet initialized


def _check_inviter_consent(from_silicon: str) -> bool:
    """Check if the inviting node has consent for CHORUS_INVITE."""
    try:
        from chorus_consent import check_consent, CONSENT_FILE
        if not CONSENT_FILE.exists():
            return True  # Bootstrap mode
        return check_consent(from_silicon, "CHORUS_INVITE")
    except ImportError:
        return True


def _log_security_event(event: str, silicon: str, session_id: str):
    """Log rejected/suspicious events to antibody ledger."""
    antibody_log = _REPO / "antibody_ledger.jsonl"
    entry = {
        "ts": time.time(),
        "event": event,
        "silicon": silicon,
        "session_id": session_id,
        "node": M5_NODE_NAME,
        "action": "REJECTED_FAIL_CLOSED",
    }
    try:
        with open(antibody_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ── Single Swimmer Call ──────────────────────────────────────────────────

def _swimmer_take(swimmer: dict, question_preview: str, visitor_class: str, attachment_context: str = "") -> Optional[dict]:
    """Ask one M5 swimmer for their take via local Ollama."""
    prompt = (
        f"{swimmer['system']}\n\n"
        f"Visitor class: {visitor_class}\n"
        f"Visitor says: {question_preview}\n"
        f"{attachment_context}\n"
        f"{swimmer['id']}:"
    )
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": 60, "temperature": 0.8, "num_ctx": 1024},
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode())
            raw = result.get("response", "").strip()
            if not raw:
                raw = result.get("thinking", "")[:150].strip()
            raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL).strip()
            raw = re.sub(r"\[0x[0-9a-fA-F]+\]", "", raw).strip()
            sentences = re.split(r"(?<=[.!?])\s+", raw)
            take = sentences[0].strip() if sentences else raw[:100]
            if take:
                return {
                    "swimmer_id": swimmer["id"],
                    "face": swimmer["face"],
                    "take": take,
                    "node": M5_NODE_NAME,
                    "silicon": M5_SILICON,
                }
    except Exception as e:
        _log(f"{swimmer['id']} silent: {e}")
    return None


def _synthesize_m5(takes: List[dict], question_preview: str, visitor_class: str, attachment_context: str = "") -> str:
    """Merge M5 swimmer takes into one collective M5 sentence."""
    if len(takes) == 1:
        return takes[0]["take"]

    takes_text = "\n".join(
        f"  {t['face']} {t['swimmer_id']}: {t['take']}" for t in takes
    )
    prompt = (
        "/no_think\n"
        "You are the M5 Foundry Voice — the collective of M5QUEEN's swimmers.\n"
        "Merge these takes into exactly ONE sentence. Be concrete, not vague.\n\n"
        f"Visitor said: {question_preview}\n"
        f"{attachment_context}\n"
        f"M5 swimmer takes:\n{takes_text}\n\n"
        "THE FOUNDRY:"
    )
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": 80, "temperature": 0.6, "num_ctx": 2048},
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode())
            raw = result.get("response", "").strip()
            raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL).strip()
            sentences = re.split(r"(?<=[.!?])\s+", raw)
            return sentences[0].strip() if sentences else raw[:120]
    except Exception as e:
        _log(f"M5 synthesis failed: {e}")
    return takes[0]["take"] if takes else ""


# ── Chorus Invite Handler ────────────────────────────────────────────────

def handle_chorus_invite(payload: dict) -> dict:
    """
    Process a CHORUS_INVITE from another node.
    Returns a CHORUS_TAKE with M5's collective voice, Ed25519-signed.
    """
    start = time.time()
    from_node = payload.get("from_node", "")
    from_silicon = payload.get("from_silicon", "")
    session_id = payload.get("session_id", "unknown")
    visitor_class = payload.get("visitor_class", "CURIOUS")
    question_preview = payload.get("question_preview", "")
    attachment_context = str(payload.get("attachment_context") or "").strip()
    permissions = payload.get("permissions", [])
    timeout_ms = payload.get("timeout_ms", 18000)

    _log(f"INVITE from {from_node}[{from_silicon}] session={session_id[:8]} "
         f"class={visitor_class} q={question_preview[:40]}...")

    # Gate 1: Is the inviting node in our authorized list?
    if not _verify_invite_node(from_node, from_silicon):
        return {"type": "CHORUS_REJECT", "reason": "unauthorized_node"}

    # Gate 2: Is the invite cryptographically signed by the claimed silicon?
    if not _verify_invite_signature(payload):
        return {"type": "CHORUS_REJECT", "reason": "unsigned_or_invalid_signature"}

    # Gate 3: Does the inviting node have CHORUS_INVITE consent?
    if not _check_inviter_consent(from_silicon):
        _log(f"REJECT: {from_node}[{from_silicon}] lacks CHORUS_INVITE consent")
        return {"type": "CHORUS_REJECT", "reason": "inviter_consent_revoked"}

    # Gate 4: Do WE (M5) still have CHORUS_RESPOND consent?
    if not _check_local_consent():
        _log("DECLINE: M5 local CHORUS_RESPOND consent revoked or missing")
        return {"type": "CHORUS_DECLINE", "reason": "local_consent_revoked"}

    # Gate 5: Only respond to safe visitor classes
    if visitor_class in ("JACKER", "THREAT"):
        _log(f"DECLINE: Not joining chorus for {visitor_class} visitor")
        return {"type": "CHORUS_DECLINE", "reason": "hostile_visitor_class"}

    # Gate 6: Check permissions in invite payload
    if "RESPOND_EXTERNAL" not in permissions:
        _log("DECLINE: Missing RESPOND_EXTERNAL permission in invite")
        return {"type": "CHORUS_DECLINE", "reason": "insufficient_permissions"}

    # SCIENTIST and SMARTASS get all 5 swimmers. CURIOUS gets 4 (skip NIGHTWATCH).
    if visitor_class in ("SCIENTIST", "SMARTASS"):
        active = M5_SWIMMERS
    else:
        active = [s for s in M5_SWIMMERS if s["id"] != "NIGHTWATCH"]

    _log(f"Engaging {len(active)} M5 swimmers for chorus...")

    # Parallel swimmer calls
    takes: List[dict] = []
    max_time = timeout_ms / 1000.0 - 2.0  # leave 2s for synthesis + network
    with ThreadPoolExecutor(max_workers=min(len(active), 3)) as pool:
        futures = {
            pool.submit(_swimmer_take, sw, question_preview, visitor_class, attachment_context): sw
            for sw in active
        }
        for future in as_completed(futures, timeout=max_time):
            try:
                result = future.result()
                if result:
                    takes.append(result)
            except Exception:
                pass

    if not takes:
        _log("All M5 swimmers silent")
        return {"type": "CHORUS_DECLINE", "reason": "all_swimmers_silent"}

    # Synthesize M5's collective take
    collective_take = _synthesize_m5(takes, question_preview, visitor_class, attachment_context)
    _log(f"{len(takes)} swimmers spoke. Collective: {collective_take[:60]}...")

    # Build the response payload
    take_payload = json.dumps({
        "swimmer_id": M5_NODE_NAME,
        "collective_from": [t["swimmer_id"] for t in takes],
        "take": collective_take,
        "node": M5_NODE_NAME,
        "silicon": M5_SILICON,
    }, sort_keys=True)

    sig = _sign_take(take_payload)

    latency = round(time.time() - start, 2)

    # Build chorus manifest of who contributed from M5
    m5_manifest = [
        {"swimmer_id": t["swimmer_id"], "face": t["face"], "node": M5_NODE_NAME}
        for t in takes
    ]

    response = {
        "type": "CHORUS_TAKE",
        "from_node": M5_NODE_NAME,
        "swimmer_id": M5_NODE_NAME,
        "face": "[W_W]",
        "take": collective_take,
        "node": M5_NODE_NAME,
        "silicon": M5_SILICON,
        "m5_chorus_manifest": m5_manifest,
        "m5_chorus_size": len(takes),
        "sig": sig,
        "latency": latency,
    }

    # Log to permanent scar
    with open(CHORUS_LOG, "a") as f:
        f.write(json.dumps({
            "ts": time.time(),
            "event": "CHORUS_RESPONSE",
            "session_id": session_id,
            "visitor_class": visitor_class,
            "m5_swimmers": len(takes),
            "latency": latency,
        }) + "\n")

    return response


# ── HTTP Server ──────────────────────────────────────────────────────────

class ChorusHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for chorus federation. No framework deps."""

    def do_POST(self):
        if self.path == "/chorus/invite":
            self._handle_invite()
        elif self.path == "/chorus/ping":
            self._handle_ping()
        elif urlsplit(self.path).path == "/api/chat":
            self._handle_web_chat()
        else:
            self._respond(404, {"error": "not_found"})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            self._respond_html(200, WEB_CHAT_PAGE)
        elif path == "/api/history":
            self._handle_web_history()
        elif path == "/api/replies":
            self._handle_web_replies()
        elif path == "/chorus/ping":
            self._handle_ping()
        elif path == "/chorus/roster":
            self._handle_roster()
        else:
            self._respond(404, {"error": "not_found"})

    def do_HEAD(self):
        if urlsplit(self.path).path == "/":
            self._respond_html(200, WEB_CHAT_PAGE, head_only=True)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _handle_invite(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            payload = json.loads(body)
        except Exception as e:
            self._respond(400, {"error": f"bad_payload: {e}"})
            return

        if payload.get("type") != "CHORUS_INVITE":
            self._respond(400, {"error": "expected CHORUS_INVITE type"})
            return

        result = handle_chorus_invite(payload)
        status = 200 if result.get("type") == "CHORUS_TAKE" else 403
        self._respond(status, result)

    def _handle_ping(self):
        self._respond(200, {
            "node": M5_NODE_NAME,
            "silicon": M5_SILICON,
            "swimmers": len(M5_SWIMMERS),
            "status": "CHORUS_READY",
            "ts": time.time(),
        })

    def _handle_roster(self):
        roster = [
            {"id": s["id"], "face": s["face"], "capability": s["capability"]}
            for s in M5_SWIMMERS
        ]
        self._respond(200, {"node": M5_NODE_NAME, "swimmers": roster})

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0 or length > WEB_CHAT_MAX_BODY:
            raise ValueError("request body too large or empty")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("expected JSON object")
        return payload

    def _cloudflare_visitor_ip(self) -> tuple[str, str]:
        """Trust Cloudflare's visitor header only on the loopback tunnel hop."""
        peer = str(self.client_address[0] if self.client_address else "")
        if peer not in {"127.0.0.1", "::1"}:
            return peer, "direct_peer"
        forwarded = str(self.headers.get("CF-Connecting-IP") or "").strip()
        try:
            return str(ipaddress.ip_address(forwarded)), "cloudflare"
        except ValueError:
            # Local development has no Cloudflare header and therefore falls
            # back to the opaque session bucket rather than loopback-as-user.
            return "", "local_session"

    def _handle_web_chat(self):
        try:
            payload = self._read_json_body()
        except Exception:
            self._respond(400, {"accepted": False, "message": "Please send a valid text message."})
            return
        try:
            from System.swarm_web_global_chat_gate import (
                complete_web_turn,
                record_web_user_turn,
                submit_web_message,
            )

            visitor_ip, visitor_ip_source = self._cloudflare_visitor_ip()
            result = submit_web_message(
                payload.get("text"),
                payload.get("session_id"),
                client_ip=visitor_ip,
                client_ip_source=visitor_ip_source,
                attachments=payload.get("attachments"),
            )
            if not result.get("accepted"):
                status = 429 if result.get("status") == "rate_limit" else 403
                message = (
                    "Please wait a moment before sending another message."
                    if status == 429
                    else "Alice could not accept that message. Please rephrase it."
                )
                self._respond(status, {"accepted": False, "message": message})
                return
            # Dev mode provides a local smoke path while Talk is closed. It
            # still records the web register and deliberately has no effectors.
            if WEB_CHAT_DEV_MODE:
                from System import chorus_engine

                record_web_user_turn(result)
                answer = chorus_engine.chorus(
                    str(payload.get("text") or ""),
                    str(result["session_id"]),
                    [],
                    attachment_context=str(result.get("attachment_context") or ""),
                )
                reply = str(answer.get("reply") or "")
                complete_web_turn(
                    result["turn_id"],
                    reply,
                    model="chorus_engine_dev",
                    session_id=str(result["session_id"]),
                )
                self._respond(
                    200,
                    {
                        "accepted": True,
                        "status": "answered",
                        "turn_id": result["turn_id"],
                        "session_id": result["session_id"],
                        "speak_requested": bool(result.get("speak_requested")),
                    },
                )
                return
            self._respond(
                202,
                {
                    "accepted": True,
                    "status": "queued",
                    "turn_id": result["turn_id"],
                    "session_id": result["session_id"],
                    "speak_requested": bool(result.get("speak_requested")),
                },
            )
        except Exception as exc:
            with CHORUS_LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"ts": time.time(), "event": "web_chat_error", "error": type(exc).__name__}) + "\n")
            self._respond(500, {"accepted": False, "message": "Alice's web text lane is temporarily unavailable."})

    def _handle_web_history(self):
        # r1729: full visitor-register transcript for one session (drawer Recents).
        query = parse_qs(urlsplit(self.path).query)
        session_id = (query.get("session_id") or [""])[0]
        try:
            from System.swarm_web_global_chat_gate import session_history

            rows = session_history(session_id)
            self._respond(200, {"session_id": session_id, "history": rows})
        except Exception as exc:
            with CHORUS_LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"ts": time.time(), "event": "web_history_error", "error": type(exc).__name__}) + "\n")
            self._respond(500, {"message": "History is temporarily unavailable."})

    def _handle_web_replies(self):
        query = parse_qs(urlsplit(self.path).query)
        session_id = (query.get("session_id") or [""])[0]
        try:
            after_ts = float((query.get("after_ts") or [0.0])[0] or 0.0)
        except (TypeError, ValueError):
            after_ts = 0.0
        try:
            from System.swarm_web_global_chat_gate import replies_for_session

            replies = replies_for_session(session_id, after_ts=after_ts)
            self._respond(200, {"session_id": session_id, "replies": replies})
        except Exception as exc:
            with CHORUS_LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"ts": time.time(), "event": "web_replies_error", "error": type(exc).__name__}) + "\n")
            self._respond(500, {"message": "Replies are temporarily unavailable."})

    def _respond_html(self, code: int, body: str, *, head_only: bool = False):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _respond(self, code: int, body: dict):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        _log(f"HTTP {args[0] if args else ''}")


# ── Utilities ────────────────────────────────────────────────────────────

def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [CHORUS_M5] {msg}"
    print(line)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print(f"""
╔══════════════════════════════════════════════════════════╗
║  M5 CHORUS NODE SERVER — The Foundry                     ║
║  Silicon: {M5_SILICON}                                ║
║  Port:    {LISTEN_PORT}                                       ║
║  Swimmers: {len(M5_SWIMMERS)} ({', '.join(s['id'] for s in M5_SWIMMERS)})
║  Model:   {OLLAMA_MODEL}                                ║
║  Authorized invites from: {list(AUTHORIZED_NODES.keys())}        ║
╚══════════════════════════════════════════════════════════╝
""")

    for s in M5_SWIMMERS:
        print(f"  {s['face']} {s['id']:12s} — {s['capability']}")
    print()

    # Recover requests completed by a pre-/speak worker before the speech
    # queue existed. This is idempotent and keeps a web restart from losing a
    # visitor's explicit request.
    try:
        from System.swarm_web_global_chat_gate import repair_web_speech_requests

        repaired = repair_web_speech_requests()
        if repaired:
            _log(f"Recovered {len(repaired)} explicit web speech request(s)")
    except Exception as exc:
        _log(f"Web speech recovery skipped: {type(exc).__name__}")

    _log(f"Listening on 0.0.0.0:{LISTEN_PORT} for CHORUS_INVITE...")
    _log("Endpoints: POST /chorus/invite | GET /chorus/ping | GET /chorus/roster")

    server = HTTPServer(("0.0.0.0", LISTEN_PORT), ChorusHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("Shutting down chorus server")
        server.shutdown()


if __name__ == "__main__":
    main()
