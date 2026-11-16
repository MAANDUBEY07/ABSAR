// Fictional examples used only to keep the interface useful when API data is unavailable.
export const demoOpportunities = [
  {
    id: "demo-national-merit-scholarship",
    title: "National Merit Scholarship Programme",
    organization: "Avsar Demo Foundation",
    category: "scholarship",
    description: "A sample merit award for undergraduate students with a strong academic record and a clear study plan.",
    location: "India",
    remote: true,
    stipend: 50000,
    deadline: "2026-12-18",
    verification_status: "UNKNOWN",
    requirements: { confirmed: false },
  },
  {
    id: "demo-climate-tech-internship",
    title: "Climate Technology Research Internship",
    organization: "Open Climate Lab (Demo)",
    category: "internship",
    description: "A sample eight-week remote internship supporting open research on energy access and climate resilience.",
    location: "Remote · India",
    remote: true,
    stipend: 18000,
    deadline: "2027-01-12",
    verification_status: "UNKNOWN",
    requirements: { confirmed: false },
  },
  {
    id: "demo-student-innovation-challenge",
    title: "Student Innovation Challenge",
    organization: "Campus Builders Network (Demo)",
    category: "innovation_challenge",
    description: "A fictional challenge for student teams building practical tools for their local communities.",
    location: "Bengaluru, Karnataka",
    remote: false,
    stipend: null,
    deadline: "2027-02-04",
    verification_status: "UNKNOWN",
    requirements: { confirmed: false },
  },
  {
    id: "demo-junior-data-analyst",
    title: "Junior Data Analyst Fellowship",
    organization: "Civic Data Studio (Demo)",
    category: "fellowship",
    description: "A sample early-career fellowship with guided projects in data cleaning, visualization, and public-interest research.",
    location: "New Delhi, India",
    remote: true,
    stipend: 24000,
    deadline: "2027-02-20",
    verification_status: "UNKNOWN",
    requirements: { confirmed: false },
  },
];

export const demoProfile = {
  name: "Aarav Mehta",
  date_of_birth: "2003-08-14",
  degree: "B.Tech",
  branch: "Computer Science",
  cgpa: 8.4,
  graduation_year: 2027,
  location: "Pune, Maharashtra",
  experience_months: 6,
  experience: [],
  education: [],
  skills: ["Python", "SQL", "Data visualization", "Research"],
  preferences: { remote: true, domain: "Data and climate technology", min_stipend: 15000, max_duration_months: 6 },
};
export const demoApplications = [
  { id: "demo-application-1", opportunity_id: demoOpportunities[0].id, status: "SAVED", revision: 1, created_at: "2026-10-28T10:30:00Z", opportunity: demoOpportunities[0] },
  { id: "demo-application-2", opportunity_id: demoOpportunities[1].id, status: "DRAFT", revision: 2, created_at: "2026-11-02T08:15:00Z", opportunity: demoOpportunities[1] },
  { id: "demo-application-3", opportunity_id: demoOpportunities[2].id, status: "READY_FOR_REVIEW", revision: 3, created_at: "2026-11-06T13:45:00Z", opportunity: demoOpportunities[2] },
];

export const demoDeadlines = demoOpportunities.slice(0, 3).map((opportunity, index) => ({
  id: `demo-deadline-${index + 1}`,
  opportunity_id: opportunity.id,
  title: opportunity.title,
  deadline: opportunity.deadline,
  application_status: demoApplications[index]?.status || "SAVED",
}));

export const demoNotifications = [
  { id: "demo-notification-1", title: "Profile tip", message: "Adding a few skills can make your opportunity matches more useful.", created_at: "2026-11-12T09:00:00Z" },
  { id: "demo-notification-2", title: "Deadline reminder", message: "The sample merit scholarship closes on 18 December 2026.", created_at: "2026-11-13T09:00:00Z" },
];

export const demoDashboard = {
  profile: demoProfile,
  recommendations: demoOpportunities.slice(0, 3).map((opportunity, index) => ({ opportunity_id: opportunity.id, opportunity, score: [88, 81, 74][index] })),
  applications: demoApplications,
  recent: demoApplications,
  deadlines: demoDeadlines,
  notifications: demoNotifications,
};
