"""Owner dashboard HTML — passkeys, named tenants, grants, audit."""

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pigeon admin</title>
<style>
  :root { color-scheme: light; --ink:#1a1410; --paper:#f6f1e8; --line:#d4cbb8; --accent:#7a1f3d; }
  body { font: 16px/1.45 Georgia, "Source Serif 4", serif; background: var(--paper); color: var(--ink); margin: 0; }
  main { max-width: 52rem; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
  h1 { font-size: 1.6rem; margin: 0 0 .25rem; }
  h2 { font-size: 1.15rem; margin: 2rem 0 .5rem; }
  .muted { color: #5c5346; font-size: .92rem; }
  button, input, select { font: inherit; }
  button { background: var(--accent); color: #fff; border: 0; padding: .4rem .8rem; border-radius: 4px; cursor: pointer; }
  button.secondary { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  input { padding: .35rem .5rem; border: 1px solid var(--line); border-radius: 4px; background: #fff; }
  table { width: 100%; border-collapse: collapse; font-size: .95rem; }
  th, td { text-align: left; padding: .4rem .35rem; border-bottom: 1px solid var(--line); vertical-align: top; }
  .secret { background: #fff; border: 1px dashed var(--accent); padding: .75rem 1rem; margin: 1rem 0; }
  .secret code { word-break: break-all; }
  .err { color: #8b1a1a; }
  #login, #app, #setup { display: none; }
</style>
</head>
<body>
<main>
  <h1>Pigeon</h1>
  <p class="muted">Owner login. Agents never see this page.</p>
  <p id="msg" class="err"></p>

  <section id="setup">
    <h2>Register a passkey</h2>
    <p>This box has no owner yet. Use the setup link from <code>pigeon-admin bootstrap</code>.</p>
    <p><label>Key name <input id="setup-name" value="1Password"></label>
    <button id="setup-go">Register passkey</button></p>
  </section>

  <section id="login">
    <p><button id="signin">Sign in with passkey</button></p>
    <p class="muted">No password. After the first key, add a second from the signed-in page.</p>
  </section>

  <section id="app">
    <p class="muted">Signed in. <button class="secondary" id="signout">Sign out</button>
      <button class="secondary" id="add-key">Add another passkey</button></p>

    <h2>Tenants</h2>
    <p class="muted">One named bearer per harness. Grant only the mailboxes that tenant may touch.
      <code>grokbot</code> is the env bearer until you rotate it.</p>
    <p>
      <input id="new-name" placeholder="cursor">
      <label><input type="checkbox" id="new-auth"> can connect mailboxes</label>
      <button id="mint">Mint</button>
    </p>
    <div id="once"></div>
    <table><thead><tr><th>Name</th><th>Mailboxes</th><th></th></tr></thead>
      <tbody id="tenants"></tbody></table>

    <h2>Connected mailboxes</h2>
    <p class="muted" id="accounts-note">Gmail OAuth files on this host. Grant them; do not re-consent per harness.</p>
    <ul id="accounts"></ul>

    <h2>Audit</h2>
    <p class="muted">Who called which tool, on which account. No bodies.</p>
    <table><thead><tr><th>When</th><th>Tenant</th><th>Tool</th><th>Account</th><th>From</th></tr></thead>
      <tbody id="audit"></tbody></table>
  </section>
</main>
<script>
const $ = (id) => document.getElementById(id);
const msg = (t) => { $('msg').textContent = t || ''; };

async function api(path, opts={}) {
  const r = await fetch(path, { credentials: 'same-origin', headers: {'content-type':'application/json'}, ...opts });
  const text = await r.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { error: text }; }
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

function b64urlToBuf(s) {
  const pad = '='.repeat((4 - s.length % 4) % 4);
  const bin = atob(s.replace(/-/g,'+').replace(/_/g,'/') + pad);
  return Uint8Array.from(bin, c => c.charCodeAt(0));
}
function bufToB64url(buf) {
  const b = String.fromCharCode(...new Uint8Array(buf));
  return btoa(b).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
}
function fixCreate(o) {
  o.challenge = b64urlToBuf(o.challenge);
  o.user.id = b64urlToBuf(o.user.id);
  (o.excludeCredentials || []).forEach(c => { c.id = b64urlToBuf(c.id); });
}
function fixGet(o) {
  o.challenge = b64urlToBuf(o.challenge);
  (o.allowCredentials || []).forEach(c => { c.id = b64urlToBuf(c.id); });
}
function credToJSON(c) {
  return {
    id: c.id, rawId: bufToB64url(c.rawId), type: c.type,
    response: {
      clientDataJSON: bufToB64url(c.response.clientDataJSON),
      attestationObject: c.response.attestationObject ? bufToB64url(c.response.attestationObject) : undefined,
      authenticatorData: c.response.authenticatorData ? bufToB64url(c.response.authenticatorData) : undefined,
      signature: c.response.signature ? bufToB64url(c.response.signature) : undefined,
      userHandle: c.response.userHandle ? bufToB64url(c.response.userHandle) : undefined,
    }
  };
}

async function refresh() {
  try {
    const me = await api('/~/api/me');
    $('app').style.display = 'block';
    $('login').style.display = 'none';
    $('setup').style.display = 'none';
    const t = await api('/~/api/tenants');
    const accts = await api('/~/api/accounts');
    const aud = await api('/~/api/audit');
    $('accounts').innerHTML = (accts.items || []).map(a =>
      `<li><code>${a.account}</code> ${a.status}</li>`).join('') || '<li class="muted">None yet</li>';
    $('tenants').innerHTML = (t.items || []).map(row => {
      const opts = (accts.items || []).map(a =>
        `<option value="${a.account}">${a.account}</option>`).join('');
      const grants = (row.grants || []).map(g =>
        `<code>${g}</code> <button class="secondary" data-revoke="${row.id}" data-acct="${g}">×</button>`
      ).join(' ');
      return `<tr>
        <td><strong>${row.name}</strong><br><span class="muted">${row.displayPrefix}…${row.canAuthStart ? ' · can OAuth' : ''}</span></td>
        <td>${grants || '<span class="muted">none</span>'}<br>
          <select data-grant-sel="${row.id}">${opts}</select>
          <button class="secondary" data-grant="${row.id}">Grant</button></td>
        <td><button class="secondary" data-forget="${row.id}">Revoke tenant</button></td>
      </tr>`;
    }).join('');
    $('audit').innerHTML = (aud.items || []).map(e =>
      `<tr><td>${e.at}</td><td>${e.tenant_name}</td><td>${e.tool}</td><td>${e.account}</td><td>${e.from_identity}</td></tr>`
    ).join('');
  } catch {
    const boot = await api('/~/api/bootstrap-state');
    $('app').style.display = 'none';
    if (boot.needsSetup && boot.setupOk) {
      $('setup').style.display = 'block';
      $('login').style.display = 'none';
    } else {
      $('setup').style.display = 'none';
      $('login').style.display = 'block';
    }
  }
}

$('signin').onclick = async () => {
  msg('');
  try {
    const begin = await api('/~/api/login/begin', { method: 'POST', body: '{}' });
    fixGet(begin.publicKey);
    const cred = await navigator.credentials.get({ publicKey: begin.publicKey });
    await api('/~/api/login/finish', { method: 'POST', body: JSON.stringify({ credential: credToJSON(cred) }) });
    await refresh();
  } catch (e) { msg(e.message); }
};

$('setup-go').onclick = async () => {
  msg('');
  try {
    const begin = await api('/~/api/register/begin', { method: 'POST', body: '{}' });
    fixCreate(begin.publicKey);
    const cred = await navigator.credentials.create({ publicKey: begin.publicKey });
    await api('/~/api/register/finish', { method: 'POST', body: JSON.stringify({
      credential: credToJSON(cred), name: $('setup-name').value
    }) });
    await refresh();
  } catch (e) { msg(e.message); }
};

$('add-key').onclick = async () => {
  msg('');
  try {
    const begin = await api('/~/api/register/begin', { method: 'POST', body: '{}' });
    fixCreate(begin.publicKey);
    const cred = await navigator.credentials.create({ publicKey: begin.publicKey });
    await api('/~/api/register/finish', { method: 'POST', body: JSON.stringify({
      credential: credToJSON(cred), name: 'Passkey'
    }) });
    msg('Passkey added.');
  } catch (e) { msg(e.message); }
};

$('signout').onclick = async () => {
  await api('/~/api/logout', { method: 'POST', body: '{}' });
  location.reload();
};

$('mint').onclick = async () => {
  msg('');
  try {
    const data = await api('/~/api/tenants', { method: 'POST', body: JSON.stringify({
      name: $('new-name').value, canAuthStart: $('new-auth').checked
    }) });
    $('once').innerHTML = `<div class="secret">Copy once. It will not be shown again.<br><code>${data.token}</code></div>`;
    $('new-name').value = '';
    await refresh();
  } catch (e) { msg(e.message); }
};

document.addEventListener('click', async (ev) => {
  const g = ev.target.dataset.grant;
  const r = ev.target.dataset.revoke;
  const f = ev.target.dataset.forget;
  try {
    if (g) {
      const sel = document.querySelector(`[data-grant-sel="${g}"]`);
      await api('/~/api/grants', { method: 'POST', body: JSON.stringify({ tenantId: g, account: sel.value }) });
      await refresh();
    }
    if (r) {
      await api('/~/api/grants', { method: 'DELETE', body: JSON.stringify({ tenantId: r, account: ev.target.dataset.acct }) });
      await refresh();
    }
    if (f && confirm('Revoke this tenant? Its bearer stops working.')) {
      await api('/~/api/tenants/revoke', { method: 'POST', body: JSON.stringify({ tenantId: f }) });
      await refresh();
    }
  } catch (e) { msg(e.message); }
});

refresh();
</script>
</body>
</html>
"""
