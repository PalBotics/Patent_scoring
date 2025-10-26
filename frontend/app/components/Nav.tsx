"use client";

import Link from "next/link";
import { useTheme } from "./ThemeProvider";

export function Nav() {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="border-b border-zinc-200 dark:border-zinc-700">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
        <Link href="/" className="font-semibold">Patent Scoring</Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/" className="hover:underline">Home</Link>
          <Link href="/records" className="hover:underline">Records</Link>
          <Link href="/settings" className="hover:underline">Settings</Link>
          <button
            onClick={toggleTheme}
            className="rounded border border-zinc-300 dark:border-zinc-600 px-2 py-1 text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800"
            aria-label="Toggle theme"
          >
            {theme === "light" ? "🌙" : "☀️"}
          </button>
        </nav>
      </div>
    </header>
  );
}
