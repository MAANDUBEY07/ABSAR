/**
 * OpportunityCard Component
 * Displays summary card for an opportunity with title, provider, deadline, and eligibility badge.
 */

export default function OpportunityCard({ opportunity }) {
  return (
    <div>
      <h3>{opportunity?.title || "Opportunity Title"}</h3>
    </div>
  );
}
