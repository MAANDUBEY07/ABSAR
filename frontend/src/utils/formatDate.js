/**
 * Date Formatting Utility
 * Standardizes date presentation across opportunity deadlines and notices.
 */

export function formatDate(dateString) {
  if (!dateString) return "N/A";
  const date = new Date(dateString);
  return date.toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
