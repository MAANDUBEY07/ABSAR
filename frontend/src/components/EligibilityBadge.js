import { ELIGIBILITY_STATUSES } from "@/utils/constants";

const labels = {
  ELIGIBLE: ["Eligible", "badge-success"],
  POTENTIALLY_ELIGIBLE: ["Potentially eligible", "badge-warning"],
  NOT_ELIGIBLE: ["Not eligible", "badge-danger"],
  CANNOT_DETERMINE: ["Cannot determine", "badge-neutral"],
};

export default function EligibilityBadge({ status }) {
  const value = Object.values(ELIGIBILITY_STATUSES).includes(status) ? status : "CANNOT_DETERMINE";
  const [label, tone] = labels[value];
  return <span className={`badge ${tone}`} role="status">{label}</span>;
}
