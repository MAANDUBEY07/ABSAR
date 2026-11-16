import test from "node:test";
import assert from "node:assert/strict";
import {
  EMPTY_PROFILE,
  cleanString,
  cleanSkills,
  numberOrNull,
  toForm,
  buildProfilePayload,
  submitProfile,
} from "../src/services/profile-contract.mjs";

test("Newly registered user with all optional fields null", () => {
  // Simulates GET /profile/me returning a fresh profile where unpopulated optional fields are null
  const apiResponse = {
    id: "8892c083-caab-42c6-9a8c-8d10df5908fe",
    email: "rtgdr26@gmail.com",
    name: null,
    date_of_birth: null,
    degree: null,
    branch: null,
    cgpa: null,
    graduation_year: null,
    location: null,
    experience_months: null,
    experience: [],
    education: [],
    skills: null,
    gender: null,
    category: null,
    domicile_state: null,
    domicile_district: null,
    annual_income: null,
    differently_abled: null,
    disability_percentage: null,
    phone: null,
    preferences: {
      remote: null,
      domain: null,
      min_stipend: null,
      max_duration_months: null,
    },
  };

  const form = toForm(apiResponse);

  // Form controls receive empty strings or defaults, not null
  assert.equal(form.name, "");
  assert.equal(form.degree, "");
  assert.equal(form.branch, "");
  assert.equal(form.location, "");
  assert.equal(form.skills, "");
  assert.equal(form.preferences.domain, "");
  assert.equal(form.preferences.remote, null);

  // Building payload does NOT throw TypeError: Cannot read properties of null (reading 'trim')
  const payload = buildProfilePayload(form);

  assert.equal(payload.name, null);
  assert.equal(payload.degree, null);
  assert.equal(payload.branch, null);
  assert.equal(payload.location, null);
  assert.deepEqual(payload.skills, []);
  assert.equal(payload.preferences.domain, null);
  assert.equal(payload.preferences.remote, null);
});

test("Partially completed profile", () => {
  const partial = {
    name: "Ritik Raj",
    degree: "B.Tech",
    branch: "Computer Science",
    cgpa: 8.75,
    skills: ["Python", "FastAPI"],
    preferences: {
      remote: true,
      domain: "Software Engineering",
    },
  };

  const form = toForm(partial);
  assert.equal(form.name, "Ritik Raj");
  assert.equal(form.degree, "B.Tech");
  assert.equal(form.skills, "Python, FastAPI");
  assert.equal(form.preferences.remote, true);

  const payload = buildProfilePayload(form);
  assert.equal(payload.name, "Ritik Raj");
  assert.equal(payload.degree, "B.Tech");
  assert.equal(payload.cgpa, 8.75);
  assert.deepEqual(payload.skills, ["Python", "FastAPI"]);
  assert.equal(payload.preferences.remote, true);
  assert.equal(payload.preferences.domain, "Software Engineering");
  // Omitted optional fields serialize cleanly as null
  assert.equal(payload.annual_income, null);
  assert.equal(payload.differently_abled, null);
});

test("Skills supplied as a string", () => {
  const form = {
    ...EMPTY_PROFILE,
    skills: "Python, Next.js, Docker,  SQL  ",
  };

  const payload = buildProfilePayload(form);
  assert.deepEqual(payload.skills, ["Python", "Next.js", "Docker", "SQL"]);
});

test("Skills supplied as an array", () => {
  const form = {
    ...EMPTY_PROFILE,
    skills: ["Python", " React ", "", "TypeScript "],
  };

  const payload = buildProfilePayload(form);
  assert.deepEqual(payload.skills, ["Python", "React", "TypeScript"]);
});

test("Empty optional fields", () => {
  // Test whitespace-only, empty strings, and null inputs
  const form = {
    ...EMPTY_PROFILE,
    name: "   ",
    degree: "",
    branch: null,
    location: undefined,
    cgpa: "",
    skills: "   ",
    preferences: {
      remote: "",
      domain: "  ",
      min_stipend: "",
      max_duration_months: "",
    },
  };

  const payload = buildProfilePayload(form);
  assert.equal(payload.name, null);
  assert.equal(payload.degree, null);
  assert.equal(payload.branch, null);
  assert.equal(payload.location, null);
  assert.equal(payload.cgpa, null);
  assert.deepEqual(payload.skills, []);
  assert.equal(payload.preferences.domain, null);
  assert.equal(payload.preferences.remote, null);
  assert.equal(payload.preferences.min_stipend, null);
  assert.equal(payload.preferences.max_duration_months, null);
});

test("Successful profile update", async () => {
  const initialForm = {
    ...EMPTY_PROFILE,
    name: "Aarav Sharma",
    degree: "B.Tech",
    skills: "Go, Kubernetes",
  };

  let capturedPayload = null;
  const mockUpdateProfile = async (payload) => {
    capturedPayload = payload;
    return {
      id: "user-123",
      email: "aarav@example.com",
      ...payload,
      skills: ["go", "kubernetes"],
    };
  };

  let savingState = null;
  let noticeMessage = "";
  let updatedForm = null;

  const result = await submitProfile({
    form: initialForm,
    updateProfile: mockUpdateProfile,
    setSaving: (saving) => {
      savingState = saving;
    },
    setError: () => {},
    setNotice: (msg) => {
      noticeMessage = msg;
    },
    setForm: (newForm) => {
      updatedForm = newForm;
    },
  });

  assert.equal(result.success, true);
  assert.equal(savingState, false, "Saving state must be reset to false upon completion");
  assert.equal(noticeMessage, "Profile saved.");
  assert.equal(capturedPayload.name, "Aarav Sharma");
  assert.deepEqual(capturedPayload.skills, ["Go", "Kubernetes"]);
  assert.equal(updatedForm.name, "Aarav Sharma");
  assert.equal(updatedForm.skills, "go, kubernetes");
});

test("Failed API request", async () => {
  const initialForm = {
    ...EMPTY_PROFILE,
    name: "Error Test",
  };

  const mockUpdateProfile = async () => {
    throw new Error("Internal Server Error (500)");
  };

  let savingState = null;
  let errorMessage = "";
  let noticeMessage = "";

  const result = await submitProfile({
    form: initialForm,
    updateProfile: mockUpdateProfile,
    setSaving: (saving) => {
      savingState = saving;
    },
    setError: (msg) => {
      errorMessage = msg;
    },
    setNotice: (msg) => {
      noticeMessage = msg;
    },
    setForm: () => {},
  });

  assert.equal(result.success, false);
  assert.equal(errorMessage, "Internal Server Error (500)");
  assert.equal(noticeMessage, "");
  assert.equal(savingState, false, "Saving state must be reset to false even when API fails");
});

test("Saving state resets after an error", async () => {
  const stateTransitions = [];
  const setSaving = (val) => stateTransitions.push(val);
  let errorMessage = "";

  const explodingUpdate = async () => {
    throw new TypeError("Cannot read properties of undefined");
  };

  await submitProfile({
    form: null, // triggers robust error handling
    updateProfile: explodingUpdate,
    setSaving,
    setError: (msg) => {
      errorMessage = msg;
    },
    setNotice: () => {},
    setForm: () => {},
  });

  assert.deepEqual(stateTransitions, [true, false], "setSaving must transition from true to false");
  assert.ok(errorMessage.length > 0, "Error message must be populated");
});
