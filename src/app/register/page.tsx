'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import Navbar from '@/components/Navbar';
import { registerArtifact } from '@/services/client';
import { Database, CheckCircle, Loader2 } from 'lucide-react';

export default function RegisterPage() {
  const [file, setFile] = useState<File | null>(null);
  const [model, setModel] = useState('Gemini 2.5');
  const [version, setVersion] = useState('2.5');
  const [action, setAction] = useState('GENERATED');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successHash, setSuccessHash] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsSubmitting(true);
    try {
      const res = await registerArtifact(file, { model, version, action });
      setSuccessHash(res.hash);
    } catch (err) {
      console.error(err);
      alert('Registration failed. Check console for details.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-gray-900">
      <Navbar />

      <main className="pt-32 pb-20 px-4 max-w-xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-black/[0.07] p-8 shadow-sm"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Developer Registry Screen</h1>
              <p className="text-[13px] text-gray-500">Register new AI artifacts directly into the provenance ledger</p>
            </div>
          </div>

          {successHash ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-6 text-center space-y-3">
              <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto" />
              <h3 className="font-semibold text-emerald-800">Artifact Registered!</h3>
              <p className="text-[12px] font-mono text-emerald-700 break-all bg-emerald-100/50 p-2.5 rounded-lg">
                SHA-256: {successHash}
              </p>
              <button
                onClick={() => {
                  setFile(null);
                  setSuccessHash(null);
                }}
                className="mt-2 text-xs font-semibold text-blue-600 hover:underline"
              >
                Register Another Artifact
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                  Artifact File
                </label>
                <input
                  type="file"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  required
                  className="w-full text-xs text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                  Model Identity
                </label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                    Version
                  </label>
                  <input
                    type="text"
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                    Action
                  </label>
                  <select
                    value={action}
                    onChange={(e) => setAction(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:border-blue-500 bg-white"
                  >
                    <option value="GENERATED">GENERATED</option>
                    <option value="TRANSFORMED">TRANSFORMED</option>
                    <option value="UPSCALED">UPSCALED</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={!file || isSubmitting}
                className="w-full mt-4 h-11 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Anchor to Provenance Ledger'}
              </button>
            </form>
          )}
        </motion.div>
      </main>
    </div>
  );
}
