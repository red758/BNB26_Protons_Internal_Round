import React from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  className = "",
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="block text-xs font-medium text-neutral-300">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full px-3.5 py-2.5 bg-neutral-900/80 border ${
          error ? "border-red-500/80 focus:border-red-500 focus:ring-red-500/20" : "border-neutral-800 focus:border-blue-500 focus:ring-blue-500/20"
        } rounded-lg text-sm text-white placeholder-neutral-500 transition-all focus:outline-none focus:ring-2 disabled:opacity-50 ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
      {helperText && !error && <p className="text-xs text-neutral-500 mt-1">{helperText}</p>}
    </div>
  );
};
