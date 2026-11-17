import test from "node:test";
import assert from "node:assert/strict";
import { sectionItems, loadAllPages } from "../src/utils/dashboard-sections.mjs";

test("dashboard sections separate saved and preparation states", () => {
  const apps = ["SAVED", "DRAFT", "READY_FOR_REVIEW", "APPROVED", "SUBMITTED"].map(status => ({ status }));
  assert.deepEqual(sectionItems("saved", apps, []).map(row => row.status), ["SAVED"]);
  assert.deepEqual(sectionItems("preparing", apps, []).map(row => row.status), ["DRAFT", "READY_FOR_REVIEW", "APPROVED"]);
});

test("deadline section includes today and seven days ahead at calendar boundaries", () => {
  const rows = ["2026-11-16", "2026-11-17", "2026-11-24", "2026-11-25", null].map(deadline => ({ deadline }));
  assert.deepEqual(sectionItems("deadlines", [], rows, new Date(2026, 10, 17, 23)).map(row => row.deadline), ["2026-11-17", "2026-11-24"]);
});

test("all records are loaded across pages", async () => {
  const offsets = [];
  const rows = await loadAllPages(async ({ limit, offset }) => {
    offsets.push(offset);
    return Array.from({ length: offset === 0 ? limit : 3 }, (_, i) => ({ id: offset + i }));
  });
  assert.equal(rows.length, 103);
  assert.deepEqual(offsets, [0, 100]);
});
