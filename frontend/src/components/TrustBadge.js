import { trustState } from "@/services/trust-state.mjs";
export default function TrustBadge({ status, report }) {
  const state = trustState(report, status);
  return <span className={`badge badge-${state.tone}`} title={report?.disclaimer || "Domain and risk signals are not proof of legitimacy or fraud"}>{state.label}</span>;
}
