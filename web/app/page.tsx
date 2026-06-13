export default function Home() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-end px-6 pb-[10dvh]">
      <h1 className="font-display text-4xl mb-2">Blindspot</h1>
      <p className="text-bone/70 mb-10">One of you doesn&apos;t know the word.</p>
      {/* Create / join controls land in M1 with the rooms API. */}
      <p className="text-bone/50 text-sm">Waiting for the first room. Check back at M1.</p>
    </main>
  );
}
