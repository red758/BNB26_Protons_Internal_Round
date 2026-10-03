'use client';

import { motion } from 'framer-motion';

const STEPS = [
  'HASHING ARTIFACT',
  'CHECKING PROVENANCE',
  'VALIDATING CHAIN',
  'RESULT',
];

interface VerifyingStateProps {
  currentStep: number;
}

export default function VerifyingState({ currentStep }: VerifyingStateProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="w-full max-w-sm mx-auto"
    >
      <div className="bg-white rounded-2xl border border-black/[0.07] shadow-sm p-8 flex flex-col items-center gap-6">
        <div className="relative w-14 h-14">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 56 56">
            <circle
              cx="28"
              cy="28"
              r="22"
              fill="none"
              stroke="#f1f5f9"
              strokeWidth="4"
            />
            <motion.circle
              cx="28"
              cy="28"
              r="22"
              fill="none"
              stroke="#3b82f6"
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={138.2}
              animate={{ strokeDashoffset: [138.2, 0] }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-blue-500" />
          </div>
        </div>

        <div className="w-full space-y-2">
          {STEPS.map((step, i) => {
            const isDone = i < currentStep;
            const isActive = i === currentStep;
            return (
              <motion.div
                key={step}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.12 }}
                className={`
                  flex items-center gap-3 px-3 py-2 rounded-lg transition-all
                  ${isActive ? 'bg-blue-50' : ''}
                `}
              >
                <div
                  className={`
                    w-1.5 h-1.5 rounded-full flex-shrink-0 transition-colors
                    ${isDone  ? 'bg-emerald-400' : ''}
                    ${isActive ? 'bg-blue-500 animate-pulse' : ''}
                    ${!isDone && !isActive ? 'bg-gray-200' : ''}
                  `}
                />
                <span
                  className={`
                    text-[12px] font-semibold tracking-wider transition-colors
                    ${isDone   ? 'text-emerald-500 line-through decoration-emerald-300' : ''}
                    ${isActive ? 'text-blue-600' : ''}
                    ${!isDone && !isActive ? 'text-gray-300' : ''}
                  `}
                >
                  {step}
                </span>
              </motion.div>
            );
          })}
        </div>
      </div>
    </motion.section>
  );
}
