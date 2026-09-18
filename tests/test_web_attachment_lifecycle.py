"""Execute the production async send handler with deferred I/O in Node.

These are JS lifecycle tests, not rendered-browser or public-delivery evidence.
"""
import ast
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def web_script():
    tree = ast.parse((ROOT / 'System/chorus_node_server.py').read_text())
    html = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                and isinstance(n.value, str) and '<script>' in n.value and 'stagedAttachments' in n.value)
    return html.split('<script>', 1)[1].split('</script>', 1)[0]


def test_entire_web_script_parses():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for JS execution')
    run = subprocess.run([node, '--check'], input=web_script(), text=True, capture_output=True)
    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize('scenario', ['double_submit', 'new_attachment', 'switch_session',
                                    'failed_send', 'read_failure', 'history_refresh'])
def test_send_lifetime(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for JS execution')
    script = web_script()
    helpers = script.split('let stagedAttachments=', 1)[1].split('function persist()', 1)[0]
    helpers = 'let stagedAttachments=' + helpers
    switch = script.split('function switchSession(', 1)[1].split('function newChat()', 1)[0]
    switch = 'function switchSession(' + switch
    handler = script.split("form.addEventListener('submit',", 1)[1].split("text.addEventListener('keydown'", 1)[0]
    handler = "form.addEventListener('submit'," + handler
    prelude = r'''
const assert=require('node:assert/strict');
let session='A',viewEpoch=0,historyLoads=0,submit,requests=[],rendered=[],resolveRead,rejectRead;
const text={value:'describe this',focus(){}},send={disabled:false},fileInput={value:'image'},UNTITLED='New conversation';
const pending=new Set(),pendingLocalRows=new Map();
const form={addEventListener(name,fn){submit=fn}};
const meta={title:UNTITLED};
const currentMeta=()=>meta,persist=()=>{},renderRecents=()=>{},openDrawer=()=>{},syncThinking=()=>{};
const renderComposerAttachments=()=>{},attachmentMeta=file=>({name:file.name});
function element(){return {isConnected:true,children:[],append(child){this.children.push(child)},remove(){this.isConnected=false},addEventListener(name,fn){this.click=fn}}}
const document={createElement:element};
function add(label,body){const row=element();row.label=label;row.body=body;rendered.push(row);return row}
function bindPendingLocalRow(body,id,row){row.bound=id}
async function loadHistory(){historyLoads++;viewEpoch++}
const read=new Promise((resolve,reject)=>{resolveRead=resolve;rejectRead=reject});
const fileToAttachment=file=>read.then(()=>({name:file.name,data_url:'test'}));
const fetch=async(url,options)=>{requests.push(JSON.parse(options.body));if(SCENARIO==='failed_send')throw Error('offline');return {ok:true,json:async()=>({turn_id:'turn-A'})}};
'''.replace('SCENARIO', repr(scenario))
    assertions = r'''
const original={name:'original.png'},next={name:'new.png'};
stagedAttachments=[original];
const sending=submit({preventDefault(){}});
assert.equal(send.disabled,true);
assert.deepEqual(stagedAttachments,[]);
assert.equal(text.value,'');
if(SCENARIO==='double_submit')await submit({preventDefault(){}});
if(SCENARIO==='new_attachment'||SCENARIO==='failed_send'){stagedAttachments=[next];text.value='next draft'}
if(SCENARIO==='switch_session'){switchSession('B');stagedAttachments=[next];text.value='private B'}
if(SCENARIO==='history_refresh')await loadHistory();
if(SCENARIO==='read_failure')rejectRead(Error('unreadable'));else resolveRead();
await sending;
assert.equal(send.disabled,false);
assert.equal(submitBusy,false);
if(SCENARIO==='read_failure')assert.equal(requests.length,0);
else {assert.equal(requests.length,1);assert.equal(requests[0].session_id,'A');assert.deepEqual(requests[0].attachments.map(x=>x.name),['original.png'])}
if(SCENARIO==='new_attachment'||SCENARIO==='failed_send')assert.equal(stagedAttachments[0],next);
if(SCENARIO==='switch_session'){
  assert.equal(session,'B');assert.equal(text.value,'private B');assert.equal(pending.size,0);
  switchSession('A');assert.deepEqual(stagedAttachments,[]);
  switchSession('B');assert.equal(stagedAttachments[0],next);assert.equal(text.value,'private B');
}
if(SCENARIO==='failed_send'||SCENARIO==='read_failure'){
  assert.equal(failedDrafts.get('A')[0].files[0],original);
  text.value='';stagedAttachments=[];
  failedDrafts.get('A')[0].notice.children[0].click();
  assert.equal(stagedAttachments[0],original);assert.equal(text.value,'describe this');assert.equal(failedDrafts.get('A').length,0);
}
if(SCENARIO==='history_refresh')assert.equal(historyLoads,2);
'''.replace('SCENARIO', repr(scenario))
    run = subprocess.run([node], input=prelude + helpers + switch + handler
                         + '(async()=>{' + assertions + '})().catch(e=>{console.error(e);process.exit(1)});',
                         text=True, capture_output=True, timeout=10)
    assert run.returncode == 0, run.stderr
