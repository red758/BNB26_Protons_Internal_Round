'use client';

import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, ShieldCheck, FileWarning, Database, Settings2 } from 'lucide-react';

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<any>(null);

  const verifyFile = async (droppedFile: File) => {
    setIsProcessing(true);
    const formData = new FormData();
    formData.append('file', droppedFile);

    try {
      const res = await fetch('/api/verify', { method: 'POST', body: formData });
      const data = await res.json();
      setResult(data);
    } catch (error) {
      console.error(error);
    }
    setIsProcessing(false);
  };

  const registerFile = async () => {
    if (!file) return;
    setIsProcessing(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      await fetch('/api/register', { method: 'POST', body: formData });
      alert("Success! Image anchored to Ledger.");
      await verifyFile(file);
    } catch (error) {
      console.error(error);
    }
  };

  const onDrop = async (acceptedFiles: File[]) => {
    const droppedFile = acceptedFiles[0];
    setFile(droppedFile);
    setResult(null);
    await verifyFile(droppedFile);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: { 'image/*': [] }, maxFiles: 1 });

  return (
    <main className="min-h-screen flex flex-col items-center py-20 px-4 bg-slate-900 text-white">
      <h1 className="text-5xl font-extrabold text-blue-400 mb-8">ModelLedger</h1>

      <div {...getRootProps()} className="w-full max-w-2xl p-16 border-2 border-dashed border-slate-600 rounded-2xl cursor-pointer hover:bg-slate-800 transition-all text-center">
        <input {...getInputProps()} />
        <UploadCloud className="w-16 h-16 mx-auto mb-4 text-slate-400" />
        <p className="text-xl">Drag & drop an image to check the Ledger</p>
      </div>

      {isProcessing && <p className="mt-8 text-yellow-400 animate-pulse font-bold">Verifying Cryptographic & Perceptual Hashes...</p>}

      {result && !isProcessing && (
        <div className="mt-8 w-full max-w-2xl">
          {/* STATE 1: EXACT MATCH (Green) */}
          {result.status === "verified_exact" && (
            <div className="bg-slate-800 p-8 rounded-xl border border-green-500 shadow-[0_0_20px_rgba(34,197,94,0.3)]">
              <h2 className="text-2xl font-bold text-green-400 flex items-center mb-4">
                <ShieldCheck className="mr-2"/> Perfect Match: Origin Verified
              </h2>
              <div className="text-slate-300 space-y-2">
                <p><strong className="text-white">Origin:</strong> {result.record.model}</p>
                <p><strong className="text-white">Trust Level:</strong> {result.record.trustLevel}</p>
                <p><strong className="text-white">Status:</strong> File has not been modified since generation.</p>
              </div>
            </div>
          )}

          {/* STATE 2: TRANSFORMED MATCH (Yellow) - THIS WINS HACKATHONS */}
          {result.status === "verified_transformed" && (
            <div className="bg-slate-800 p-8 rounded-xl border border-yellow-500 shadow-[0_0_20px_rgba(234,179,8,0.3)]">
              <h2 className="text-2xl font-bold text-yellow-400 flex items-center mb-4">
                <Settings2 className="mr-2"/> Provenance Verified (Modified File)
              </h2>
              <div className="text-slate-300 space-y-2 mb-4">
                <p><strong className="text-white">Origin:</strong> {result.record.model}</p>
                <p><strong className="text-white">Trust Level:</strong> {result.record.trustLevel}</p>
              </div>
              <div className="p-4 bg-yellow-950/50 text-yellow-200 border border-yellow-700/50 rounded-lg text-sm">
                <strong>Analysis:</strong> {result.message}
              </div>
            </div>
          )}

          {/* STATE 3: UNVERIFIED (Red) */}
          {result.status === "unverified" && (
            <div className="bg-slate-800 p-8 rounded-xl border border-red-500 shadow-[0_0_20px_rgba(239,68,68,0.3)]">
              <h2 className="text-2xl font-bold text-red-400 flex items-center mb-4">
                <FileWarning className="mr-2"/> Unverifiable Origin
              </h2>
              <p className="mb-6 text-slate-300">{result.message}</p>
              <button onClick={registerFile} className="w-full flex justify-center items-center px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg font-bold transition-all">
                <Database className="mr-2 w-5 h-5"/> Simulate AI Generation (Write to Ledger)
              </button>
            </div>
          )}
        </div>
      )}
    </main>
  );
}