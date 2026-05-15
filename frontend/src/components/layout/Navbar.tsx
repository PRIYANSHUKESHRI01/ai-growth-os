"use client";

import Link from "next/link";
import Image from "next/image";
import {
  SignInButton,
  SignUpButton,
  UserButton,
  useAuth,
} from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

export function Navbar() {
  const { isSignedIn, isLoaded } = useAuth();

  return (
    <nav className="fixed top-0 left-0 right-0 h-16 border-b border-border bg-card/80 backdrop-blur-md z-50">
      <div className="max-w-6xl mx-auto px-6 h-full flex items-center justify-between">

        {/* ── Brand ── */}
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-3">
            {/* Logo — no container, no border, no hover effect. White bg blends with navbar. */}
            <Image
              src="/logo.png"
              alt="AI Growth OS"
              width={44}
              height={44}
              className="object-contain"
              priority
            />
            <span className="font-bold text-xl text-primary tracking-tight">
              AI Growth OS
            </span>
          </Link>

          {/* Nav links */}
          <div className="hidden md:flex items-center gap-6 text-sm font-medium text-secondary">
            <Link href="/" className="hover:text-primary transition-colors">Platform</Link>
            <Link href="/" className="hover:text-primary transition-colors">Solutions</Link>
            <Link href="/" className="hover:text-primary transition-colors">Resources</Link>
            <Link href="/" className="hover:text-primary transition-colors">Pricing</Link>
          </div>
        </div>

        {/* ── Auth ── */}
        <div className="flex items-center gap-3">
          {!isLoaded ? null : !isSignedIn ? (
            <>
              <SignInButton mode="redirect">
                <Button variant="ghost" size="sm">Log In</Button>
              </SignInButton>
              <SignUpButton mode="redirect">
                <Button variant="primary" size="sm">Get Started</Button>
              </SignUpButton>
            </>
          ) : (
            <>
              <Link href="/dashboard">
                <Button variant="ghost" size="sm">Dashboard</Button>
              </Link>
              <UserButton />
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
