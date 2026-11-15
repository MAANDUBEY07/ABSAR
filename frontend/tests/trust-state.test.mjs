import test from "node:test";
import assert from "node:assert/strict";
import { trustState } from "../src/services/trust-state.mjs";
test("trust signals preserve uncertainty and expiry", () => {
 assert.equal(trustState(null, "UNKNOWN").label, "Unverified");
 assert.equal(trustState({risk_level:"HIGH"}, "UNKNOWN").tone, "warning");
 assert.equal(trustState({risk_level:"HIGH"}, "EXPIRED").label, "Expired");
 assert.equal(trustState({source_assessment:{status:"VERIFIED",official_domain_match:true}}, "UNKNOWN").label, "Official domain match");
});
