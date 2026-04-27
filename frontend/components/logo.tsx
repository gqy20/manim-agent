interface LogoProps {
  size?: number;
  className?: string;
}

/**
 * Manim Agent logo: a compact compass/play mark for math animation.
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
      aria-hidden="true"
    >
      <circle cx="18" cy="18" r="16.5" stroke="currentColor" strokeWidth="1" opacity="0.18" />
      <circle cx="18" cy="18" r="11.5" stroke="currentColor" strokeWidth="0.7" opacity="0.1" />
      <path
        d="M8.5 24.5 C 8.5 14.5, 15 6.8, 26.5 10.2"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
        fill="none"
        opacity="0.9"
      />
      <path
        d="M12.2 23.4 L 23.6 15.7 L 17.6 8.8 Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
        fill="currentColor"
        opacity="0.88"
      />
      <path
        d="M18 4.8 V7.2 M18 28.8 V31.2 M4.8 18 H7.2 M28.8 18 H31.2"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.32"
      />
      <circle cx="26.1" cy="10.5" r="2.1" fill="currentColor" opacity="0.76" />
    </svg>
  );
}
