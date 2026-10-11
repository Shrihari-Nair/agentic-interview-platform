import Link from 'next/link';
import {
  FileText,
  Target,
  Mic,
  ArrowRight,
  Sparkles,
  Code2,
  BarChart3,
  Brain,
} from 'lucide-react';
import { AuroraBackground } from '../components/AuroraBackground';

const FEATURES = [
  {
    icon: FileText,
    title: 'Resume Analysis',
    desc: 'Upload your resume — our AI extracts your skills, projects, and gaps.',
    tint: 'text-blue-400',
  },
  {
    icon: Target,
    title: 'Tailored Questions',
    desc: 'Questions specific to your background AND the job description.',
    tint: 'text-cyan-300',
  },
  {
    icon: Mic,
    title: 'Voice Interview',
    desc: 'Real-time voice interview with a professional AI interviewer.',
    tint: 'text-violet-400',
  },
  {
    icon: Code2,
    title: 'Live Coding',
    desc: 'Solve problems in an in-browser editor while the interviewer watches.',
    tint: 'text-emerald-300',
  },
  {
    icon: Brain,
    title: 'Remembers You',
    desc: 'Opt in and future sessions focus on the areas you struggled with.',
    tint: 'text-fuchsia-300',
  },
  {
    icon: BarChart3,
    title: 'Instant Report',
    desc: 'Scored feedback on every answer the moment the interview ends.',
    tint: 'text-amber-300',
  },
];

const STEPS = [
  { n: '01', title: 'Drop in your resume', desc: 'Plus the job description you are targeting.' },
  { n: '02', title: 'Talk it out', desc: 'A 30-minute voice interview, tuned to you.' },
  { n: '03', title: 'Get your scorecard', desc: 'See what landed, what did not, and what to fix.' },
];

const STATS = [
  ['2 min', 'to set up'],
  ['30 min', 'live interview'],
  ['0', 'awkward small talk'],
];

const WAVE_DELAYS = [0, 0.15, 0.3, 0.1, 0.4, 0.2, 0.35, 0.05, 0.25, 0.45, 0.12, 0.3];

function InterviewPreview() {
  return (
    <div className="relative mx-auto w-full max-w-xl [animation:float-y_7s_ease-in-out_infinite]">
      <div className="absolute -inset-6 rounded-[2rem] bg-gradient-to-r from-blue-600/30 via-violet-600/30 to-cyan-500/30 blur-3xl" aria-hidden />
      <div className="glow-border glow-border-always relative rounded-3xl border border-white/10 bg-slate-900/70 p-5 text-left shadow-2xl shadow-black/50 backdrop-blur-2xl">
        {/* header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="relative flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-violet-500">
              <span className="absolute inset-0 rounded-full bg-blue-400/50 [animation:ping-soft_2.4s_ease-out_infinite]" aria-hidden />
              <Sparkles className="relative h-5 w-5 text-white" />
            </span>
            <div>
              <p className="font-display text-sm font-semibold">Aria · AI Interviewer</p>
              <p className="text-xs text-emerald-400">● Live · Question 3 of 8</p>
            </div>
          </div>
          <div className="flex h-8 items-end gap-[3px]" aria-hidden>
            {WAVE_DELAYS.map((d, i) => (
              <span
                key={i}
                className="h-full w-[3px] origin-bottom rounded-full bg-gradient-to-t from-blue-500 to-cyan-300"
                style={{ animation: `wave 1.1s ease-in-out ${d}s infinite` }}
              />
            ))}
          </div>
        </div>

        {/* transcript */}
        <div className="mt-5 space-y-3 text-sm">
          <p className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white/5 px-4 py-3 text-slate-200">
            You led the payments migration. Walk me through how you handled rollback safety.
          </p>
          <p className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-gradient-to-r from-blue-600/80 to-violet-600/80 px-4 py-3 text-white">
            We shipped behind a feature flag and replayed traffic against both systems before cutover…
          </p>
          <div className="flex items-center gap-1.5 px-1" aria-label="Interviewer is thinking">
            {[0, 0.2, 0.4].map((d) => (
              <span
                key={d}
                className="h-1.5 w-1.5 rounded-full bg-slate-400"
                style={{ animation: `blink-dot 1.2s ease-in-out ${d}s infinite` }}
              />
            ))}
          </div>
        </div>

        {/* score chips */}
        <div className="mt-5 flex flex-wrap gap-2 text-xs font-medium">
          <span className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-emerald-300">
            Clarity 9/10
          </span>
          <span className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-cyan-300">
            Depth 8/10
          </span>
          <span className="rounded-full border border-violet-400/30 bg-violet-500/10 px-3 py-1 text-violet-300">
            Structure 7/10
          </span>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <AuroraBackground />
      <div className="bg-grid pointer-events-none absolute inset-0 -z-10" aria-hidden />

      <div className="relative z-10 mx-auto max-w-5xl space-y-24 px-6 pb-24 pt-16 text-center sm:pt-24">
        {/* Hero */}
        <section className="space-y-8">
          <div className="animate-fade-in-up">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-medium text-slate-300 backdrop-blur">
              <span className="relative flex h-2 w-2">
                <span className="absolute inset-0 rounded-full bg-emerald-400 [animation:ping-soft_2s_ease-out_infinite]" aria-hidden />
                <span className="relative h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              Voice-first AI interviewer
            </span>
          </div>

          <h1
            className="animate-fade-in-up font-display text-5xl font-bold leading-[1.05] tracking-tight sm:text-7xl"
            style={{ animationDelay: '0.1s' }}
          >
            Ace the interview
            <br />
            <span className="text-shimmer bg-gradient-to-r from-blue-400 via-cyan-300 to-violet-400 bg-clip-text text-transparent">
              before it counts.
            </span>
          </h1>

          <p
            className="animate-fade-in-up mx-auto max-w-xl text-lg text-slate-300 sm:text-xl"
            style={{ animationDelay: '0.2s' }}
          >
            MockMind runs a realistic voice interview built from your resume and the job you
            want — then tells you exactly how you did.
          </p>

          <div className="animate-fade-in-up space-y-4" style={{ animationDelay: '0.3s' }}>
            <Link
              href="/setup"
              className="group relative inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-blue-600 via-violet-600 to-cyan-500 px-10 py-4 text-xl font-bold text-white shadow-2xl shadow-violet-600/30 transition-all duration-300 hover:scale-[1.03] hover:shadow-violet-500/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300 active:scale-[0.98]"
            >
              Start Your Interview
              <ArrowRight className="h-5 w-5 transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
            <p className="text-sm text-slate-400">Takes 2 minutes to set up · 30-minute interview · Instant feedback report</p>
          </div>
        </section>

        {/* Product preview */}
        <section className="animate-fade-in-up" style={{ animationDelay: '0.45s' }}>
          <InterviewPreview />
        </section>

        {/* Stats */}
        <section className="grid grid-cols-3 gap-4">
          {STATS.map(([big, small]) => (
            <div key={small} className="space-y-1">
              <p className="bg-gradient-to-r from-blue-300 to-cyan-200 bg-clip-text font-display text-3xl font-bold text-transparent sm:text-5xl">
                {big}
              </p>
              <p className="text-xs uppercase tracking-widest text-slate-400 sm:text-sm">{small}</p>
            </div>
          ))}
        </section>

        {/* Features */}
        <section className="space-y-10">
          <h2 className="font-display text-3xl font-bold sm:text-4xl">
            Everything a real interview throws at you
          </h2>
          <div className="grid grid-cols-1 gap-5 text-left sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="glow-border group space-y-3 rounded-2xl border border-white/10 bg-white/5 p-6 shadow-lg shadow-black/20 backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:bg-white/10"
              >
                <f.icon
                  aria-hidden
                  className={`h-9 w-9 ${f.tint} transition-transform duration-300 group-hover:scale-110`}
                />
                <h3 className="font-display text-lg font-semibold">{f.title}</h3>
                <p className="text-sm text-slate-300">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section className="space-y-10">
          <h2 className="font-display text-3xl font-bold sm:text-4xl">Three steps. Zero prep.</h2>
          <ol className="grid grid-cols-1 gap-5 text-left md:grid-cols-3">
            {STEPS.map((s) => (
              <li key={s.n} className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
                <span className="bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text font-display text-4xl font-bold text-transparent">
                  {s.n}
                </span>
                <h3 className="mt-3 font-display text-lg font-semibold">{s.title}</h3>
                <p className="mt-1 text-sm text-slate-300">{s.desc}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Final CTA */}
        <section className="glow-border glow-border-always rounded-3xl border border-white/10 bg-gradient-to-br from-blue-600/10 via-violet-600/10 to-cyan-500/10 px-6 py-14 backdrop-blur-xl">
          <h2 className="font-display text-3xl font-bold sm:text-4xl">Your next interview starts here.</h2>
          <Link
            href="/setup"
            className="group mt-8 inline-flex items-center gap-2 rounded-2xl bg-white px-8 py-3.5 text-lg font-bold text-slate-900 transition-all duration-300 hover:scale-[1.03] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300 active:scale-[0.98]"
          >
            Get started
            <ArrowRight className="h-5 w-5 transition-transform duration-300 group-hover:translate-x-1" />
          </Link>
        </section>
      </div>
    </main>
  );
}
