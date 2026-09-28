import Link from 'next/link';
import { FileText, Target, Mic, ArrowRight } from 'lucide-react';
import { AuroraBackground } from '../components/AuroraBackground';

const FEATURES = [
  {
    icon: FileText,
    title: 'Resume Analysis',
    desc: 'Upload your resume — our AI extracts your skills, projects, and gaps.',
  },
  {
    icon: Target,
    title: 'Tailored Questions',
    desc: 'Questions specific to your background AND the job description.',
  },
  {
    icon: Mic,
    title: 'Voice Interview',
    desc: 'Real-time voice interview with a professional AI interviewer.',
  },
];

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden flex flex-col items-center justify-center p-8">
      <AuroraBackground />

      <div className="relative z-10 max-w-3xl w-full text-center space-y-8">
        {/* Logo */}
        <div className="animate-fade-in-up">
          <h1 className="font-display text-6xl font-bold tracking-tight bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">
            MockMind
          </h1>
          <p className="text-xl text-slate-400 mt-3">
            AI-powered mock interviews, personalized to your resume.
          </p>
        </div>

        {/* Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 my-12">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className="group bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6 space-y-3 shadow-lg shadow-black/20 transition-all duration-300 hover:-translate-y-1 hover:border-blue-400/30 hover:bg-white/10 hover:shadow-blue-500/10 animate-fade-in-up"
              style={{ animationDelay: `${0.15 + i * 0.1}s` }}
            >
              <f.icon className="w-9 h-9 text-blue-400 transition-transform duration-300 group-hover:scale-110" />
              <h3 className="font-display font-semibold text-lg">{f.title}</h3>
              <p className="text-slate-400 text-sm">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="animate-fade-in-up" style={{ animationDelay: '0.5s' }}>
          <Link
            href="/setup"
            className="group inline-flex items-center gap-2 px-10 py-4 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-bold text-xl rounded-2xl transition-all duration-300 hover:scale-[1.03] active:scale-[0.98] shadow-2xl shadow-blue-600/30"
          >
            Start Your Interview
            <ArrowRight className="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1" />
          </Link>

          <p className="text-slate-500 text-sm mt-4">
            Takes 2 minutes to set up · 30-minute interview · Instant feedback report
          </p>
        </div>
      </div>
    </main>
  );
}
