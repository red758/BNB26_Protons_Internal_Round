'use client';

import Link from 'next/link';

export default function Navbar() {
  return (
    <header className="fixed top-0 inset-x-0 z-50 h-14">
      {/* Glass backdrop */}
      <div className="absolute inset-0 bg-white/80 backdrop-blur-xl border-b border-black/[0.06]" />

      <nav className="relative h-full max-w-6xl mx-auto px-6 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          {/* Abstract P + chain icon */}
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center shadow-sm group-hover:bg-blue-700 transition-colors">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-white">
              <path
                d="M4 3h5.5a2.5 2.5 0 0 1 0 5H4"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
              <path
                d="M4 3v10"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
              <circle cx="4" cy="13" r="0.8" fill="currentColor" />
              <circle cx="7" cy="13" r="0.8" fill="currentColor" opacity="0.6" />
              <circle cx="10" cy="13" r="0.8" fill="currentColor" opacity="0.35" />
            </svg>
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-gray-900 select-none">
            ProvLedger
          </span>
        </Link>

        {/* Center nav */}
        <div className="hidden sm:flex items-center gap-1">
          <Link
            href="/verify"
            className="px-3 py-1.5 text-[14px] font-medium text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-all duration-150"
          >
            Verify
          </Link>
          <Link
            href="/register"
            className="px-3 py-1.5 text-[14px] font-medium text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-all duration-150"
          >
            Register
          </Link>
        </div>

        {/* System status */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <span className="text-[11px] font-semibold tracking-widest text-emerald-700 uppercase">
            ΓùÅ SYSTEM ONLINE
          </span>
        </div>
      </nav>
    </header>
  );
}
