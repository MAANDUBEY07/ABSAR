"use client";

import { useRef, useState } from "react";
import { FileText, UploadCloud } from "lucide-react";

export default function ResumeUploader({ onUpload, busy = false }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  function chooseFile(candidate) {
    if (candidate) setFile(candidate);
  }
  function submit(event) {
    event.preventDefault();
    if (file) onUpload?.(file);
  }
  return (
    <form className="panel resume-panel" onSubmit={submit} aria-busy={busy}>
      <div className="panel-heading"><span className="panel-icon"><FileText size={20} /></span><div><h2>Upload your resume</h2><p>PDF or DOCX, up to 5 MiB. Your file is handled by the AVSAR backend.</p></div></div>
      <label
        className={`drop-zone ${dragging ? "drop-zone-active" : ""}`}
        htmlFor="resume-file"
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false); }}
        onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0]); }}
      >
        <UploadCloud size={28} className="upload-icon" aria-hidden="true" />
        <strong>{file ? file.name : "Choose or drop a resume"}</strong>
        <p id="resume-help">PDF or DOCX, up to 5 MiB. You can also browse files.</p>
        {file && <small>{(file.size / (1024 * 1024)).toFixed(2)} MiB selected</small>}
      </label>
      <input ref={inputRef} id="resume-file" className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => chooseFile(event.target.files?.[0])} disabled={busy} aria-describedby="resume-help" />
      <div className="resume-upload-actions">
        {file && <button className="button button-secondary" type="button" onClick={() => { setFile(null); if (inputRef.current) inputRef.current.value = ""; }} disabled={busy}>Remove file</button>}
        <button className="button button-primary upload-submit" type="submit" disabled={!file || busy}>{busy ? "Uploading and analysing…" : "Upload resume"}</button>
      </div>
    </form>
  );
}
