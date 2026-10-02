'use client';

import { useState } from 'react';
import Editor from '@monaco-editor/react';
import { Code2, Send } from 'lucide-react';

export interface CodingChallenge {
  question_id: string;
  language: string;
  problem_statement: string;
  starter_code: string;
}

export function CodeEditorPanel({
  challenge,
  onSubmit,
}: {
  challenge: CodingChallenge;
  onSubmit: (code: string) => void;
}) {
  const [code, setCode] = useState(challenge.starter_code);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl h-[85vh] bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-fade-in-up">
        {/* Header */}
        <div className="flex items-center gap-2 px-6 py-4 border-b border-white/10 shrink-0">
          <Code2 className="w-5 h-5 text-blue-400" />
          <h2 className="font-display text-lg font-bold text-white">Live Coding Question</h2>
          <span className="ml-auto text-xs text-slate-500 uppercase tracking-wide">
            {challenge.language}
          </span>
        </div>

        {/* Problem statement */}
        <div className="px-6 py-4 border-b border-white/10 shrink-0 max-h-40 overflow-y-auto">
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
            {challenge.problem_statement}
          </p>
        </div>

        {/* Editor */}
        <div className="flex-1 min-h-0">
          <Editor
            height="100%"
            language={challenge.language}
            value={code}
            onChange={(value) => setCode(value ?? '')}
            theme="vs-dark"
            options={{
              fontSize: 14,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              automaticLayout: true,
            }}
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-white/10 shrink-0">
          <p className="text-xs text-slate-500">
            Submit when ready — Alex will review it and react out loud.
          </p>
          <button
            onClick={() => onSubmit(code)}
            disabled={!code.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 disabled:from-white/10 disabled:to-white/10 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-blue-600/20"
          >
            <Send className="w-4 h-4" /> Submit Code
          </button>
        </div>
      </div>
    </div>
  );
}
