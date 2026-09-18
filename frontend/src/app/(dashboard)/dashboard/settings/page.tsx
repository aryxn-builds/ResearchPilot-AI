import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import { revalidatePath } from 'next/cache'
import Link from 'next/link'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { ArrowLeft, User, Shield, LogOut } from 'lucide-react'
import { logout } from '@/app/auth/actions'

export const dynamic = 'force-dynamic'

async function updateProfile(formData: FormData) {
  'use server'
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  const displayName = (formData.get('display_name') as string)?.trim()

  try {
    // 1. Update public.users table (Rule S-03 user isolation)
    const { error: dbError } = await supabase
      .from('users')
      .update({
        display_name: displayName || null,
        updated_at: new Date().toISOString(),
      })
      .eq('id', user.id)

    if (dbError) {
      redirect(`/dashboard/settings?error=${encodeURIComponent(dbError.message)}`)
    }

    // 2. Update auth user metadata
    await supabase.auth.updateUser({
      data: { display_name: displayName },
    })

    revalidatePath('/dashboard/settings')
    revalidatePath('/dashboard')
    redirect('/dashboard/settings?success=Profile updated successfully')
  } catch (err: unknown) {
    if ((err as { digest?: string })?.digest?.startsWith('NEXT_REDIRECT')) {
      throw err
    }
    const message = err instanceof Error ? err.message : 'Failed to update profile'
    redirect(`/dashboard/settings?error=${encodeURIComponent(message)}`)
  }
}

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: { success?: string; error?: string }
}) {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  // Fetch public user profile
  const { data: profile } = await supabase
    .from('users')
    .select('display_name, email, created_at')
    .eq('id', user.id)
    .single()

  const currentDisplayName =
    profile?.display_name || (user.user_metadata?.display_name as string) || ''
  const memberSince = user.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      })
    : 'N/A'

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Link href="/dashboard">
            <Button variant="ghost" size="sm" className="gap-1.5 text-secondary hover:text-foreground">
              <ArrowLeft className="h-4 w-4" /> Back to Dashboard
            </Button>
          </Link>
        </div>
        <h1 className="text-3xl font-bold font-serif tracking-tight text-foreground">
          Account Settings
        </h1>
        <p className="text-secondary text-sm">
          Manage your personal profile and account credentials.
        </p>
      </div>

      {searchParams?.success && (
        <div className="rounded-md bg-brand-sage/10 border border-brand-sage/20 p-4 text-sm text-brand-sage font-medium">
          {searchParams.success}
        </div>
      )}

      {searchParams?.error && (
        <div className="rounded-md bg-status-error/10 border border-status-error/20 p-4 text-sm text-status-error font-medium">
          {searchParams.error}
        </div>
      )}

      <div className="grid gap-6">
        {/* Profile Settings */}
        <Card className="border-border bg-surface shadow-sm">
          <CardHeader>
            <div className="flex items-center gap-2">
              <User className="h-5 w-5 text-brand-sage" />
              <CardTitle className="text-lg font-serif">Profile Information</CardTitle>
            </div>
            <CardDescription className="text-secondary">
              Update how your name appears across research sessions.
            </CardDescription>
          </CardHeader>
          <form action={updateProfile}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="display_name" className="text-sm font-medium text-foreground">
                  Display Name
                </label>
                <Input
                  id="display_name"
                  name="display_name"
                  defaultValue={currentDisplayName}
                  placeholder="Your full name or title"
                  className="max-w-md"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium text-foreground">
                  Email Address
                </label>
                <Input
                  id="email"
                  value={user.email || ''}
                  disabled
                  readOnly
                  className="max-w-md bg-accent-light/50 text-secondary cursor-not-allowed"
                />
                <p className="text-xs text-secondary">
                  Email address cannot be modified directly in MVP.
                </p>
              </div>
            </CardContent>
            <CardFooter className="border-t border-border pt-4">
              <Button variant="brand" type="submit">
                Save Changes
              </Button>
            </CardFooter>
          </form>
        </Card>

        {/* Account Details & Security */}
        <Card className="border-border bg-surface shadow-sm">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-brand-sage" />
              <CardTitle className="text-lg font-serif">Account Details</CardTitle>
            </div>
            <CardDescription className="text-secondary">
              Read-only details regarding your account identity and authentication.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between py-2 border-b border-border">
              <span className="text-secondary font-medium">User Identifier</span>
              <code className="text-xs font-mono bg-accent-light px-2 py-1 rounded text-foreground mt-1 sm:mt-0">
                {user.id}
              </code>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between py-2 border-b border-border">
              <span className="text-secondary font-medium">Member Since</span>
              <span className="text-foreground mt-1 sm:mt-0">{memberSince}</span>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between py-2">
              <span className="text-secondary font-medium">Session Status</span>
              <span className="text-brand-sage font-medium mt-1 sm:mt-0">Active / Authenticated</span>
            </div>
          </CardContent>
          <CardFooter className="border-t border-border pt-4">
            <form action={logout} className="w-full sm:w-auto">
              <Button variant="outline" type="submit" className="text-status-error hover:text-status-error gap-2">
                <LogOut className="h-4 w-4" /> Sign Out
              </Button>
            </form>
          </CardFooter>
        </Card>
      </div>
    </div>
  )
}
