// Alice swarm logo: the stigmergic ant (replaces the DeepSeek whale mark).
// Side-profile ant — three filled body segments (abdomen, thorax, head) plus
// one stroked path for legs and antennae. Rendered square; color rides
// currentColor (brand ink).

import type { IconProps } from './icons/props.ts'

/**
 * Render the ant logo, the stigmergic brand mark.
 * @param props.size - width in px (default 24; height equals width).
 * @param props.className - extra class for layout placement.
 * @returns the logo svg (aria-hidden; pair with the wordmark for accessibility).
 */
export function AntLogo({ size = 24, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <ellipse cx="6.2" cy="14.4" rx="4.1" ry="3.3" fill="currentColor" />
      <ellipse cx="12.1" cy="11.8" rx="2" ry="1.7" fill="currentColor" />
      <circle cx="17.2" cy="9.4" r="2.2" fill="currentColor" />
      <path
        d="M18.4 7.6C19.6 5.6 21.2 4.6 23 4.4M16.6 7.2C16 5.4 16.1 3.4 17 1.9M13.2 12.8L16 15.2L17.4 18.6M11.9 13.4L11.3 16.6L12.1 19.8M10.7 13L7.9 15.6L6.3 19"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}