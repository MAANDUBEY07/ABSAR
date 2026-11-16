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

test("Restored resume analysis preserves full credentials contract", () => {
  const completeAnalysis = {
    document_id: "doc-xyz-789",
    skills: ["python", "fastapi", "react"],
    parsed_skills: ["python", "fastapi", "react"],
    experience_years: 3.5,
    education: [
      {
        degree: "B.Tech",
        field: "Computer Science",
        institution: "National Institute of Technology",
        graduation_year: 2024,
      },
    ],
    readiness_score: 88.0,
    recommendations: ["Add cloud certifications to strengthen deployment capabilities."],
    warnings: ["Rule-based estimates; absence of evidence is not proof of no experience"],
    disclaimer: "Deterministic resume claims and completeness score; not verified qualifications",
  };

  const state = applyRestorationState({
    currentAnalysis: null,
    currentDocId: "",
    busy: false,
    savedAnalysis: completeAnalysis,
  });

  assert.equal(state.documentId, "doc-xyz-789");
  assert.equal(state.analysis.experience_years, 3.5);
  assert.equal(state.analysis.readiness_score, 88.0);
  assert.equal(state.analysis.education.length, 1);
  assert.equal(state.analysis.education[0].degree, "B.Tech");
  assert.equal(state.analysis.education[0].institution, "National Institute of Technology");
  assert.deepEqual(state.analysis.recommendations, [
    "Add cloud certifications to strengthen deployment capabilities.",
  ]);
});
