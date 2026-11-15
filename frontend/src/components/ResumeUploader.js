"use client";

import { useRef, useState } from "react";
import { FileText, UploadCloud } from "lucide-react";

export default function ResumeUploader({ onUpload, busy = false }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  function submit(event) {
    event.preventDefault();
    if (file) onUpload?.(file);
  }
  return (
    <form className="panel resume-panel" onSubmit={submit}>
      <div className="panel-heading"><span className="panel-icon"><FileText size={20} /></span><div><h2>Upload your resume</h2><p>PDF or DOCX, up to 5 MiB. Your file is handled by the AVSAR backend.</p></div></div>
      <label className="drop-zone" htmlFor="resume-file"><UploadCloud size={28} className="upload-icon" aria-hidden="true" /><strong>{file ? file.name : "Choose a resume file"}</strong><p>Select a PDF or Word document to begin analysis.</p></label>
      <input ref={inputRef} id="resume-file" className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] || null)} disabled={busy} />
      <button className="button button-primary upload-submit" type="submit" disabled={!file || busy}>{busy ? "Uploading and analysing…" : "Upload resume"}</button>
    </form>
  );
}
