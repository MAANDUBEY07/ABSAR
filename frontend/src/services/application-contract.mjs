export function submissionRequest(id, revision, key) {
  if (!key || key.length < 8) throw new Error("A stable idempotency key is required");
  return {path: `/applications/${encodeURIComponent(id)}/submit`, options: {method:"POST", body:{revision,confirmation:true},headers:{"Idempotency-Key":key}}};
}
