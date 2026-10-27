import React, { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { useAuth } from '../auth/AuthContext'
import { PageHeading } from '../components/RegistryPrimitives'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { responseError } from '../lib/registry'

const schema = z.object({
  institution_code: z.string().trim().min(1, 'Enter an institution code.').max(32),
  institution_name: z.string().trim().min(1, 'Enter an institution name.').max(200),
  institution_type: z.string().max(80),
  state: z.string().max(80),
  contact_email: z.string().max(254).refine((value) => !value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value), 'Enter a valid email address.'),
})
type FormValues = z.infer<typeof schema>

export default function InstitutionFormPage() {
  const { apiFetch } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema), defaultValues: { institution_code: '', institution_name: '', institution_type: '', state: '', contact_email: '' },
  })

  async function submit(values: FormValues) {
    setServerError('')
    const response = await apiFetch('/api/v1/institutions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...values, institution_type: values.institution_type || null, state: values.state || null, contact_email: values.contact_email || null }),
    })
    if (!response.ok) { setServerError(await responseError(response)); return }
    const institution = await response.json() as { id: string }
    navigate(`/institutions/${institution.id}`)
  }

  return <section>
    <PageHeading title="Add institution" description="Register an institution using synthetic or authorised project data." />
    <Card><CardContent className="p-5 sm:p-7">
      <form className="grid gap-5 sm:grid-cols-2" onSubmit={handleSubmit(submit)} noValidate>
        <Field label="Institution code" error={errors.institution_code?.message}><Input {...register('institution_code')} autoComplete="off" /></Field>
        <Field label="Institution name" error={errors.institution_name?.message}><Input {...register('institution_name')} /></Field>
        <Field label="Institution type" error={errors.institution_type?.message}><Input {...register('institution_type')} /></Field>
        <Field label="State" error={errors.state?.message}><Input {...register('state')} /></Field>
        <Field label="Contact email" error={errors.contact_email?.message}><Input type="email" {...register('contact_email')} /></Field>
        {serverError && <p role="alert" className="sm:col-span-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{serverError}</p>}
        <div className="flex gap-3 sm:col-span-2"><Button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Saving…' : 'Create institution'}</Button><Button type="button" variant="outline" onClick={() => navigate('/institutions')}>Cancel</Button></div>
      </form>
    </CardContent></Card>
  </section>
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactElement<{ id?: string; 'aria-invalid'?: boolean }> }) {
  const id = label.toLowerCase().replaceAll(' ', '-')
  return <div className="space-y-1.5"><label htmlFor={id} className="text-sm font-medium">{label}</label>{React.cloneElement(children, { id, 'aria-invalid': Boolean(error) })}{error && <p role="alert" className="text-xs text-rose-700">{error}</p>}</div>
}
