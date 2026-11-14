export default function TrustBadge({ status }) {
  const normalized = String(status || "UNKNOWN").toUpperCase();
  const expired = normalized === "EXPIRED";
  return <span className={`badge ${expired ? "badge-warning" : "badge-neutral"}`} title="This source status is not a fraud determination">{expired ? "Verification expired" : "Source not verified"}</span>;
}
