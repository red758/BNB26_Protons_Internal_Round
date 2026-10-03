'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  CheckCircle2,
  Cpu,
  ArrowDown,
  Layers,
  Sliders,
  ShieldCheck,
  Video,
  Play,
  Clock,
  Monitor,
  Clapperboard,
} from 'lucide-react';
import type { VerificationResult, HistoryEvent } from '@/services/client';
import { formatTimestamp, truncateHash } from '@/services/client';

interface LineageTreeProps {
  result: VerificationResult;
  artifactPreviewUrl?: string;
}

const ACTION_COLORS: Record<string, { dot: string; badge: string }> = {
  GENERATED:                { dot: 'bg-blue-500',    badge: 'bg-blue-100 text-blue-700' },
  TRANSFORMED:              { dot: 'bg-violet-500',  badge: 'bg-violet-100 text-violet-700' },
  'RE-ENCODED':             { dot: 'bg-violet-500',  badge: 'bg-violet-100 text-violet-700' },
  'CLAIMED GENERATION':     { dot: 'bg-orange-400',  badge: 'bg-orange-100 text-orange-700' },
  'UNAUTHORIZED MODIFICATION': { dot: 'bg-red-500',  badge: 'bg-red-100 text-red-700' },
  'GENERATED (ZERO-KNOWLEDGE)': { dot: 'bg-blue-500', badge: 'bg-blue-100 text-blue-700' },
  CURRENT:                  { dot: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700' },
};

function getColors(action: string) {
  return ACTION_COLORS[action] || ACTION_COLORS[action.toUpperCase()] || { dot: 'bg-gray-400', badge: 'bg-gray-100 text-gray-600' };
}

export default function LineageTree({ result, artifactPreviewUrl }: LineageTreeProps) {
  const { history, artifact, status, multi_system, transformation } = result;
  const isVideo = artifact.kind === 'video';
  const vm = artifact.video_metadata;

  return (
    <section
      id="provenance"
      className="w-full max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6"
    >
      {/* LEFT: Artifact Preview */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="flex flex-col gap-4"
      >
        <div className="flex items-center justify-between">
          <SectionLabel>ARTIFACT INSPECTION</SectionLabel>
          {isVideo && (
            <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200">
              <Video className="w-2.5 h-2.5" /> VIDEO
            </span>
          )}
        </div>

        {/* Preview container */}
        <div
          className={`
            relative bg-black/5 rounded-2xl border border-black/[0.07] shadow-sm overflow-hidden
            ${isVideo ? 'aspect-video' : 'aspect-square sm:aspect-[4/3]'}
          `}
        >
          {artifactPreviewUrl ? (
            isVideo ? (
              <VideoPlayer src={artifactPreviewUrl} />
            ) : (
              <img
                src={artifactPreviewUrl}
                alt={artifact.name}
                className="w-full h-full object-contain bg-white"
              />
            )
          ) : (
            <NoPreview isVideo={isVideo} />
          )}
        </div>

        {/* Metadata card */}
        <div className="bg-white rounded-xl border border-black/[0.07] p-4 space-y-2.5">
          <MetaRow label="Filename" value={artifact.name} />
          <MetaRow label="Size"     value={artifact.size} />
          <MetaRow label="Type"     value={artifact.type} />

          {/* Video-specific metadata rows */}
          {isVideo && vm && (
            <>
              {vm.duration && <MetaRow label="Duration"   value={vm.duration} />}
              {vm.resolution && <MetaRow label="Resolution" value={vm.resolution} />}
              {vm.fps && <MetaRow label="Frame Rate"  value={vm.fps} />}
              {vm.codec && <MetaRow label="Codec"       value={vm.codec} />}
              {vm.frame_count && (
                <MetaRow label="Frames" value={`${vm.frame_count.toLocaleString()} frames`} />
              )}
            </>
          )}

          {/* Transformation type */}
          {transformation?.transformation_type && (
            <MetaRow label="Transform" value={transformation.transformation_type} />
          )}

          {/* SHA-256 hash */}
          <div className="pt-1 border-t border-gray-100">
            <p className="text-[10px] font-semibold tracking-[0.12em] uppercase text-gray-400 mb-1">
              {isVideo ? 'SHA-256 (Full File)' : 'SHA-256'}
            </p>
            <p className="text-[11px] font-mono text-gray-600 break-all leading-relaxed">
              {artifact.hash}
            </p>
          </div>

          {/* Key-frame sampling note for video */}
          {isVideo && vm?.sampling_strategy && (
            <div className="flex items-start gap-2 pt-1 border-t border-gray-100">
              <Clapperboard className="w-3 h-3 text-blue-400 mt-0.5 flex-shrink-0" />
              <p className="text-[11px] text-blue-600 leading-snug">
                {vm.sampling_strategy}
              </p>
            </div>
          )}
        </div>
      </motion.div>

      {/* RIGHT: Lineage Tree */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: 0.08 }}
        className="flex flex-col gap-4"
      >
        <div className="flex items-center justify-between">
          <SectionLabel>
            {isVideo ? 'VIDEO PROVENANCE LINEAGE' : 'MULTI-SYSTEM PROVENANCE LINEAGE'}
          </SectionLabel>
          {multi_system?.systems_count > 0 && (
            <span className="text-[11px] font-semibold text-blue-600 flex items-center gap-1">
              <Layers className="w-3 h-3" /> {multi_system.systems_count} AI Engines
            </span>
          )}
        </div>

        {history.length === 0 ? (
          <div className="flex-1 flex items-center justify-center py-16 text-center">
            <div>
              <p className="text-[13px] font-medium text-gray-400">No provenance history available.</p>
              <p className="text-[12px] text-gray-300 mt-1">Register this artifact to begin tracking.</p>
            </div>
          </div>
        ) : (
          <div className="relative">
            {/* Vertical connector */}
            <div className="absolute left-[19px] top-5 bottom-5 w-px bg-gradient-to-b from-gray-200 via-gray-200 to-transparent" />

            <div className="space-y-1">
              {history.map((event, i) => (
                <TimelineEvent
                  key={i}
                  event={event}
                  index={i}
                  isLast={i === history.length - 1}
                  isVideo={isVideo}
                />
              ))}
            </div>

            {/* Chain validity badge */}
            {result.chain_valid && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                className="mt-4 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-50 border border-emerald-100"
              >
                <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                <span className="text-[12px] font-semibold text-emerald-700 tracking-wide">
                  {isVideo
                    ? 'Γ£ô VIDEO PROVENANCE CHAIN VERIFIED'
                    : 'Γ£ô MULTI-SYSTEM CHAIN INTEGRITY VERIFIED'}
                </span>
              </motion.div>
            )}
          </div>
        )}
      </motion.div>
    </section>
  );
}

// ΓöÇΓöÇ Sub-components ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

function VideoPlayer({ src }: { src: string }) {
  const [playing, setPlaying] = useState(false);
  return (
    <div className="relative w-full h-full bg-black group">
      <video
        src={src}
        className="w-full h-full object-contain"
        controls
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />
      {/* Overlay badge */}
      {!playing && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
            <Play className="w-5 h-5 text-white fill-white ml-0.5" />
          </div>
        </div>
      )}
    </div>
  );
}

function NoPreview({ isVideo }: { isVideo: boolean }) {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center gap-3 text-gray-300">
      {isVideo ? (
        <>
          <Video className="w-12 h-12" />
          <span className="text-[13px] font-medium">Video preview unavailable</span>
        </>
      ) : (
        <>
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <rect x="6" y="6" width="36" height="36" rx="8" stroke="currentColor" strokeWidth="2" />
            <circle cx="18" cy="19" r="3.5" stroke="currentColor" strokeWidth="1.8" />
            <path d="M6 32 L16 22 L24 30 L32 21 L42 32" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
          </svg>
          <span className="text-[13px] font-medium">Preview unavailable</span>
        </>
      )}
    </div>
  );
}

function TimelineEvent({
  event,
  index,
  isLast,
  isVideo,
}: {
  event: HistoryEvent;
  index: number;
  isLast: boolean;
  isVideo: boolean;
}) {
  const colors = getColors(event.action);

  return (
    <motion.div
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.15 + index * 0.1, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="relative flex gap-4 group"
    >
      {/* Dot */}
      <div className="relative flex-shrink-0 flex flex-col items-center">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2 + index * 0.1, type: 'spring', stiffness: 500 }}
          className={`w-10 h-10 rounded-full border-2 border-white shadow-sm flex items-center justify-center z-10 ${colors.dot}`}
        >
          {event.action.toUpperCase().includes('CURRENT') ? (
            <CheckCircle2 className="w-4 h-4 text-white" />
          ) : isVideo ? (
            <Clapperboard className="w-4 h-4 text-white opacity-90" />
          ) : (
            <Cpu className="w-4 h-4 text-white opacity-80" />
          )}
        </motion.div>
        {!isLast && (
          <div className="flex-1 flex items-center justify-center mt-1 mb-1">
            <ArrowDown className="w-3 h-3 text-gray-300" />
          </div>
        )}
      </div>

      {/* Card */}
      <div className="flex-1 bg-white rounded-xl border border-black/[0.06] shadow-sm p-4 mb-3 group-last:mb-0">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <span className={`inline-block text-[10px] font-bold tracking-[0.12em] uppercase px-2 py-0.5 rounded-full ${colors.badge}`}>
              ΓùÅ {event.action}
            </span>
            <p className="mt-1 text-[13px] font-semibold text-gray-800">{event.model}</p>
            {event.system_app && (
              <p className="text-[11px] text-gray-400">System: {event.system_app}</p>
            )}
          </div>
          <p className="text-[11px] text-gray-400 whitespace-nowrap text-right leading-tight">
            {formatTimestamp(event.timestamp)}
          </p>
        </div>

        {/* Perceptual distance for transformations */}
        {event.perceptual_distance !== undefined && (
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-violet-700 bg-violet-50 p-1.5 rounded-lg border border-violet-100">
            <Sliders className="w-3 h-3 flex-shrink-0" />
            <span>
              Perceptual Distance: {event.perceptual_distance}{' '}
              {isVideo ? 'bits (Video Frame Hash Delta)' : 'bits (Preserved)'}
            </span>
          </div>
        )}

        {/* Hashes */}
        <div className="space-y-1.5">
          {event.parent_hash && <HashRow label="Parent" hash={event.parent_hash} />}
          <HashRow
            label={event.action.includes('CURRENT') ? 'Hash' : 'New Hash'}
            hash={event.hash}
          />
        </div>
      </div>
    </motion.div>
  );
}

function HashRow({ label, hash }: { label: string; hash: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-[0.1em] w-14 flex-shrink-0">
        {label}
      </span>
      <span className="text-[11px] font-mono text-gray-500 truncate">
        {truncateHash(hash, 10)}
      </span>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-gray-400 flex-shrink-0">
        {label}
      </span>
      <span className="text-[13px] text-gray-700 text-right truncate max-w-[60%]">{value}</span>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-bold tracking-[0.2em] uppercase text-gray-400">{children}</p>
  );
}
