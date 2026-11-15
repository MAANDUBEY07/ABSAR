export function trustState(report, status) {
  if (String(report?.verification_status || status).toUpperCase() === "EXPIRED") return {label: "Expired", tone: "warning"};
  if (!report) return {label: "Unverified", tone: "neutral"};
  if (["HIGH", "REVIEW"].includes(report.risk_level) || report.source_assessment?.status === "SUSPICIOUS") return {label: "Risk signals - review", tone: "warning"};
  if (report.source_assessment?.official_domain_match && report.source_assessment?.status === "VERIFIED") return {label: "Official domain match", tone: "neutral"};
  return {label: "Unverified", tone: "neutral"};
}
