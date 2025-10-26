import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Patent Scoring</h1>
      <p className="text-zinc-600 dark:text-zinc-300">
        Frontend is running. Go to Settings to configure the API base URL and your APP_API_KEY.
      </p>
      <Link href="/settings" className="inline-block rounded bg-black px-4 py-2 text-white">
        Open Settings
      </Link>
    </div>
  );
}
