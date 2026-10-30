import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import FdrDocuments from './FdrDocuments'

const uploader={id:'u',email:'institution@synthetic.invalid',full_name:'Synthetic Institution Admin',role:'institution_admin',institution_id:'inst',permissions:['document.read','document.upload']}
const verifier={...uploader,role:'verification_officer',permissions:['document.read','document.reprocess']}
const queued={id:'doc-1',fdr_record_id:'fdr-1',document_type:'fdr_certificate',original_filename:'synthetic.pdf',file_size:1024,uploaded_by_name:'Synthetic Institution Admin',uploaded_at:'2026-10-27T10:00:00Z',processing_status:'queued',processing_error_code:null,page_count:1,ocr_engine:null,extraction_method:null}
const extraction={document_id:'doc-1',notice:'Machine-extracted and unreviewed. OCR output does not confirm that a document is genuine.',fields:[{field_name:'bank_name',extracted_value:null,confidence_score:null,extraction_method:'ocr',source_page:null,stored_value:'Synthetic Bank',comparison:'not_extracted'}]}
function response(body:unknown,status=200){return{ok:status>=200&&status<300,status,json:async()=>body,blob:async()=>new Blob(['synthetic-file'])} as Response}
function bootstrap(url:string,user=uploader){if(url.endsWith('/auth/refresh'))return response({access_token:'test-token'});if(url.endsWith('/auth/me'))return response(user);return null}
function renderDocs(){return render(<MemoryRouter><AuthProvider><FdrDocuments recordId="fdr-1"/></AuthProvider></MemoryRouter>)}
afterEach(()=>{vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals()})

describe('FDR documents',()=>{
  it('validates uploads and uploads accepted files with authenticated requests',async()=>{
    const fetchMock=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{void init;const url=String(input),initial=bootstrap(url);if(initial)return initial;if(url.endsWith('/fdrs/fdr-1/documents'))return response({items:[queued]});if(url.endsWith('/documents'))return response(queued,202);return response({},404)})
    vi.stubGlobal('fetch',fetchMock)
    renderDocs()
    const fileInput=await screen.findByLabelText(/Choose PDF, PNG, or JPEG/)
    const invalid=new File(['not a pdf'],'bad.exe',{type:'application/octet-stream'})
    fireEvent.change(fileInput,{target:{files:[invalid]}})
    expect(await screen.findByText(/Choose a PDF, PNG, or JPEG/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([input])=>String(input).endsWith('/fdrs/fdr-1/documents'))).toBe(true)
    const valid=new File(['%PDF-synthetic'],'synthetic.pdf',{type:'application/pdf'})
    fireEvent.change(fileInput,{target:{files:[valid]}})
    fireEvent.click(screen.getByRole('button',{name:'Upload document'}))
    await waitFor(()=>expect(fetchMock.mock.calls.some(([input,init])=>String(input).endsWith('/fdrs/fdr-1/documents')&&init?.method==='POST'&&init.body instanceof FormData&&new Headers(init.headers).get('Authorization')==='Bearer test-token')).toBe(true))
    expect(await screen.findByRole('status')).toHaveTextContent('Document uploaded and queued for processing.')
  })

  it('polls pending processing, renders null confidence, and uses authenticated blob download',async()=>{
    vi.useFakeTimers()
    let polls=0
    const fetchMock=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{void init;const url=String(input),initial=bootstrap(url);if(initial)return initial;if(url.endsWith('/fdrs/fdr-1/documents')){polls++;return response({items:[{...queued,processing_status:polls>1?'processed':'queued'}]})}if(url.endsWith('/documents/doc-1/extraction'))return response(extraction);if(url.endsWith('/documents/doc-1/download'))return response({}) ;return response({},404)})
    vi.stubGlobal('fetch',fetchMock)
    vi.spyOn(URL,'createObjectURL').mockReturnValue('blob:synthetic')
    vi.spyOn(URL,'revokeObjectURL').mockImplementation(()=>undefined)
    vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>undefined)
    renderDocs()
    await act(async()=>{for(let i=0;i<20;i++)await Promise.resolve()})
    expect(screen.getByText('queued')).toBeInTheDocument()
    await act(async()=>{await vi.advanceTimersByTimeAsync(2100);for(let i=0;i<20;i++)await Promise.resolve()})
    expect(screen.getByText('processed')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'View extracted fields'}))
    await act(async()=>{for(let i=0;i<20;i++)await Promise.resolve()})
    expect(screen.getByText('Not available')).toBeInTheDocument()
    expect(screen.getByText('not extracted')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'Download'}))
    await act(async()=>{for(let i=0;i<20;i++)await Promise.resolve()})
    expect(fetchMock.mock.calls.some(([input,init])=>String(input).endsWith('/documents/doc-1/download')&&new Headers(init?.headers).get('Authorization')==='Bearer test-token')).toBe(true)
  })

  it('shows upload and reprocess controls only for matching permissions',async()=>{
    const fetchMock=vi.fn(async(input:RequestInfo|URL)=>{const url=String(input),initial=bootstrap(url,verifier);if(initial)return initial;if(url.endsWith('/fdrs/fdr-1/documents'))return response({items:[{...queued,processing_status:'failed'}]});return response({},404)})
    vi.stubGlobal('fetch',fetchMock)
    renderDocs()
    expect(await screen.findByText('failed')).toBeInTheDocument()
    expect(screen.queryByLabelText(/Choose PDF, PNG, or JPEG/)).not.toBeInTheDocument()
    expect(screen.getByRole('button',{name:'Reprocess'})).toBeInTheDocument()
  })

  it.each([
    ['Download','/documents/doc-1/download'],
    ['View extracted fields','/documents/doc-1/extraction'],
    ['Reprocess','/documents/doc-1/reprocess'],
  ])('shows the safe missing-file message after %s',async(button,path)=>{
    const fetchMock=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
      void init
      const url=String(input),initial=bootstrap(url,verifier)
      if(initial)return initial
      if(url.endsWith('/fdrs/fdr-1/documents'))return response({items:[queued]})
      if(url.endsWith(path))return response({detail:'The stored file is no longer available'},410)
      return response({},404)
    })
    vi.stubGlobal('fetch',fetchMock)
    renderDocs()
    fireEvent.click(await screen.findByRole('button',{name:button}))
    expect(await screen.findByRole('alert')).toHaveTextContent('The stored file is no longer available')
    expect(fetchMock.mock.calls.some(([input])=>String(input).endsWith(path))).toBe(true)
  })
})
