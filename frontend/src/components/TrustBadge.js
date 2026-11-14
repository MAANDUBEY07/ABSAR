/**
 * TrustBadge Component
 * Displays verified shield or credibility indicator for authentic opportunities.
 */

export default function TrustBadge({ trustScore, isVerified }) {
  return (
    <span>{isVerified ? "Verified Official" : "Unverified"}</span>
  );
}
