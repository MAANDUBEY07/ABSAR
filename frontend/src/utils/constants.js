export const ELIGIBILITY_STATUSES = {
  ELIGIBLE: "ELIGIBLE",
  POTENTIALLY_ELIGIBLE: "POTENTIALLY_ELIGIBLE",
  NOT_ELIGIBLE: "NOT_ELIGIBLE",
  CANNOT_DETERMINE: "CANNOT_DETERMINE",
};

export const OPPORTUNITY_CATEGORIES = [
  "scholarship",
  "internship",
  "job",
  "government_scheme",
  "fellowship",
  "apprenticeship",
  "hackathon",
  "coding_competition",
  "innovation_challenge",
  "startup_challenge",
  "grant",
];

export const CATEGORY_LABELS = {
  scholarship: "Scholarship",
  internship: "Internship",
  job: "Job",
  government_scheme: "Government scheme",
  fellowship: "Fellowship",
  apprenticeship: "Apprenticeship",
  hackathon: "Hackathon",
  coding_competition: "Coding competition",
  innovation_challenge: "Innovation challenge",
  startup_challenge: "Startup challenge",
  grant: "Grant",
  scheme: "Scheme",
  competition: "Competition",
  other: "Other",
};

export const APPLICATION_STATUSES = [
  "SAVED",
  "PREPARING",
  "APPLIED",
  "SHORTLISTED",
  "SELECTED",
  "REJECTED",
];

// Current backend lifecycle values from backend/app/schemas/application.py.
export const BACKEND_APPLICATION_STATUSES = [
  "SAVED",
  "DRAFT",
  "READY_FOR_REVIEW",
  "APPROVED",
  "SUBMITTED",
  "ASSESSMENT",
  "INTERVIEW",
  "OFFER",
  "REJECTED",
  "WITHDRAWN",
];

export const BACKEND_APPLICATION_TRANSITIONS = {
  SAVED: ["DRAFT", "WITHDRAWN"],
  DRAFT: ["READY_FOR_REVIEW", "WITHDRAWN"],
  READY_FOR_REVIEW: ["DRAFT", "WITHDRAWN"],
  APPROVED: ["DRAFT", "WITHDRAWN"],
  SUBMITTED: ["ASSESSMENT", "INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"],
  ASSESSMENT: ["INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"],
  INTERVIEW: ["OFFER", "REJECTED", "WITHDRAWN"],
  OFFER: ["WITHDRAWN"],
};

export const APPLICATION_STATUS_LABELS = {
  SAVED: "Saved",
  DRAFT: "Preparing",
  READY_FOR_REVIEW: "Preparing · ready for review",
  APPROVED: "Preparing · approved",
  SUBMITTED: "Applied · submitted",
  ASSESSMENT: "Applied · assessment",
  INTERVIEW: "Shortlisted · interview",
  OFFER: "Selected · offer",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
};
