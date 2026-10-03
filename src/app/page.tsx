'use client';

import { useState, useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Navbar from '@/components/Navbar';
import DragDropZone from '@/components/DragDropZone';
import VerificationResultCard from '@/components/VerificationResult';
import LineageTree from '@/components/LineageTree';
import CryptoProof from '@/components/CryptoProof';
import VerifyingState from '@/components/VerifyingState';
import { verifyArtifact, type VerificationResult, type MockMode } from '@/services/client';
import { ShieldCheck, ShieldAlert, Sliders, Layers, Lock, AlertTriangle, Cpu } from 'lucide-react';

const STEP_TIMINGS = [500, 900, 1500, 2000];

const KEY_FEATURES = [
  { icon: ShieldCheck, title: 'Provenance Verification', desc: 'Verifies claimed origin & generation history' },
  { icon: ShieldAlert, title: 'Provenance Trust', desc: 'Evaluates verifiable evidence & trust levels' },
  { icon: Sliders, title: 'Transformation Handling', desc: 'Preserves lineage across edits & format changes' },
  { icon: Layers, title: 'Multi-System Provenance', desc: 'Tracks artifacts across multi-stage AI pipelines' },
  { icon: AlertTriangle, title: 'Tamper Detection', desc: 'Flags payload alterations & inconsistent claims' },
  { icon: Lock, title: 'Privacy-Preserving ZK', desc: 'Salted prompt hash without exposing prompt data' },
  { icon: Cpu, title: 'Adversarial Testing', desc: 'Resilient evaluation against fabricated manifests' },
];

export default function Home() {
  const [mockMode, setMockMode] = useState<MockMode>('live');
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyStep, setVerifyStep] = useState(0);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleVerify = async (file: File) => {
    setResult(null);
    setError(null);
    setVerifyStep(0);
    setIsVerifying(true);

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (file.type.startsWith('image/')) {
      setPreviewUrl(URL.createObjectURL(file));
    } else {
      setPreviewUrl(null);
    }

    const stepTimers = STEP_TIMINGS.map((ms, i) =>
      setTimeout(() => setVerifyStep(i), ms)
    );

    try {
      const data = await verifyArtifact(file, mockMode);
      setResult(data);
    } catch (err: any) {
      setError(err?.message || 'Verification failed. Please try again.');
    } finally {
      stepTimers.forEach(clearTimeout);
      setIsVerifying(false);
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 150);
    }
  };

  const handleReset = () => {
    setResult(null);
    setError(null);
    setPreviewUrl(null);
    setVerifyStep(0);
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-gray-900">
      <Navbar />

      {/* Hero Header */}
      <section className="pt-32 pb-12 px-4 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="max-w-3xl mx-auto"
        >
          <p className="text-[11px] font-bold tracking-[0.22em] uppercase text-blue-600 mb-4">
            Cryptographic AI Content Provenance System
          </p>

          <h1 className="text-4xl sm:text-5xl lg:text-[3.75rem] font-bold leading-[1.08] tracking-tight text-gray-900 mb-5">
            VERIFY THE<br />
            <span className="text-blue-600">ORIGIN OF AI CONTENT.</span>
          </h1>

          <p className="text-[16px] sm:text-[17px] text-gray-500 leading-relaxed max-w-xl mx-auto mb-10">
            Trace an artifact from creation through every transformation —
            and verify its provenance with cryptographic evidence.
          </p>

          <DragDropZone
            onVerify={handleVerify}
            isLoading={isVerifying}
            mockMode={mockMode}
            onMockModeChange={setMockMode}
          />
        </motion.div>
      </section>

      {/* 7 Key Features Highlights Bar */}
      <section className="max-w-5xl mx-auto px-4 pb-12">
        <div className="bg-white/70 backdrop-blur-xl rounded-2xl border border-black/[0.06] p-6 shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-gray-400 mb-4 text-center">
            CORE PROVENANCE INSPECTION CAPABILITIES
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 text-center">
            {KEY_FEATURES.map((feat, i) => {
              const Icon = feat.icon;
              return (
                <div key={i} className="p-2.5 rounded-xl bg-gray-50/80 border border-gray-100/80 flex flex-col items-center">
                  <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center mb-1.5">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <p className="text-[11px] font-bold text-gray-800 leading-tight">{feat.title}</p>
                  <p className="text-[9.5px] text-gray-400 mt-0.5 leading-tight">{feat.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Results */}
      <AnimatePresence>
        {(isVerifying || result || error) && (
          <motion.div
            ref={resultsRef}
            key="results"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="px-4 pb-24 space-y-6"
          >
            <AnimatePresence>
              {isVerifying && (
                <VerifyingState key="verifying" currentStep={verifyStep} />
              )}
            </AnimatePresence>

            {error && !isVerifying && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-2xl mx-auto bg-red-50 border border-red-200 rounded-2xl p-6 text-center"
              >
                <p className="text-[14px] font-semibold text-red-700 mb-1">
                  Verification Error
                </p>
                <p className="text-[13px] text-red-500">{error}</p>
              </motion.div>
            )}

            {result && !isVerifying && (
              <>
                <VerificationResultCard result={result} />

                {(result.history.length > 0 || previewUrl) && (
                  <LineageTree
                    result={result}
                    artifactPreviewUrl={previewUrl ?? undefined}
                  />
                )}

                <CryptoProof result={result} />

                <div className="flex justify-center pt-2">
                  <button
                    onClick={handleReset}
                    className="text-[13px] font-medium text-gray-400 hover:text-gray-600 transition-colors underline underline-offset-2"
                  >
                    Verify another artifact
                  </button>
                </div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <footer className="border-t border-black/[0.06] bg-white/60 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-md bg-blue-600 flex items-center justify-center">
              <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="text-white">
                <path d="M4 3h5.5a2.5 2.5 0 0 1 0 5H4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                <path d="M4 3v10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="text-[13px] font-semibold text-gray-600">ProvLedger</span>
          </div>
          <p className="text-[12px] text-gray-400 text-center">
            Cryptographic provenance for AI-generated content.
          </p>
          <p className="text-[11px] text-gray-300 tracking-wider uppercase">
            ● SYSTEM ONLINE
          </p>
        </div>
      </footer>
    </div>
  );
}
