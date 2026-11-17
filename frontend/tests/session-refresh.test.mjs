import test from "node:test";
import assert from "node:assert/strict";
import { refreshAccessToken, fetchWithSessionRecovery } from "../src/services/session-refresh.mjs";

test("concurrent requests share one refresh", async () => {
  let calls = 0;
  const client = { auth: { refreshSession: async () => {
    calls++;
    return { data: { session: { access_token: "fresh" } } };
  } } };
  assert.deepEqual(await Promise.all([refreshAccessToken(client), refreshAccessToken(client)]), ["fresh", "fresh"]);
  assert.equal(calls, 1);
});

test("401 retries with fresh authorization only once", async () => {
  let calls = 0;
  let token;
  const response = await fetchWithSessionRecovery(async () => {
    calls++;
    if (calls === 2) assert.equal(token, "fresh");
    return { status: 401 };
  }, { enabled: true, refresh: async () => "fresh", setToken: value => { token = value; } });
  assert.equal(response.status, 401);
  assert.equal(calls, 2);
});

test("successful, forbidden and local requests do not refresh", async () => {
  for (const [status, enabled] of [[200, true], [403, true], [401, false]]) {
    await fetchWithSessionRecovery(async () => ({ status }), {
      enabled, refresh: () => assert.fail("Unexpected refresh"), setToken: () => {}
    });
  }
});

test("failed refresh releases shared promise for later recovery", async () => {
  await assert.rejects(refreshAccessToken({ auth: { refreshSession: async () => { throw new Error("offline"); } } }));
  assert.equal(await refreshAccessToken({ auth: { refreshSession: async () => ({ data: { session: { access_token: "recovered" } } }) } }), "recovered");
});
