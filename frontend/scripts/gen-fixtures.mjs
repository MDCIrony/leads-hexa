#!/usr/bin/env node
// Captures test fixtures from the real backend instead of writing them by hand: a captured
// response is proof of yesterday's contract, a handwritten one is only a guess. Rerun after the
// backend's contract changes and diff the fixtures to see what moved.
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const BASE = `${process.env.VITE_API_BASE_URL ?? 'http://localhost:8001'}/api/v1`;
const OUT_DIR = path.join(import.meta.dirname, '../src/test/fixtures');
const STAMP = Date.now();
const PASSWORD = 'Secret123';

async function call(method, url, { token, body, form } = {}) {
  const headers = {};
  if (token) headers.Cookie = token;
  let payload;
  if (form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${url}`, { method, headers, body: payload });
  const data = await res.json().catch(() => null);
  const setCookie = res.headers.get('set-cookie');
  return { status: res.status, data, cookie: setCookie?.split(';', 1)[0] };
}

async function save(name, value) {
  await writeFile(path.join(OUT_DIR, name), `${JSON.stringify(value, null, 2)}\n`);
  console.log(`  wrote ${name}`);
}

async function login(email, password) {
  const { cookie } = await call('POST', '/auth/login', { form: { username: email, password } });
  if (!cookie) throw new Error(`login did not set a session cookie for ${email}`);
  return cookie;
}

// Bounded polling, same reasoning as scripts/verify-e2e.sh: processing runs
// after the ingest response is sent, so a fixed sleep is either wasteful or flaky.
async function awaitJob(token, jobId) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const { data } = await call('GET', `/intake/jobs/${jobId}`, { token });
    if (data.status === 'COMPLETED' || data.status === 'FAILED') return data;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`intake job ${jobId} never reached a terminal status`);
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  // Same bootstrap as verify-e2e.sh: 201 the first time the platform runs,
  // 401 on every run after — both mean the admin is usable.
  await call('POST', '/agents', { body: { name: 'Root', email: 'root@plat.test', password: PASSWORD } });
  const adminToken = await login('root@plat.test', PASSWORD);
  await save('me-admin.json', (await call('GET', '/auth/me', { token: adminToken })).data);
  const tenant = await call('POST', '/tenants', {
    token: adminToken,
    body: {
      name: `Fixtures Org ${STAMP}`,
      manager: { name: 'Fixture Manager', email: `mgr-${STAMP}@fixtures.test`, password: PASSWORD },
    },
  });
  const managerEmail = tenant.data.manager.email;
  const loginResponse = await call('POST', '/auth/login', { form: { username: managerEmail, password: PASSWORD } });
  await save('login.json', loginResponse.data);
  const managerToken = loginResponse.cookie;
  if (!managerToken) throw new Error('manager login did not set a session cookie');
  await save('me-manager.json', (await call('GET', '/auth/me', { token: managerToken })).data);

  const agent = await call('POST', '/agents', {
    token: managerToken,
    body: { name: 'Fixture Agent', email: `agent-${STAMP}@fixtures.test`, password: PASSWORD, role: 'AGENT' },
  });
  const agentToken = await login(`agent-${STAMP}@fixtures.test`, PASSWORD);
  await save('me-agent.json', (await call('GET', '/auth/me', { token: agentToken })).data);

  await call('POST', '/rules/scoring', {
    token: managerToken,
    body: {
      name: `Presupuesto alto ${STAMP}`,
      conditions: [{ field: 'budget', operator: 'GREATER_THAN', value: 5000 }],
      score_delta: 25,
      priority: 5,
    },
  });
  await call('POST', '/rules/scoring', {
    token: managerToken,
    body: {
      name: `Sector tecnologico ${STAMP}`,
      conditions: [{ field: 'industry', operator: 'EQUALS', value: 'Technology' }],
      score_delta: 15,
      priority: 0,
    },
  });
  await save('scoring-rules-page.json', (await call('GET', '/rules/scoring', { token: managerToken })).data);

  const group = await call('POST', '/groups', {
    token: managerToken,
    body: { name: `Ventas Fixtures ${STAMP}`, default_strategy: 'LOWEST_LOAD' },
  });
  await call('PATCH', `/advisors/${agent.data.id}`, { token: managerToken, body: { group_id: group.data.id } });
  await save('groups-page.json', (await call('GET', '/groups', { token: managerToken })).data);
  // A fresh organization already carries its two default sources — nothing to create first.
  await save('sources-page.json', (await call('GET', '/sources', { token: managerToken })).data);

  await call('POST', '/rules/assignment', {
    token: managerToken,
    body: {
      name: `Todo al asesor ${STAMP}`,
      min_score: 0,
      max_score: null,
      target_agent_ids: [agent.data.id],
      agent_match_mode: 'ANY',
      strategy: 'DIRECT_AGENT',
      priority: 10,
      conditions: [],
    },
  });
  await save('assignment-rules-page.json', (await call('GET', '/rules/assignment', { token: managerToken })).data);

  const ingested = await call('POST', '/intake/leads/ingest', {
    token: managerToken,
    body: {
      first_name: 'Marta',
      last_name: 'Iglesias',
      email: `marta-${STAMP}@northwind.test`,
      company: 'Northwind',
      budget: 42000,
      industry: 'Technology',
      phone: '+34600111222',
    },
  });
  await save('intake-accepted.json', ingested.data);
  await save('intake-job-completed.json', await awaitJob(managerToken, ingested.data.job_id));

  const records = await call('GET', `/intake/records?job_id=${ingested.data.job_id}`, { token: managerToken });
  const leadId = records.data.items[0].lead_id;
  await save('lead-detail.json', (await call('GET', `/leads/${leadId}`, { token: managerToken })).data);
  await save('leads-page.json', (await call('GET', '/leads', { token: managerToken })).data);
  // Capped: the dev database accumulates organizations across runs, and a
  // fixture of a hundred rows buries the contract change its diff should show.
  await save('tenants-page.json', (await call('GET', '/tenants?limit=5', { token: adminToken })).data);
  await save('agents-page.json', (await call('GET', '/agents', { token: managerToken })).data);
  await save('advisors-page.json', (await call('GET', '/advisors', { token: managerToken })).data);
  await save('lead-stats.json', (await call('GET', '/leads/stats', { token: managerToken })).data);
  await save('intake-stats.json', (await call('GET', '/intake/stats', { token: managerToken })).data);
  // The assignment rule above targets this agent, so LEAD_ASSIGNED lands in their own inbox.
  await save('notifications-page.json', (await call('GET', '/notifications', { token: agentToken })).data);

  // Errors, provoked on purpose — each fixture keeps its status alongside the envelope.
  await save('error-400.json', await call('POST', '/rules/scoring', {
    token: managerToken,
    body: { name: 'no puntuable', conditions: [{ field: 'tenant_id', operator: 'EQUALS', value: 'x' }], score_delta: 10 },
  }));
  await save('error-401.json', await call('GET', '/auth/me', { token: 'not-a-real-token' }));
  await save('error-404.json', await call('GET', '/leads/00000000-0000-0000-0000-000000000000', { token: managerToken }));
  await save('error-422.json', await call('POST', '/rules/scoring', { token: managerToken, body: {} }));

  console.log('done.');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
