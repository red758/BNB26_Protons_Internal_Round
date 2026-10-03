'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, File as FileIcon, Loader2, ChevronRight } from 'lucide-react';
import type { MockMode } from '@/services/client';

interface DragDropZoneProps {
  onVerify: (file: File) => void;
  isLoading: boolean;
  mockMode: MockMode;
  onMockModeChange: (mode: MockMode) => void;
}

const MOCK_OPTIONS: { value: MockMode; label: string; color: string }[] = [
  { value: 'live',        label: 'Live (Auto)',   color: 'text-gray-600' },
  { value: 'verified',    label: 'Verified',      color: 'text-emerald-600' },
  { value: 'tampered',    label: 'Tampered',      color: 'text-red-600' },
  { value: 'unregistered',label: 'No Record',     color: 'text-amber-600' },
];

export default function DragDropZone({ onVerify, isLoading, mockMode, onMockModeChange }: DragDropZoneProps) {
  const [staged, setStaged] = useState<File | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setStaged(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [], 'video/mp4': [] },
    maxFiles: 1,
    disabled: isLoading,
  });

  const handleVerify = () => {
    if (staged) onVerify(staged);
  };

  const handleDemoClick = () => {
    const demoFile = new globalThis.File(['demo artifact content'], 'ai-generated-image.png', {
      type: 'image/png',
    });
    onVerify(demoFile);
  };

  return (
    <section id="verify" className="w-full max-w-2xl mx-auto">
      {/* Drop zone */}
      <motion.div
        {...(getRootProps() as any)}
        animate={{
          borderColor: isDragActive
            ? 'rgba(59,130,246,0.8)'
            : staged
            ? 'rgba(59,130,246,0.4)'
            : 'rgba(0,0,0,0.12)',
          backgroundColor: isDragActive
            ? 'rgba(239,246,255,0.8)'
            : staged
            ? 'rgba(239,246,255,0.4)'
            : 'rgba(255,255,255,0.7)',
          boxShadow: isDragActive
            ? '0 0 0 4px rgba(59,130,246,0.12), 0 8px 32px rgba(0,0,0,0.06)'
            : '0 4px 24px rgba(0,0,0,0.05)',
        }}
        transition={{ duration: 0.2 }}
        className="relative cursor-pointer rounded-2xl border-2 border-dashed p-10 sm:p-14 text-center backdrop-blur-xl transition-all"
        style={{ outline: 'none' }}
      >
        <input {...getInputProps()} />

        <AnimatePresence mode="wait">
          {staged ? (
            <motion.div
              key="staged"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="flex flex-col items-center gap-3"
            >
              <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
                <FileIcon className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900 text-[15px]">{staged.name}</p>
                <p className="text-[13px] text-gray-400 mt-0.5">
                  {(staged.size / 1048576).toFixed(2)} MB · Click to replace
                </p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="flex flex-col items-center gap-3"
            >
              <motion.div
                animate={{ scale: isDragActive ? 1.1 : 1 }}
                transition={{ type: 'spring', stiffness: 400 }}
                className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center"
              >
                <Upload className="w-6 h-6 text-gray-400" />
              </motion.div>
              <div>
                <p className="font-semibold text-gray-700 text-[15px]">
                  {isDragActive ? 'Release to upload' : 'Drop an artifact here'}
                </p>
                <p className="text-[13px] text-gray-400 mt-0.5">
                  or choose a file from your device
                </p>
              </div>
              <p className="text-[11px] text-gray-300 tracking-widest uppercase font-medium">
                PNG · JPG · WEBP · MP4
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Action buttons */}
      <div className="mt-4 flex flex-col sm:flex-row items-center gap-3">
        <motion.button
          onClick={handleVerify}
          disabled={!staged || isLoading}
          whileTap={{ scale: staged && !isLoading ? 0.97 : 1 }}
          className={`
            flex-1 w-full sm:w-auto flex items-center justify-center gap-2
            h-11 px-6 rounded-xl font-semibold text-[14px] tracking-wide
            transition-all duration-200
            ${staged && !isLoading
              ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-200'
              : 'bg-gray-100 text-gray-300 cursor-not-allowed'
            }
          `}
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          VERIFY PROVENANCE
        </motion.button>

        <button
          onClick={handleDemoClick}
          disabled={isLoading}
          className="text-[13px] font-medium text-blue-600 hover:text-blue-700 hover:underline underline-offset-2 transition-all whitespace-nowrap disabled:opacity-40"
        >
          Try Demo Artifact
        </button>
      </div>

      {/* Dev toggle */}
      <div className="mt-5 flex items-center justify-center gap-2 flex-wrap">
        <span className="text-[11px] font-medium text-gray-300 uppercase tracking-widest">
          Demo mode
        </span>
        {MOCK_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onMockModeChange(opt.value)}
            className={`
              text-[11px] font-medium px-2.5 py-1 rounded-full border transition-all
              ${mockMode === opt.value
                ? `border-current bg-current/10 ${opt.color}`
                : 'border-gray-200 text-gray-300 hover:border-gray-300 hover:text-gray-400'
              }
            `}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </section>
  );
}
