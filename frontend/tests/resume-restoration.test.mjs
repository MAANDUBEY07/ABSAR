import test from "node:test";
import assert from "node:assert/strict";

/**
 * Pure state reducer simulating ResumePage hydration behavior.
 */
function applyRestorationState({ currentAnalysis, currentDocId, busy, savedAnalysis }) {
  if (!savedAnalysis) {
    return { analysis: currentAnalysis, documentId: currentDocId };
  }
  if (busy || currentAnalysis) {
    // Preserve active/newly uploaded analysis; do not overwrite with late-arriving restoration
    return { analysis: currentAnalysis, documentId: currentDocId };
  }
  return {
    analysis: savedAnalysis,
    documentId: savedAnalysis.document_id || savedAnalysis.id || "",
  };
}

test("Resume restoration on initial load with completed analysis", () => {
  const saved = {
    document_id: "doc-abc-123",
    skills: ["Python", "FastAPI"],
    readiness_score: 85,
    experience_years: 2.5,
  };

  const state = applyRestorationState({
    currentAnalysis: null,
    currentDocId: "",
    busy: false,
    savedAnalysis: saved,
  });

  assert.deepEqual(state.analysis, saved);
  assert.equal(state.documentId, "doc-abc-123");
});

test("Resume restoration with empty state (no prior upload)", () => {
  const state = applyRestorationState({
    currentAnalysis: null,
    currentDocId: "",
    busy: false,
    savedAnalysis: null,
  });

  assert.equal(state.analysis, null);
  assert.equal(state.documentId, "");
});

test("Late-arriving restoration does not overwrite newly uploaded analysis", () => {
  const newlyUploaded = {
    document_id: "doc-new-456",
    skills: ["Go", "Kubernetes"],
    readiness_score: 95,
  };
  const staleSaved = {
    document_id: "doc-old-123",
    skills: ["Python"],
    readiness_score: 50,
  };

  // Case A: Upload already completed
  const stateAfterUpload = applyRestorationState({
    currentAnalysis: newlyUploaded,
    currentDocId: "doc-new-456",
    busy: false,
    savedAnalysis: staleSaved,
  });

  assert.equal(stateAfterUpload.documentId, "doc-new-456");
  assert.deepEqual(stateAfterUpload.analysis.skills, ["Go", "Kubernetes"]);

  // Case B: Upload currently busy in flight
  const stateDuringUpload = applyRestorationState({
    currentAnalysis: null,
    currentDocId: "doc-new-456",
    busy: true,
    savedAnalysis: staleSaved,
  });

  assert.equal(stateDuringUpload.analysis, null);
  assert.equal(stateDuringUpload.documentId, "doc-new-456");
});
