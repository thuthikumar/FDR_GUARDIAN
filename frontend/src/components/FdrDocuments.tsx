import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useAuth } from '../auth/AuthContext'
import { Button } from './ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { responseError } from '../lib/registry'

type DocumentRow = { id:string;fdr_record_id:string;document_type:string;original_filename:string;file_size:number;uploaded_by_name:string;uploaded_at:string;processing_status:string;processing_error_code:string|null;page_count:number|null;ocr_engine:string|null;extraction_method:string|null }
type Field = {field_name:string;extracted_value:string|null;confidence_score:number|null;extraction_method:string|null;source_page:number|null;stored_value:string|null;comparison:'matches'|'differs'|'not_comparable'|'not_extracted'}
type Extraction = {document_id:string;notice:string;fields:Field[]}
const MAX_FILE_BYTES = 10 * 1024 * 1024
const allowedTypes = new Set(['application/pdf','image/png','image/jpeg'])
const labels: Record<string,string> = {fdr_certificate:'FDR certificate',bank_confirmation_letter:'Bank confirmation letter',institution_request_letter:'Institution request letter',other:'Other'}
const statusStyles: Record<string,string> = {queued:'bg-blue-50 text-blue-800',processing:'bg-amber-50 text-amber-800',processed:'bg-emerald-50 text-emerald-800',failed:'bg-rose-50 text-rose-800',ocr_unavailable:'bg-slate-100 text-slate-700',uploaded:'bg-slate-100 text-slate-700'}

export default function FdrDocuments({recordId}:{recordId:string}) {
  const {apiFetch,user}=useAuth()
  const canUpload=Boolean(user?.permissions.includes('document.upload'))
  const canReprocess=Boolean(user?.permissions.includes('document.reprocess'))
  const [documents,setDocuments]=useState<DocumentRow[]>([]),[loading,setLoading]=useState(true),[uploading,setUploading]=useState(false)
  const [documentType,setDocumentType]=useState('fdr_certificate'),[file,setFile]=useState<File|null>(null),[error,setError]=useState(''),[success,setSuccess]=useState('')
  const [expanded,setExpanded]=useState<string|null>(null),[extractions,setExtractions]=useState<Record<string,Extraction>>({}),[pending,setPending]=useState<string|null>(null)

  const load=useCallback(async()=>{
    const response=await apiFetch(`/api/v1/fdrs/${recordId}/documents`)
    if(!response.ok)throw new Error(await responseError(response))
    const body=await response.json() as {items:DocumentRow[]}
    setDocuments(body.items)
  },[apiFetch,recordId])
  useEffect(()=>{let active=true;void load().catch(reason=>{if(active)setError(reason instanceof Error?reason.message:'Documents could not be loaded.')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[load])
  const hasPending=documents.some(item=>item.processing_status==='queued'||item.processing_status==='processing')
  useEffect(()=>{if(!hasPending)return;const timer=window.setInterval(()=>{void load().catch(()=>undefined)},2000);return()=>window.clearInterval(timer)},[hasPending,load])

  function validateFile(selected:File|null) {
    setFile(selected);setError('');setSuccess('')
    if(!selected)return
    const extension=selected.name.split('.').pop()?.toLowerCase()
    const extensionOkay=extension==='pdf'||extension==='png'||extension==='jpg'||extension==='jpeg'
    if(!extensionOkay||!allowedTypes.has(selected.type)){setError('Choose a PDF, PNG, or JPEG file with a matching file type.');return}
    if(selected.size===0){setError('Empty files cannot be uploaded.');return}
    if(selected.size>MAX_FILE_BYTES)setError('The file must be 10 MB or smaller.')
  }

  async function upload(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();if(!file||error)return
    setUploading(true);setError('');setSuccess('')
    try{const body=new FormData();body.append('file',file);body.append('document_type',documentType)
      const response=await apiFetch(`/api/v1/fdrs/${recordId}/documents`,{method:'POST',body})
      if(!response.ok)throw new Error(await responseError(response))
      const created=await response.json() as DocumentRow;setDocuments(rows=>[created,...rows]);setFile(null)
      const input=document.getElementById(`document-file-${recordId}`) as HTMLInputElement|null;if(input)input.value=''
      setSuccess('Document uploaded and queued for processing.');await load()
    }catch(reason){setError(reason instanceof Error?reason.message:'Document upload failed.')}finally{setUploading(false)}
  }

  async function toggleExtraction(id:string){
    if(expanded===id){setExpanded(null);return}setExpanded(id)
    if(extractions[id])return
    setPending(id);setError('')
    try{const response=await apiFetch(`/api/v1/documents/${id}/extraction`);if(!response.ok)throw new Error(await responseError(response));const body=await response.json() as Extraction;setExtractions(value=>({...value,[id]:body}))}
    catch(reason){setError(reason instanceof Error?reason.message:'Extracted fields could not be loaded.')}finally{setPending(null)}
  }

  async function download(item:DocumentRow){
    setPending(item.id);setError('')
    try{const response=await apiFetch(`/api/v1/documents/${item.id}/download`);if(!response.ok)throw new Error(await responseError(response));const blob=await response.blob();const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=item.original_filename;anchor.click();URL.revokeObjectURL(url)}
    catch(reason){setError(reason instanceof Error?reason.message:'Download failed.')}finally{setPending(null)}
  }

  async function reprocess(item:DocumentRow){
    setPending(item.id);setError('')
    try{const response=await apiFetch(`/api/v1/documents/${item.id}/reprocess`,{method:'POST'});if(!response.ok)throw new Error(await responseError(response));await load()}
    catch(reason){setError(reason instanceof Error?reason.message:'Document could not be queued again.')}finally{setPending(null)}
  }

  return <Card><CardHeader><CardTitle className="text-base">Documents</CardTitle></CardHeader><CardContent className="space-y-4">
    <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">Machine-extracted and unreviewed. OCR output does not confirm that a document is genuine.</p>
    {error&&<p role="alert" className="text-sm text-rose-700">{error}</p>}{success&&<p role="status" className="text-sm text-emerald-800">{success}</p>}
    {canUpload&&<form onSubmit={upload} className="grid gap-3 rounded-lg border p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
      <div className="space-y-1"><label htmlFor={`document-type-${recordId}`} className="text-sm font-medium">Document type</label><select id={`document-type-${recordId}`} value={documentType} onChange={event=>setDocumentType(event.target.value)} className="h-9 w-full rounded-lg border bg-background px-3 text-sm">{Object.entries(labels).map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></div>
      <div className="space-y-1"><label htmlFor={`document-file-${recordId}`} className="text-sm font-medium">Choose PDF, PNG, or JPEG (max 10 MB)</label><input id={`document-file-${recordId}`} type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={event=>validateFile(event.target.files?.[0]||null)} className="block w-full text-sm" /></div>
      <Button type="submit" disabled={uploading||!file||Boolean(error)}>{uploading?'Uploading...':'Upload document'}</Button>
    </form>}
    {loading?<p role="status" className="text-sm text-slate-500">Loading documents...</p>:documents.length===0?<p className="text-sm text-slate-500">No documents have been uploaded for this FDR.</p>:<ul className="space-y-3">{documents.map(item=><li key={item.id} className="rounded-lg border p-3">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">{item.original_filename}</p><p className="mt-1 text-xs text-slate-600">{labels[item.document_type]||item.document_type} | {(item.file_size/1024).toLocaleString('en-IN',{maximumFractionDigits:1})} KB | Uploaded by {item.uploaded_by_name} | {new Date(item.uploaded_at).toLocaleString('en-IN')}</p><span className={`mt-2 inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusStyles[item.processing_status]||statusStyles.uploaded}`}>{item.processing_status==='ocr_unavailable'?'OCR unavailable':item.processing_status}</span>{item.processing_error_code&&<p className="mt-1 text-xs text-slate-600">{item.processing_error_code==='ocr_unavailable'?'OCR is unavailable on this server.':`Processing issue: ${item.processing_error_code.replaceAll('_',' ')}.`}</p>}</div>
      <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" onClick={()=>void download(item)} disabled={pending===item.id}>Download</Button><Button type="button" variant="outline" onClick={()=>void toggleExtraction(item.id)} disabled={pending===item.id}>{pending===item.id?'Loading...':expanded===item.id?'Hide extracted fields':'View extracted fields'}</Button>{canReprocess&&<Button type="button" variant="outline" onClick={()=>void reprocess(item)} disabled={pending===item.id}>Reprocess</Button>}</div></div>
      {expanded===item.id&&extractions[item.id]&&<div className="mt-4 overflow-x-auto"><p className="mb-2 text-sm font-semibold">Unreviewed extracted values</p><table className="w-full min-w-[650px] text-left text-sm"><thead><tr><th className="p-2">Field</th><th className="p-2">Extracted</th><th className="p-2">Confidence</th><th className="p-2">Method</th><th className="p-2">Stored FDR value</th><th className="p-2">Comparison</th></tr></thead><tbody>{extractions[item.id].fields.map(field=><tr key={field.field_name} className="border-t"><th scope="row" className="p-2 font-medium">{field.field_name.replaceAll('_',' ')}</th><td className="max-w-56 p-2">{field.extracted_value||'Not extracted'}</td><td className="p-2">{field.confidence_score===null?'Not available':`${Math.round(field.confidence_score*100)}%`}</td><td className="p-2">{field.extraction_method||'-'}</td><td className="max-w-56 p-2">{field.stored_value||'-'}</td><td className="p-2 capitalize">{field.comparison.replaceAll('_',' ')}</td></tr>)}</tbody></table><p className="mt-2 text-xs text-slate-600">Tesseract confidence is its own recognition score, not a probability of correctness.</p></div>}
    </li>)}</ul>}
  </CardContent></Card>
}
