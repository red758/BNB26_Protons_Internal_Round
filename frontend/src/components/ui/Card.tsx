import React from "react";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  gradient?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = "",
  gradient = false,
}) => {
  return (
    <div
      className={`rounded-2xl border ${
        gradient
          ? "bg-gradient-to-b from-neutral-900/90 to-neutral-950/90 border-neutral-800/80 shadow-2xl backdrop-blur-xl"
          : "bg-neutral-900/60 border-neutral-800/60 backdrop-blur-lg"
      } p-6 transition-all duration-300 hover:border-neutral-700/80 ${className}`}
    >
      {children}
    </div>
  );
};
