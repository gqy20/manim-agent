interface LogoProps {
  size?: number;
  className?: string;
}

/**
 * Manim Agent logo — abstract geometric mark representing
 * math visualization + animation motion.
 */
export function Logo({ size = 32, className = "" }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Background circle */}
      <circle cx="18" cy="18" r="17" stroke="currentColor" strokeWidth="1.2" opacity="0.15" />

      {/* Animated arc — represents motion / rendering */}
      <path
        d="M8 24 C 8 14, 14 6, 26 10"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
        opacity="0.9"
      />

      {/* Triangle / play geometry — core math shape */}
      <path
        d="M12 22 L 22 16 L 18 9 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
        fill="currentColor"
        opacity="0.85"
      />

      {/* Dot — focal point */}
      <circle cx="25" cy="11" r="2.2" fill="currentColor" opacity="0.7" />
    </svg>
  );
}
