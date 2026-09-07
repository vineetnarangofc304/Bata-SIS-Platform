import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, FileSpreadsheet, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "@/lib/api";
import { PageHeader, Field, selectCls, inputCls } from "@/components/common/DataTable";
import { ConfidenceBadge } from "@/components/common/Badges";

export default function Upload() {
  const [partners, setPartners] = useState([]);
  const [partner, setPartner] = useState("");
  const [notes, setNotes] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [sheet, setSheet] = useState(0);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef();
  const nav = useNavigate();
  useEffect(() => { api.get("/partners").then((r) => setPartners(r.data.filter((p) => p.active))); }, []);

  const pick = async (f) => {
    if (!f) return;
    if (!/\.(xlsx|xls|csv|xlsm)$/i.test(f.name)) return toast.error("Only .xlsx, .xls and .csv files are accepted");
    setFile(f); setPreview(null); setBusy(true);
    const fd = new FormData(); fd.append("file", f);
    try { const { data } = await api.post("/uploads/preview", fd); setPreview(data); setSheet(0); } catch (e) { toast.error(errMsg(e)); setFile(null); } finally { setBusy(false); }
  };
  const submit = async () => {
    setBusy(true);
    const fd = new FormData(); fd.append("file", file); if (partner) fd.append("partner_code", partner); if (notes) fd.append("notes", notes);
    try { const { data } = await api.post("/uploads", fd); toast.success(data.status === "Rejected" ? "File rejected as duplicate" : "File received — analysis started"); nav(`/batches/${data.id}`); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const s = preview?.sheets?.[sheet];
  return (
    <div data-testid="upload-page">
      <PageHeader title="Upload Data" sub="Drop a partner sales file. The recognition engine detects the partner, header row and column mappings — nothing is written to reporting until validation passes." />
      <div className="grid lg:grid-cols-[1fr_320px] gap-6">
        <div>
          <div data-testid="upload-file-dropzone" onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }} onClick={() => inputRef.current.click()}
            className={`card border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${drag ? "border-[#E60000] bg-red-50/40" : "border-slate-300 hover:border-slate-400"}`}>
            <input ref={inputRef} type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={(e) => pick(e.target.files[0])} data-testid="upload-file-input" />
            {busy && !preview ? <Loader2 className="h-8 w-8 mx-auto text-[#E60000] animate-spin" /> : <UploadCloud className="h-8 w-8 mx-auto text-[#E60000]" />}
            <div className="mt-3 font-display font-semibold text-slate-800">{file ? file.name : "Drag & drop a sales file here"}</div>
            <div className="text-xs text-slate-500 mt-1">.xlsx · .xls · .csv · up to 50 MB · multi-sheet supported</div>
          </div>
          {preview && s && (
            <div className="card mt-4 fade-up" data-testid="upload-preview">
              <div className="flex items-center gap-2 px-4 pt-3 border-b overflow-x-auto">
                {preview.sheets.map((sh, i) => <button key={sh.name} data-testid={`upload-sheet-tab-${i}`} onClick={() => setSheet(i)} className={`px-3 py-2 text-xs font-medium border-b-2 -mb-px whitespace-nowrap ${i === sheet ? "border-[#E60000] text-[#E60000]" : "border-transparent text-slate-500"}`}><FileSpreadsheet className="inline h-3 w-3 mr-1" />{sh.name} <span className="text-slate-400">({sh.data_rows} rows)</span></button>)}
              </div>
              <div className="flex flex-wrap gap-4 px-4 py-3 text-xs text-slate-600 border-b bg-slate-50">
                <span>Header row detected: <b className="font-mono">{s.header_row + 1}</b></span><span className="flex items-center gap-1">Header confidence <ConfidenceBadge value={s.header_confidence} /></span>
                <span>Data rows: <b>{s.data_rows}</b></span><span>Skipped blank: <b>{s.skipped.blank}</b></span><span>Skipped totals: <b>{s.skipped.totals}</b></span>
              </div>
              <div className="overflow-auto max-h-80">
                <table className="text-xs w-full" data-testid="upload-preview-table"><tbody>
                  {s.preview.map((row, ri) => <tr key={ri} className={ri === s.header_row ? "bg-red-50 font-semibold text-slate-900" : ri < s.header_row ? "text-slate-400 italic" : "text-slate-700"}>
                    <td className="px-2 py-1 border-b border-r bg-slate-50 text-slate-400 font-mono w-8">{ri + 1}</td>{row.map((c, ci) => <td key={ci} className="px-2 py-1 border-b border-slate-100 whitespace-nowrap max-w-[180px] truncate">{c ?? ""}</td>)}</tr>)}
                </tbody></table>
              </div>
            </div>
          )}
        </div>
        <div className="card p-5 space-y-4 h-fit">
          <Field label="Partner (optional — leave blank to auto-detect)"><select data-testid="upload-partner-select" value={partner} onChange={(e) => setPartner(e.target.value)} className={selectCls}><option value="">Auto-detect</option>{partners.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select></Field>
          <Field label="Notes"><input data-testid="upload-notes-input" value={notes} onChange={(e) => setNotes(e.target.value)} className={inputCls} placeholder="e.g. resubmission for 05-Jun" /></Field>
          <div className="text-xs text-slate-500 space-y-1 border-t pt-3">
            <div className="label-caps">What happens next</div>
            <ol className="list-decimal pl-4 space-y-1"><li>File hash checked — exact duplicates are blocked.</li><li>Partner, sheet, header row & columns recognised with confidence scores.</li><li>High confidence → auto-validate. Medium/low → Review Queue.</li><li>Valid rows load to reporting; bad rows become exceptions.</li></ol>
          </div>
          <div className="flex gap-2">
            <button data-testid="upload-submit-btn" disabled={!file || busy} onClick={submit} className="flex-1 h-10 rounded-md btn-red font-semibold text-sm disabled:opacity-50 flex items-center justify-center gap-2">{busy && <Loader2 className="h-4 w-4 animate-spin" />}Upload & analyse</button>
            {file && <button data-testid="upload-clear-btn" onClick={() => { setFile(null); setPreview(null); }} className="h-10 w-10 rounded-md border flex items-center justify-center hover:bg-slate-50"><X className="h-4 w-4" /></button>}
          </div>
        </div>
      </div>
    </div>
  );
}
