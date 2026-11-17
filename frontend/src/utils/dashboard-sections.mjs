export function sectionItems(section, applications, deadlines, now = new Date()) {
  if (section === "saved") return applications.filter(item => item.status === "SAVED");
  if (section === "preparing") return applications.filter(item => ["DRAFT", "READY_FOR_REVIEW", "APPROVED"].includes(item.status));
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return deadlines.filter(item => {
    const date = new Date(`${item.deadline}T00:00:00`);
    return date >= start && date <= end;
  });
}

export async function loadAllPages(loadPage) {
  const rows = [];
  for (let offset = 0; ; offset += 100) {
    const page = await loadPage({ limit: 100, offset });
    if (!Array.isArray(page)) throw new Error("Could not load your records. Please retry.");
    rows.push(...page);
    if (page.length < 100) return rows;
  }
}
