export function AuroraBackground({ subtle = false }: { subtle?: boolean }) {
  const opacity = subtle ? 'opacity-40' : 'opacity-100';
  return (
    <div
      className={`pointer-events-none fixed inset-0 -z-10 overflow-hidden ${opacity}`}
      aria-hidden
    >
      <div className="absolute -top-40 -left-40 h-[32rem] w-[32rem] rounded-full bg-blue-600/30 blur-3xl [animation:aurora-drift-1_18s_ease-in-out_infinite]" />
      <div className="absolute top-1/3 -right-32 h-[28rem] w-[28rem] rounded-full bg-cyan-500/20 blur-3xl [animation:aurora-drift-2_22s_ease-in-out_infinite]" />
      <div className="absolute -bottom-40 left-1/4 h-[30rem] w-[30rem] rounded-full bg-purple-600/20 blur-3xl [animation:aurora-drift-3_20s_ease-in-out_infinite]" />
    </div>
  );
}
