import { ClerkProvider } from "@clerk/nextjs";
import type { AppProps } from "next/app";
import Head from "next/head";

import "../styles/globals.css";

export default function App({ Component, pageProps }: AppProps) {
  const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  if (!clerkPublishableKey) {
    return <Component {...pageProps} />;
  }

  return (
    <>
      <Head>
        <link rel="icon" href="/icon.svg" type="image/svg+xml" />
      </Head>
      <ClerkProvider
        publishableKey={clerkPublishableKey}
        signInFallbackRedirectUrl="/dashboard"
        signUpFallbackRedirectUrl="/dashboard"
        {...pageProps}
        appearance={{ cssLayerName: "clerk" }}
      >
        <Component {...pageProps} />
      </ClerkProvider>
    </>
  );
}
