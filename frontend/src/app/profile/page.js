"use client";

import { useEffect, useState } from "react";
import { UserRound, Save } from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import { api } from "@/services/api";
import {
  EMPTY_PROFILE,
  toForm,
  buildProfilePayload,
} from "@/services/profile-contract.mjs";

export default function ProfilePage() {
  const [form, setForm] = useState(EMPTY_PROFILE);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api
      .profile()
      .then((profile) => setForm(toForm(profile)))
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updatePreference(key, value) {
    setForm((current) => ({
      ...current,
      preferences: { ...current.preferences, [key]: value },
    }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = buildProfilePayload(form);
      const updated = await api.updateProfile(payload);
      setForm(toForm(updated));
      setNotice("Profile saved.");
    } catch (requestError) {
      setError(requestError?.message || "Failed to save profile. Please check your inputs.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ProtectedWorkspace>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR INFORMATION</span>
          <h1>Student profile</h1>
          <p>Keep your profile up to date to improve opportunity matching and eligibility checks.</p>
        </div>
      </div>
      {loading ? (
        <Loading label="Loading profile" />
      ) : (
        <>
          {error && <div className="inline-message error" role="alert">{error}</div>}
          {notice && <div className="inline-message" role="status">{notice}</div>}
          <form className="panel" onSubmit={submit}>
            <div className="panel-heading">
              <span className="panel-icon"><UserRound size={20} /></span>
              <div>
                <h2>Education and experience</h2>
                <p>Only fields supported by the profile API are submitted.</p>
              </div>
            </div>
            <div className="form-grid">
              <label>
                <span className="field-label">Name</span>
                <input
                  className="form-control"
                  value={form.name || ""}
                  onChange={(event) => update("name", event.target.value)}
                  maxLength={200}
                  autoComplete="name"
                />
              </label>
              <label>
                <span className="field-label">Date of birth</span>
                <input
                  className="form-control"
                  type="date"
                  value={form.date_of_birth || ""}
                  onChange={(event) => update("date_of_birth", event.target.value)}
                />
              </label>
              <label>
                <span className="field-label">Degree</span>
                <input
                  className="form-control"
                  value={form.degree || ""}
                  onChange={(event) => update("degree", event.target.value)}
                />
              </label>
              <label>
                <span className="field-label">Branch / field</span>
                <input
                  className="form-control"
                  value={form.branch || ""}
                  onChange={(event) => update("branch", event.target.value)}
                />
              </label>
              <label>
                <span className="field-label">CGPA (0–10)</span>
                <input
                  className="form-control"
                  type="number"
                  min="0"
                  max="10"
                  step="0.01"
                  value={form.cgpa}
                  onChange={(event) => update("cgpa", event.target.value)}
                />
              </label>
              <label>
                <span className="field-label">Graduation year</span>
                <input
                  className="form-control"
                  type="number"
                  min="1950"
                  max="2150"
                  value={form.graduation_year}
                  onChange={(event) => update("graduation_year", event.target.value)}
                />
              </label>
              <label>
                <span className="field-label">Location / state</span>
                <input
                  className="form-control"
                  value={form.location || ""}
                  onChange={(event) => update("location", event.target.value)}
                />
              </label>
              <label>
                <span className="field-label">Experience (months)</span>
                <input
                  className="form-control"
                  type="number"
                  min="0"
                  max="1200"
                  value={form.experience_months}
                  onChange={(event) => update("experience_months", event.target.value)}
                />
              </label>
              <label className="full-span">
                <span className="field-label">Skills (comma separated)</span>
                <textarea
                  className="form-control"
                  rows="3"
                  value={form.skills}
                  onChange={(event) => update("skills", event.target.value)}
                  placeholder="e.g. Python, research, communication"
                />
              </label>
            </div>
            <details className="detail-section">
              <summary>Optional eligibility information</summary>
              <p>Provide these facts only when an opportunity you choose requires them. Missing information stays unknown.</p>
              <div className="form-grid">
                <label>
                  <span className="field-label">Gender (as required by the source)</span>
                  <input
                    className="form-control"
                    value={form.gender || ""}
                    onChange={(event) => update("gender", event.target.value)}
                  />
                </label>
                <label>
                  <span className="field-label">Social category</span>
                  <input
                    className="form-control"
                    value={form.category || ""}
                    onChange={(event) => update("category", event.target.value)}
                  />
                </label>
                <label>
                  <span className="field-label">Domicile state</span>
                  <input
                    className="form-control"
                    value={form.domicile_state || ""}
                    onChange={(event) => update("domicile_state", event.target.value)}
                  />
                </label>
                <label>
                  <span className="field-label">Annual income (same units as the source rule)</span>
                  <input
                    type="number"
                    min="0"
                    className="form-control"
                    value={form.annual_income ?? ""}
                    onChange={(event) => update("annual_income", event.target.value)}
                  />
                </label>
                <label>
                  <span className="field-label">Disability status, if required</span>
                  <select
                    className="form-control"
                    value={form.differently_abled == null ? "" : String(form.differently_abled)}
                    onChange={(event) => update("differently_abled", event.target.value === "" ? null : event.target.value === "true")}
                  >
                    <option value="">Not provided</option>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </select>
                </label>
              </div>
            </details>
            <div className="detail-section">
              <h2>Opportunity preferences</h2>
              <div className="form-grid">
                <label>
                  <span className="field-label">Preferred mode</span>
                  <select
                    className="form-control"
                    value={form.preferences.remote == null ? "" : String(form.preferences.remote)}
                    onChange={(event) => updatePreference("remote", event.target.value)}
                  >
                    <option value="">Any mode</option>
                    <option value="true">Online</option>
                    <option value="false">On-site</option>
                  </select>
                </label>
                <label>
                  <span className="field-label">Domain</span>
                  <input
                    className="form-control"
                    value={form.preferences.domain || ""}
                    onChange={(event) => updatePreference("domain", event.target.value)}
                    maxLength={200}
                  />
                </label>
                <label>
                  <span className="field-label">Minimum stipend</span>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    step="1"
                    value={form.preferences.min_stipend}
                    onChange={(event) => updatePreference("min_stipend", event.target.value)}
                  />
                </label>
                <label>
                  <span className="field-label">Maximum duration (months)</span>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    max="120"
                    value={form.preferences.max_duration_months}
                    onChange={(event) => updatePreference("max_duration_months", event.target.value)}
                  />
                </label>
              </div>
            </div>
            <div className="form-actions">
              <span className="form-feedback">Your profile is private to your account.</span>
              <button className="button button-primary" type="submit" disabled={saving}>
                {saving ? "Saving…" : <><Save size={15} /> Save profile</>}
              </button>
            </div>
          </form>
        </>
      )}
    </ProtectedWorkspace>
  );
}
