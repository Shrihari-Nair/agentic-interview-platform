import Link from 'next/link';

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col items-center justify-center p-8 text-white">
      <div className="max-w-3xl w-full text-center space-y-8">
        {/* Logo */}
        <div>
          <h1 className="text-6xl font-black tracking-tight bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
            MockMind
          </h1>
          <p className="text-xl text-slate-400 mt-3">
            AI-powered mock interviews, personalized to your resume.
          </p>
        </div>

        {/* Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 my-12">
          {[
            {
              icon: '📄',
              title: 'Resume Analysis',
              desc: 'Upload your resume — our AI extracts your skills, projects, and gaps.',
            },
            {
              icon: '🎯',
              title: 'Tailored Questions',
              desc: 'Questions specific to your background AND the job description.',
            },
            {
              icon: '🎙️',
              title: 'Voice Interview',
              desc: 'Real-time voice interview with a professional AI interviewer.',
            },
          ].map((f) => (
            <div
              key={f.title}
              className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 space-y-3"
            >
              <div className="text-4xl">{f.icon}</div>
              <h3 className="font-bold text-lg">{f.title}</h3>
              <p className="text-slate-400 text-sm">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* CTA */}
        <Link
          href="/setup"
          className="inline-block px-10 py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xl rounded-2xl transition-colors shadow-xl shadow-blue-600/20"
        >
          Start Your Interview →
        </Link>

        <p className="text-slate-500 text-sm mt-4">
          Takes 2 minutes to set up · 30-minute interview · Instant feedback report
        </p>
      </div>
    </main>
  );
}
