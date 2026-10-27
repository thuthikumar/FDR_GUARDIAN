import { zodResolver } from '@hookform/resolvers/zod'
import React from 'react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'
import { useAuth } from '../auth/AuthContext'
import { PageHeading, StateMessage } from '../components/RegistryPrimitives'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { formatDate, responseError, type FdrRecord } from '../lib/registry'

const schema = z.object({
  bank_name: z.string().trim().min(1, 'Enter the bank name.').max(160, 'Bank name must be 160 characters or fewer.'),
  branch_name: z.string().max(160, 'Branch name must be 160 characters or fewer.'),
  fdr_number: z.string().trim().min(1, 'Enter the FDR number.').max(100, 'FDR number must be 100 characters or fewer.'),
  amount: z.string().trim().regex(/^\d{1,12}(\.\d{1,2})?$/, 'Enter a positive amount with at most 2 decimal places.').refine((value) => Number(value) > 0, 'Amount must be greater than zero.'),
  currency: z.string().regex(/^[A-Z]{3}$/, 'Use three uppercase currency letters, such as INR.'),
  issue_date: z.string().date('Enter a valid issue date.').refine((value) => value <= new Date(Date.now() + 86_400_000).toISOString().slice(0, 10), 'Issue date cannot be in the future.'),
  maturity_date: z.string().date('Enter a valid maturity date.'),
}).refine((value) => value.maturity_date > value.issue_date, { message: 'Maturity date must be after issue date.', path: ['maturity_date'] })

type FormValues = z.infer<typeof schema>
const emptyValues: FormValues = { bank_name: '', branch_name: '', fdr_number: '', amount: '', currency: 'INR', issue_date: '', maturity_date: '' }

export default function FdrFormPage() {
  const { recordId } = useParams()
  const { apiFetch, user } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(Boolean(recordId))
  const [loadError, setLoadError] = useState('')
  const [serverError, setServerError] = useState('')
  const [updatedAt, setUpdatedAt] = useState('')
  const { register, handleSubmit, reset, setError, formState: { errors, isSubmitting } } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: emptyValues })

  useEffect(() => {
    if (!recordId) return
    let active = true
    setLoading(true)
    void apiFetch(`/api/v1/fdrs/${recordId}`).then(async (response) => {
      if (!response.ok) throw new Error(await responseError(response))
      return response.json() as Promise<FdrRecord>
    }).then((record) => {
      if (!active) return
      setUpdatedAt(record.updated_at)
      reset({
        bank_name: record.bank_name,
        branch_name: record.branch_name || '',
        fdr_number: record.fdr_number,
        amount: String(record.amount),
        currency: record.currency,
        issue_date: record.issue_date,
        maturity_date: record.maturity_date,
      })
    }).catch((reason: unknown) => {
      if (active) setLoadError(reason instanceof Error ? reason.message : 'FDR record could not be loaded.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [apiFetch, recordId, reset])

  async function submit(values: FormValues) {
    setServerError('')
    const response = await apiFetch(recordId ? `/api/v1/fdrs/${recordId}` : '/api/v1/fdrs', {
      method: recordId ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...(recordId ? { updated_at: updatedAt } : {}),
        ...values,
        branch_name: values.branch_name || null,
        amount: values.amount,
      }),
    })
    if (!response.ok) {
      if (response.status === 409 && recordId) {
        setServerError('This record changed after you opened it. Reload the latest version before saving your changes.')
        return
      }
      try {
        const body = await response.json() as { detail?: unknown }
        if (Array.isArray(body.detail)) {
          let mapped = false
          for (const issue of body.detail) {
            if (!issue || typeof issue !== 'object' || !('loc' in issue) || !('msg' in issue)) continue
            const field = (issue.loc as unknown[]).at(-1)
            if (typeof field === 'string' && field in emptyValues) {
              setError(field as keyof FormValues, { type: 'server', message: String(issue.msg) })
              mapped = true
            }
          }
          setServerError(mapped ? 'Some fields need attention. Review the highlighted errors.' : 'The server rejected this record. Check the entered values.')
        } else {
          setServerError(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`)
        }
      } catch {
        setServerError(await responseError(response))
      }
      return
    }
    const saved = await response.json() as FdrRecord
    navigate(`/fdrs/${saved.id}`, { replace: true })
  }

  if (!user?.permissions.includes('fdr.write')) return <StateMessage kind="error">Your role cannot create or edit FDR records.</StateMessage>
  if (loading) return <StateMessage kind="loading">Loading FDR record…</StateMessage>
  if (loadError) return <StateMessage kind="error">{loadError}</StateMessage>

  return <section>
    <PageHeading title={recordId ? 'Edit FDR record' : 'Add FDR record'} description="Enter the business fields for a manually entered synthetic record." />
    <Card><CardContent className="p-5 sm:p-7">
      <form className="grid gap-5 sm:grid-cols-2" onSubmit={handleSubmit(submit)} noValidate>
        <Field label="Bank name" error={errors.bank_name?.message}><Input autoComplete="organization" {...register('bank_name')} /></Field>
        <Field label="Branch name" error={errors.branch_name?.message}><Input {...register('branch_name')} /></Field>
        <Field label="FDR number" error={errors.fdr_number?.message}><Input autoComplete="off" {...register('fdr_number')} /></Field>
        <Field label="Principal amount" error={errors.amount?.message}><Input inputMode="decimal" {...register('amount')} /></Field>
        <Field label="Currency" error={errors.currency?.message}><Input maxLength={3} {...register('currency')} /></Field>
        <Field label="Issue date" error={errors.issue_date?.message}><Input type="date" {...register('issue_date')} /></Field>
        <Field label="Maturity date" error={errors.maturity_date?.message}><Input type="date" {...register('maturity_date')} /></Field>
        {serverError && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800 sm:col-span-2">{serverError}</p>}
        <div className="flex gap-3 sm:col-span-2"><Button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Saving…' : recordId ? 'Save changes' : 'Create FDR'}</Button><Button type="button" variant="outline" render={<Link to={recordId ? `/fdrs/${recordId}` : '/fdrs'} />}>Cancel</Button></div>
      </form>
      {recordId && updatedAt && <p className="mt-5 text-xs text-slate-500">Record opened {formatDate(updatedAt)}. Your changes are checked against this version.</p>}
    </CardContent></Card>
  </section>
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactElement<{ id?: string; 'aria-invalid'?: boolean }> }) {
  const id = `fdr-${label.toLowerCase().replaceAll(' ', '-')}`
  return <div className="space-y-1.5"><label htmlFor={id} className="text-sm font-medium">{label}</label>{React.cloneElement(children, { id, 'aria-invalid': Boolean(error) })}{error && <p role="alert" className="text-xs text-rose-700">{error}</p>}</div>
}
