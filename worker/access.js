// Cloudflare Access identity.
//
// Access sits in front of this Worker and only forwards requests it has already
// authenticated. It attaches a signed JWT in Cf-Access-Jwt-Assertion. We still
// verify the signature: without that, anyone who reaches the Worker origin
// directly could forge the header.

let keyCache = { at: 0, keys: null };

async function certs(team) {
  if (keyCache.keys && Date.now() - keyCache.at < 3600e3) return keyCache.keys;
  const r = await fetch(`https://${team}.cloudflareaccess.com/cdn-cgi/access/certs`);
  if (!r.ok) throw new Error('access certs fetch failed: ' + r.status);
  const { keys } = await r.json();
  keyCache = { at: Date.now(), keys };
  return keys;
}

const b64url = (s) =>
  Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));

export async function identify(request, env) {
  const token =
    request.headers.get('Cf-Access-Jwt-Assertion') ||
    (request.headers.get('Cookie') || '').match(/CF_Authorization=([^;]+)/)?.[1];
  if (!token) return null;

  const [h, p, s] = token.split('.');
  if (!h || !p || !s) return null;

  const header = JSON.parse(new TextDecoder().decode(b64url(h)));
  const jwk = (await certs(env.ACCESS_TEAM)).find((k) => k.kid === header.kid);
  if (!jwk) return null;

  const key = await crypto.subtle.importKey(
    'jwk', jwk, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']
  );
  const ok = await crypto.subtle.verify(
    'RSASSA-PKCS1-v1_5', key, b64url(s), new TextEncoder().encode(`${h}.${p}`)
  );
  if (!ok) return null;

  const claims = JSON.parse(new TextDecoder().decode(b64url(p)));
  if (claims.exp * 1000 < Date.now()) return null;
  // aud is the Access application tag — stops a token minted for a *different*
  // app in the same Zero Trust org from working here.
  if (!([].concat(claims.aud)).includes(env.ACCESS_AUD)) return null;

  return { email: String(claims.email || '').toLowerCase(), sub: claims.sub };
}

// Resolves the Access identity to a row in `users`, creating an annotator row
// on first sign-in. Access already decided *whether* they may enter; this table
// only decides what they may do once inside.
export async function currentUser(request, env) {
  const id = await identify(request, env);
  if (!id) return null;

  let u = await env.DB.prepare('SELECT * FROM users WHERE email = ?').bind(id.email).first();
  if (!u) {
    const first = !(await env.DB.prepare('SELECT 1 FROM users LIMIT 1').first());
    u = {
      id: 'u' + crypto.randomUUID().slice(0, 8),
      name: id.email.split('@')[0],
      email: id.email,
      role: first ? 'admin' : 'annotator', // first person through the door owns it
    };
    await env.DB.prepare('INSERT INTO users (id,name,email,role) VALUES (?,?,?,?)')
      .bind(u.id, u.name, u.email, u.role).run();
  }
  return u;
}
