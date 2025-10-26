import Link from "next/link";

export function Nav() {
  return (
    <header className="border-b border-zinc-200 dark:border-zinc-700">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
        <Link href="/" className="font-semibold">Patent Scoring</Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/" className="hover:underline">Home</Link>
          <Link href="/settings" className="hover:underline">Settings</Link>
        </nav>
      </div>
    </header>
  );
}
