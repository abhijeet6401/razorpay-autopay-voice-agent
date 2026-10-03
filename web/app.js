const $ = id => document.getElementById(id);
let customers = [], selected, mode = 'rehearsal', session = null, vapi = null, active = false, transcript = [];
let sdkClass, queue = Promise.resolve(), callStartedAt = null, providerCallId = null;
const hints = {retry:'Eligible active mandate · offer a mock retry',checkout:'Offer fictional checkout · no mandate renewal',callback:'Customer prefers to speak later',opt_out:'Customer wants recovery contact to stop',payment_claim:'Customer reports an existing payment',dispute:'Customer disputes the amount',wrong_person:'Tester is not the intended customer'};
const stateText = {unverified:'Confirm the fictional identity before discussing payment details.',ready:'Identity confirmed. Ask for consent before a recovery action.',retry_queued:'A mock retry is queued. No payment is confirmed yet.',checkout_created:'Fictional checkout is ready. No payment is confirmed yet.',recovered:'A separate mock settlement confirmed simulated recovery. No real money moved.',opted_out:'Contact suppressed for this fictional customer until the server is reset.',wrong_person:'Wrong person. No payment information should be disclosed.',claimed_paid:'Needs reconciliation. A payment claim is not confirmed recovery.',disputed:'Needs human review. Recovery has stopped.',callback_requested:'Callback request captured. No call was scheduled.'};
async function api(path, body) {
  const response = await fetch('/api/' + path, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Demo backend request failed');
  return data;
}
function showError(message) { $('error').textContent = message; $('error').hidden = false; }
function line(role, text) {
  transcript.push({at:new Date().toISOString(),role,text});
  $('transcript').querySelector('.empty')?.remove();
  const bubble = document.createElement('div'); bubble.className = 'bubble ' + role;
  const label = document.createElement('strong'); label.textContent = {assistant:'MIRA',user:'CUSTOMER',backend:'LOCAL BACKEND'}[role] || role;
  const content = document.createElement('span'); content.textContent = text;
  bubble.append(label, content); $('transcript').append(bubble); $('transcript').scrollTop = $('transcript').scrollHeight;
}
function selectCustomer(customer) {
  if (active) return;
  selected = customer; session = null; transcript = []; providerCallId = null; callStartedAt = null;
  $('customer-name').textContent = customer.name; $('demo-code').textContent = customer.demo_code;
  $('scenario-hint').textContent = hints[customer.scenario];
  $('transcript').replaceChildren(); $('error').hidden = true; $('export').disabled = true;
  $('ledger-state').textContent = 'No session'; $('state-description').textContent = 'Recovery is confirmed only after a simulated payment settlement.';
  $('payment-detail').replaceChildren(); $('settlement').hidden = true; $('rehearsal-controls').hidden = true;
  for (const button of $('customer-list').children) button.classList.toggle('active', button.dataset.id === customer.id);
}
function setMode(next) {
  if (active) return;
  mode = next; $('provider-config').hidden = mode !== 'vapi';
  $('rehearsal-mode').classList.toggle('selected', mode === 'rehearsal'); $('vapi-mode').classList.toggle('selected',mode === 'vapi');
  $('mode-badge').textContent = mode === 'vapi' ? 'Vapi · not connected' : 'Offline rehearsal';
  $('start').textContent = mode === 'vapi' ? 'Start voice conversation' : 'Start rehearsal';
}
async function refresh() {
  if (!session) return;
  const state = await api('state', {token:session.token});
  $('ledger-state').textContent = state.state.replaceAll('_',' '); $('state-description').textContent = stateText[state.state];
  $('payment-detail').replaceChildren();
  if (state.payment) {
    const text = document.createElement('p'); text.textContent = `${new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(state.payment.amount_paise/100)} · ${state.payment.failure_reason.replaceAll('_',' ')} · mandate ${state.payment.mandate_status}`;
    $('payment-detail').append(text);
  }
  $('settlement').hidden = !['retry_queued','checkout_created'].includes(state.state);
  return state;
}
async function dispatchTool(name, args, id, token = session.token) {
  const result = await api('tool', {token,name,arguments:args,tool_call_id:id});
  if (session?.token !== token) return result;
  line('backend',JSON.stringify({tool:name,result},null,2)); await refresh();
  return result;
}
function sendContext(data) {
  // This is documented context injection, NOT a synchronous Vapi tool result.
  vapi?.send({type:'add-message',message:{role:'system',content:'LOCAL_BACKEND_RESULT: ' + JSON.stringify(data)},triggerResponseEnabled:true});
}
function onProviderMessage(message, token) {
  if (message.type === 'transcript' && message.transcriptType === 'final') line(message.role === 'user' ? 'user' : 'assistant', message.transcript);
  if (message.type === 'tool-calls') {
    for (const call of message.toolCallList || []) {
      queue = queue.then(async () => {
        if (session?.token !== token) return;
        let args = call.function?.arguments;
        if (typeof args === 'string') args = JSON.parse(args);
        const result = await dispatchTool(call.function?.name,args,call.id,token);
        if (session?.token === token) sendContext({tool_call_id:call.id,tool:call.function?.name,...result});
      }).catch(error => {
        if (session?.token !== token) return;
        line('backend','Action rejected: ' + error.message); showError(error.message);
        sendContext({ok:false,message:'Action rejected by backend. Do not claim success.'});
      });
    }
  }
}
function setActive(value) {
  active = value; $('start').disabled = value; $('stop').disabled = !value;
  $('rehearsal-mode').disabled = value; $('vapi-mode').disabled = value;
  for (const button of $('customer-list').children) button.disabled = value;
}
async function start() {
  $('error').hidden = true;
  try {
    if (mode === 'vapi') {
      if (!$('voice-consent').checked) throw new Error('Please agree to browser microphone sharing before starting.');
      const key = $('public-key').value.trim();
      if (!key || key.startsWith('sk-')) throw new Error('Enter a Vapi public browser key, never an OpenAI or private API key.');
      if (!sdkClass) sdkClass = (await import('/vapi.js')).default;
      vapi = new sdkClass(key); $('public-key').value = '';
    }
    session = await api('session',{customer_id:selected.id,mode});
    transcript = []; $('transcript').replaceChildren(); queue = Promise.resolve(); providerCallId = null; callStartedAt = null;
    setActive(true); $('export').disabled = false; await refresh();
    if (mode === 'rehearsal') {
      $('call-status').textContent = 'Offline rehearsal active'; $('rehearsal-controls').hidden = false;
      line('assistant',"Hi, I'm Mira, an AI assistant for Cedar's fictional recovery demo. Is now a good time? Please confirm your DEMO code before we discuss payment details.");
      return;
    }
    const config = await api('assistant');
    const callToken = session.token;
    vapi.on('message',message => { if (session?.token === callToken) onProviderMessage(message,callToken); });
    vapi.on('speech-start',() => document.body.classList.add('speaking'));
    vapi.on('speech-end',() => document.body.classList.remove('speaking'));
    vapi.on('call-start',() => {
      callStartedAt = new Date().toISOString(); $('provider-status').textContent = 'Vapi connected';
      $('call-status').textContent = 'Mira is listening'; $('mode-badge').textContent = 'Live Vapi browser voice';
    });
    vapi.on('call-end',() => { setActive(false); document.body.classList.remove('speaking'); $('call-status').textContent = 'Conversation ended'; $('provider-status').textContent = 'Call ended'; });
    vapi.on('error',() => { showError('Vapi could not complete the call. Check browser microphone permission, account credits, public-key origin restrictions and transient-assistant access.'); vapi.stop(); setActive(false); });
    $('call-status').textContent = 'Connecting to Vapi…';
    const call = await vapi.start(config);
    if (!call?.id) throw new Error('Vapi did not return a call ID; live call is unconfirmed.');
    providerCallId = call.id;
    await api('live-event',{token:session.token,call_id:call.id});
  } catch (error) { showError(error.message); vapi?.stop(); setActive(false); $('call-status').textContent = 'Ready when you are'; }
}
$('start').onclick = start;
$('stop').onclick = () => { vapi?.stop(); setActive(false); $('rehearsal-controls').hidden = true; $('call-status').textContent = 'Conversation ended'; };
$('rehearsal-mode').onclick = () => setMode('rehearsal'); $('vapi-mode').onclick = () => setMode('vapi');
$('verify').onclick = async () => {
  try { line('user','My demo code is ' + selected.demo_code); const result = await dispatchTool('verify_demo_identity',{demo_code:selected.demo_code},crypto.randomUUID());
    line('assistant',result.ok ? `Thank you. The fictional autopay of ₹${result.payment.amount_paise/100} failed because of ${result.payment.failure_reason.replaceAll('_',' ')}. Would you like help with the next step?` : result.message);
  } catch (error) { showError(error.message); }
};
for (const button of document.querySelectorAll('[data-action]')) button.onclick = async () => {
  try { line('user',button.textContent); const result = await dispatchTool('record_recovery_action',{action:button.dataset.action,consent:true},crypto.randomUUID()); line('assistant',result.message); }
  catch (error) { line('assistant','That action was not accepted. Please confirm identity and choose an eligible option.'); showError(error.message); }
};
$('settle').onclick = async () => {
  try { const state = await refresh(); const result = await api('settle',{token:session.token,reference:state.checkout_ref || 'mock-retry'});
    line('backend','mock_payment_settled: fictional recovery confirmed; no money moved.'); await refresh();
    if (mode === 'vapi' && active) sendContext({event:'mock_payment_settled',state:result.state,fictional:true});
  } catch (error) { showError(error.message); }
};
$('export').onclick = async () => {
  try { const state = await refresh(); const evidenceMode = state.mode; const evidence = {demo:'Cedar autopay recovery',exported_at:new Date().toISOString(),fictional:true,
    mode:evidenceMode,live_provider_verified:false,provider_call_id:providerCallId,call_started_at:callStartedAt,
    verification_note:evidenceMode === 'vapi' ? 'Match call ID with Vapi dashboard. Browser event and transcript are not server-attested.' : 'Offline scripted rehearsal; no provider audio.',state,transcript};
    const anchor = document.createElement('a'); anchor.href = URL.createObjectURL(new Blob([JSON.stringify(evidence,null,2)],{type:'application/json'}));
    anchor.download = evidenceMode === 'vapi' ? 'live-evidence.json' : 'rehearsal-evidence.json'; anchor.click(); setTimeout(() => URL.revokeObjectURL(anchor.href),1000);
  } catch(error) { showError(error.message); }
};
try {
  customers = (await api('customers')).customers;
  for (const customer of customers) {
    const button = document.createElement('button'); button.className = 'customer-button'; button.dataset.id = customer.id;
    const name = document.createElement('strong'); name.textContent = customer.name;
    const detail = document.createElement('span'); detail.textContent = customer.id + ' · ' + customer.failure_reason.replaceAll('_',' ');
    button.append(name,detail); button.onclick = () => selectCustomer(customer); $('customer-list').append(button);
  }
  selectCustomer(customers[0]);
} catch (error) { showError('Could not load fictional records. Start the local demo server.'); }
