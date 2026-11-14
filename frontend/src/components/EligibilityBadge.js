/**
 * EligibilityBadge Component
 * Renders color-coded badge for the four AVSAR eligibility statuses:
 * - ELIGIBLE (Green)
 * - POTENTIALLY_ELIGIBLE (Amber / Yellow)
 * - NOT_ELIGIBLE (Red)
 * - CANNOT_DETERMINE (Gray)
 */

export default function EligibilityBadge({ status }) {
  return (
    <span>{status || "CANNOT_DETERMINE"}</span>
  );
}
