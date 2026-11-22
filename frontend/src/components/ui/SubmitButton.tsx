'use client'
import { useFormStatus } from 'react-dom'
import { Button } from './Button'
export function SubmitButton({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus()
  return <Button variant="brand" type="submit" disabled={pending} aria-busy={pending}>{pending ? 'Please wait?' : children}</Button>
}
