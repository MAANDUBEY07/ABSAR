import test from "node:test";
import assert from "node:assert/strict";
import {submissionRequest} from "../src/services/application-contract.mjs";
test("submission carries explicit confirmation and stable idempotency on retries", () => {
 const first = submissionRequest("owned-id", 5, "same-request-key");
 const retry = submissionRequest("owned-id", 5, "same-request-key");
 assert.deepEqual(first, retry);
 assert.equal(first.path, "/applications/owned-id/submit");
 assert.deepEqual(first.options.body, {revision:5, confirmation:true});
 assert.equal(first.options.headers["Idempotency-Key"], "same-request-key");
 assert.throws(() => submissionRequest("owned-id", 5, ""));
});
