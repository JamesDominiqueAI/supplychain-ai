import { SignIn, SignedIn, UserButton } from "@clerk/nextjs";
import Head from "next/head";
import Link from "next/link";

export default function LoginPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

  if (!clerkEnabled) {
    return (
      <>
        <Head>
          <title>Login | SupplyChain AI</title>
        </Head>
        <main className="page shell auth-plain-page">
          <section className="auth-plain-panel">
            <div className="auth-copy auth-copy-plain">
              <p className="eyebrow">Clerk Setup Required</p>
              <h1>Configure Clerk keys to enable sign-in.</h1>
              <p className="lede">
                Add `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` to your `.env`, then restart the
                frontend.
              </p>
              <div className="card-actions">
                <Link className="button primary" href="/">
                  Back Home
                </Link>
              </div>
            </div>
          </section>
        </main>
      </>
    );
  }

  return (
    <>
      <Head>
        <title>Login | SupplyChain AI</title>
      </Head>
      <main className="page shell auth-plain-page">
        <section className="auth-plain-panel">
          <div className="auth-copy auth-copy-plain">
            <p className="eyebrow">Sign In</p>
            <h1>Open your inventory workspace.</h1>
            <p className="lede">
              Sign in with Clerk to access products, orders, movements, reports, suppliers, and settings.
            </p>
            <SignedIn>
              <div className="signed-in-banner">
                <p>You are already signed in.</p>
                <div className="card-actions">
                  <Link className="button primary" href="/dashboard" prefetch={false}>
                    Go to Dashboard
                  </Link>
                  <UserButton />
                </div>
              </div>
            </SignedIn>
          </div>
          <div className="auth-form auth-form-plain clerk-shell">
            <SignIn
              path="/login"
              routing="path"
              signUpUrl="/login"
              forceRedirectUrl="/dashboard"
              appearance={{
                elements: {
                  rootBox: "clerk-root",
                  card: "clerk-card",
                },
              }}
            />
          </div>
        </section>
      </main>
    </>
  );
}
