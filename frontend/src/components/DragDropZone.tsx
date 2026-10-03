'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  File as FileIcon,
  Video,
  Loader2,
  ChevronRight,
  ShieldCheck,
  ShieldAlert,
  Lock,
  SlidersHorizontal,
  AlertTriangle,
  Clapperboard,
} from 'lucide-react';
import type { MockMode } from '@/services/client';

interface DragDropZoneProps {
  onVerify: (file: File) => void;
  isLoading: boolean;
  mockMode: MockMode;
  onMockModeChange: (mode: MockMode) => void;
}

const MOCK_OPTIONS: { value: MockMode; label: string; icon: any; color: string; desc: string }[] = [
  { value: 'live',        label: 'Live (Auto)',       icon: SlidersHorizontal, color: 'text-gray-600',   desc: 'Calls real backend / local API' },
  { value: 'verified',    label: 'Verified',          icon: ShieldCheck,       color: 'text-emerald-600', desc: 'High-trust verified image' },
  { value: 'video',       label: 'Video Verified',    icon: Clapperboard,      color: 'text-blue-600',    desc: 'Full video provenance chain' },
  { value: 'transformed', label: 'Transformed',       icon: SlidersHorizontal, color: 'text-violet-600',  desc: 'Transformation & Multi-System' },
  { value: 'tampered',    label: 'Adversarial',       icon: ShieldAlert,       color: 'text-red-600',     desc: 'Tamper detection scenario' },
  { value: 'privacy',     label: 'Privacy Shielded',  icon: Lock,              color: 'text-blue-600',    desc: 'Zero-knowledge provenance' },
  { value: 'unregistered',label: 'No Record',         icon: AlertTriangle,     color: 'text-amber-600',   desc: 'Unregistered artifact' },
];

const ACCEPTED_TYPES = {
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/webp': ['.webp'],
  'image/gif': ['.gif'],
  'video/mp4': ['.mp4'],
  'video/webm': ['.webm'],
  'video/quicktime': ['.mov'],
  'video/x-msvideo': ['.avi'],
};

function isVideoFile(file: File) {
  return file.type.startsWith('video/');
}

export default function DragDropZone({
  onVerify,
  isLoading,
  mockMode,
  onMockModeChange,
}: DragDropZoneProps) {
  const [staged, setStaged] = useState<File | null>(null);
  const [videoThumbUrl, setVideoThumbUrl] = useState<string | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    const file = accepted[0];
    if (!file) return;
    setStaged(file);

    // Generate preview URL for video thumbnail
    if (isVideoFile(file)) {
      const url = URL.createObjectURL(file);
      setVideoThumbUrl(url);
    } else {
      if (videoThumbUrl) URL.revokeObjectURL(videoThumbUrl);
      setVideoThumbUrl(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxFiles: 1,
    disabled: isLoading,
  });

  const handleVerify = () => {
    if (staged) onVerify(staged);
  };

  const handleDemoClick = () => {
    // Use video demo if video mode selected
    const isVideoMode = mockMode === 'video';
    const fileName = isVideoMode ? 'ai-generated-cinematic.mp4' : 'ai-generated-landscape.png';
    const fileType = isVideoMode ? 'video/mp4' : 'image/png';
    const demoFile = new globalThis.File(['demo artifact content'], fileName, { type: fileType });
    onVerify(demoFile);
  };

  const stagedIsVideo = staged ? isVideoFile(staged) : false;

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
        className="relative cursor-pointer rounded-2xl border-2 border-dashed p-10 sm:p-14 text-center backdrop-blur-xl"
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
              {/* Video mini-preview OR icon */}
              {stagedIsVideo && videoThumbUrl ? (
                <div className="w-24 h-14 rounded-xl overflow-hidden bg-black/10 relative shadow-sm">
                  <video
                    src={videoThumbUrl}
                    className="w-full h-full object-cover"
                    muted
                    playsInline
                  />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30 rounded-xl">
                    <Video className="w-4 h-4 text-white" />
                  </div>
                </div>
              ) : (
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${stagedIsVideo ? 'bg-blue-100' : 'bg-blue-100'}`}>
                  {stagedIsVideo ? (
                    <Video className="w-6 h-6 text-blue-600" />
                  ) : (
                    <FileIcon className="w-6 h-6 text-blue-600" />
                  )}
                </div>
              )}
              <div>
                <p className="font-semibold text-gray-900 text-[15px]">{staged.name}</p>
                <p className="text-[13px] text-gray-400 mt-0.5">
                  {(staged.size / 1048576).toFixed(2)} MB
                  {stagedIsVideo && (
                    <span className="ml-2 px-1.5 py-0.5 text-[10px] rounded bg-blue-100 text-blue-700 font-semibold">
                      VIDEO
                    </span>
                  )}
                  <span className="ml-1">┬╖ Click to replace</span>
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
              <div className="flex flex-col items-center gap-1">
                <p className="text-[11px] text-gray-300 tracking-widest uppercase font-medium">
                  PNG ┬╖ JPG ┬╖ WEBP ┬╖ GIF
                </p>
                <div className="flex items-center gap-1.5">
                  <Video className="w-3 h-3 text-blue-400" />
                  <p className="text-[11px] text-blue-400 tracking-widest uppercase font-medium">
                    MP4 ┬╖ MOV ┬╖ WEBM ┬╖ AVI
                  </p>
                </div>
              </div>
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
            h-11 px-6 rounded-xl font-semibold text-[14px] tracking-wide transition-all duration-200
            ${staged && !isLoading
              ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-200'
              : 'bg-gray-100 text-gray-300 cursor-not-allowed'}
          `}
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : stagedIsVideo ? (
            <Video className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          {stagedIsVideo ? 'VERIFY VIDEO PROVENANCE' : 'VERIFY PROVENANCE'}
        </motion.button>

        <button
          onClick={handleDemoClick}
          disabled={isLoading}
          className="text-[13px] font-medium text-blue-600 hover:text-blue-700 hover:underline underline-offset-2 transition-all whitespace-nowrap disabled:opacity-40"
        >
          Try Demo {mockMode === 'video' ? 'Video' : 'Artifact'}
        </button>
      </div>

      {/* Feature Demo Scenario Selector */}
      <div className="mt-6 pt-5 border-t border-black/[0.06]">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">
            FEATURE DEMO SCENARIOS
          </span>
          <span className="text-[11px] text-gray-400 font-medium">
            Simulates Backend Responses
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {MOCK_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const isSelected = mockMode === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => onMockModeChange(opt.value)}
                title={opt.desc}
                className={`
                  flex items-center gap-2 px-3 py-2 rounded-xl text-left border transition-all text-xs font-medium
                  ${isSelected
                    ? `border-blue-500/50 bg-blue-50/80 shadow-sm ${opt.color}`
                    : 'border-gray-200/80 bg-white/50 text-gray-600 hover:bg-white hover:border-gray-300'}
                `}
              >
                <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${isSelected ? opt.color : 'text-gray-400'}`} />
                <span className="truncate">{opt.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
