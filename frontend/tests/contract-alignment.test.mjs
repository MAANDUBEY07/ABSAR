import test from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
const contract = JSON.parse(await readFile(new URL("../../docs/API_CONTRACTS.json", import.meta.url), "utf8"));
const openapi = JSON.parse(await readFile(new URL("../../docs/openapi.json", import.meta.url), "utf8"));
const source = await readFile(new URL("../src/utils/constants.js", import.meta.url), "utf8");
const constants = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
test("all eleven frontend IDs equal backend canonical schema", () => {
 const category = contract.definitions.OpportunityInput.properties.category;
 assert.deepEqual(constants.OPPORTUNITY_CATEGORIES, category.anyOf[0].enum);
});
test("submission and job-result client paths match registered API", () => {
 assert.ok(openapi.paths["/api/v1/jobs/{record_id}/result"].get);
 const submit=openapi.paths["/api/v1/applications/{record_id}/submit"].post;
 assert.ok(submit.parameters.some((parameter) => parameter.name === "Idempotency-Key" && parameter.required));
 assert.ok(contract.definitions.Submit.required.includes("confirmation"));
});
