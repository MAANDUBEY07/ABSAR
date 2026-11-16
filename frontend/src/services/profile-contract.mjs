/**
 * Profile contract and serialization helpers.
 * Handles safe null/undefined normalization, trimming, and payload building
 * to prevent runtime TypeError on incomplete profiles.
 */

export const EMPTY_PROFILE = {
  name: "",
  date_of_birth: "",
  degree: "",
  branch: "",
  cgpa: "",
  graduation_year: "",
  location: "",
  experience_months: "",
  experience: [],
  education: [],
  skills: "",
  gender: "",
  category: "",
  domicile_state: "",
  domicile_district: "",
  annual_income: "",
  differently_abled: null,
  disability_percentage: "",
  phone: "",
  preferences: {
    remote: null,
    domain: "",
    min_stipend: "",
    max_duration_months: "",
  },
};

export function cleanString(value) {
  if (value == null) return null;
  const str = String(value).trim();
  return str.length > 0 ? str : null;
}

export function cleanSkills(skills) {
  if (Array.isArray(skills)) {
    return skills
      .map((skill) => (typeof skill === "string" ? skill.trim() : String(skill || "").trim()))
      .filter(Boolean);
  }
  if (typeof skills === "string") {
    return skills
      .split(",")
      .map((skill) => skill.trim())
      .filter(Boolean);
  }
  return [];
}

export function numberOrNull(value) {
  if (value === "" || value == null) return null;
  const num = Number(value);
  return Number.isNaN(num) ? null : num;
}

export function toForm(profile) {
  const p = profile || {};
  const pref = p.preferences || {};
  return {
    ...EMPTY_PROFILE,
    ...p,
    name: p.name || "",
    date_of_birth: p.date_of_birth || p.dob || "",
    degree: p.degree || "",
    branch: p.branch || "",
    location: p.location || "",
    gender: p.gender || "",
    category: p.category || "",
    domicile_state: p.domicile_state || "",
    domicile_district: p.domicile_district || "",
    phone: p.phone || "",
    cgpa: p.cgpa ?? "",
    graduation_year: p.graduation_year ?? "",
    experience_months: p.experience_months ?? "",
    annual_income: p.annual_income ?? "",
    differently_abled: p.differently_abled ?? null,
    disability_percentage: p.disability_percentage ?? "",
    skills: Array.isArray(p.skills)
      ? p.skills.join(", ")
      : typeof p.skills === "string"
      ? p.skills
      : "",
    experience: Array.isArray(p.experience) ? p.experience : [],
    education: p.education ?? [],
    preferences: {
      ...EMPTY_PROFILE.preferences,
      ...pref,
      remote: pref.remote ?? null,
      domain: pref.domain || "",
      min_stipend: pref.min_stipend ?? "",
      max_duration_months: pref.max_duration_months ?? "",
    },
  };
}

export function buildProfilePayload(form) {
  const f = form || {};
  const preferences = f.preferences || {};
  const remote =
    String(preferences.remote) === "true"
      ? true
      : String(preferences.remote) === "false"
      ? false
      : null;

  return {
    name: cleanString(f.name),
    date_of_birth: cleanString(f.date_of_birth),
    degree: cleanString(f.degree),
    branch: cleanString(f.branch),
    cgpa: numberOrNull(f.cgpa),
    graduation_year: numberOrNull(f.graduation_year),
    location: cleanString(f.location),
    experience_months: numberOrNull(f.experience_months),
    experience: Array.isArray(f.experience) ? f.experience : [],
    education: f.education ?? [],
    gender: cleanString(f.gender),
    category: cleanString(f.category),
    domicile_state: cleanString(f.domicile_state),
    domicile_district: cleanString(f.domicile_district),
    annual_income: numberOrNull(f.annual_income),
    differently_abled: f.differently_abled == null ? null : Boolean(f.differently_abled),
    disability_percentage: numberOrNull(f.disability_percentage),
    phone: cleanString(f.phone),
    skills: cleanSkills(f.skills),
    preferences: {
      remote,
      domain: cleanString(preferences.domain),
      min_stipend: numberOrNull(preferences.min_stipend),
      max_duration_months: numberOrNull(preferences.max_duration_months),
    },
  };
}

export async function submitProfile({
  form,
  updateProfile,
  setSaving,
  setError,
  setNotice,
  setForm,
}) {
  if (setSaving) setSaving(true);
  if (setError) setError("");
  if (setNotice) setNotice("");
  try {
    const payload = buildProfilePayload(form);
    const updated = await updateProfile(payload);
    if (setForm) setForm(toForm(updated));
    if (setNotice) setNotice("Profile saved.");
    return { success: true, data: updated, payload };
  } catch (requestError) {
    const message = requestError?.message || "Failed to save profile. Please check your inputs.";
    if (setError) setError(message);
    return { success: false, error: message };
  } finally {
    if (setSaving) setSaving(false);
  }
}
