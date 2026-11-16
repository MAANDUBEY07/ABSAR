import test from "node:test";
import assert from "node:assert/strict";
import { opportunityMode, opportunityModeLabel } from "../src/utils/opportunity-mode.mjs";

test("explicit modes are displayed consistently with the API filters", () => {
  for (const [value, label] of [["online", "Online"], ["offline", "On-site"], ["hybrid", "Hybrid"]]) {
    const row = { opportunity_mode: value, remote: false };
    assert.equal(opportunityMode(row), value);
    assert.equal(opportunityModeLabel(row), label);
  }
});

test("legacy non-remote does not incorrectly imply on-site", () => {
  assert.equal(opportunityMode({ remote: false }), null);
  assert.equal(opportunityModeLabel({ remote: false }), "Mode not specified");
});

test("remote-only records still match online", () => {
  assert.equal(opportunityMode({ remote: true }), "online");
});

test("invalid and absent modes stay unknown", () => {
  assert.equal(opportunityMode({ opportunity_mode: "invalid" }), null);
  assert.equal(opportunityModeLabel(null), "Mode not specified");
});
