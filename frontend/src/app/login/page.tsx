import { login } from '@/app/auth/actions'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import Link from 'next/link'

export default function LoginPage({
  searchParams,
}: {
  searchParams: { error?: string; message?: string }
}) {
  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-background">
      <Card className="w-full max-w-md border-border bg-surface shadow-sm">
        <CardHeader className="space-y-2 text-center">
          <CardTitle className="text-2xl font-bold tracking-tight text-brand-sage font-serif">
            Welcome back
          </CardTitle>
          <CardDescription className="text-secondary">
            Enter your email to sign in to your ResearchPilot account
          </CardDescription>
        </CardHeader>
        <form action={login}>
          <CardContent className="space-y-4">
            {searchParams?.message && (
              <div className="rounded-md bg-brand-sage/10 border border-brand-sage/20 p-3 text-sm text-brand-sage">
                {searchParams.message}
              </div>
            )}
            {searchParams?.error && (
              <div className="rounded-md bg-status-error/10 border border-status-error/20 p-3 text-sm text-status-error">
                {searchParams.error}
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium leading-none text-foreground">
                Email
              </label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="researcher@example.com"
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium leading-none text-foreground">
                Password
              </label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="••••••••"
                required
                autoComplete="current-password"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button variant="brand" className="w-full font-medium" type="submit">
              Sign In
            </Button>
            <div className="text-center text-sm text-secondary">
              Don&apos;t have an account?{' '}
              <Link href="/signup" className="text-brand-sage hover:underline font-medium">
                Sign up
              </Link>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
