const labels = { online: "Online", offline: "On-site", hybrid: "Hybrid" };

export function opportunityMode(opportunity) {
  if (Object.hasOwn(labels, opportunity?.opportunity_mode)) return opportunity.opportunity_mode;
  return opportunity?.remote === true ? "online" : null;
}

export function opportunityModeLabel(opportunity) {
  return labels[opportunityMode(opportunity)] || "Mode not specified";
}
