export function Mark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden="true"
    >
      <path d="M31 9H52L29 36H48L32 55H10L33 28H15L31 9Z" fill="currentColor" />
      <path d="M29 36H48L32 55H10L29 36Z" fill="white" opacity=".23" />
      <path d="M33 28L29 36H21L33 28Z" fill="#0a4656" opacity=".6" />
    </svg>
  );
}
export function Orbital() {
  return (
    <div className="orbital" aria-hidden="true">
      <div className="orbital-glow" />
      <div className="orbit orbit-one" />
      <div className="orbit orbit-two" />
      <div className="orbit orbit-three" />
      <div className="core">
        <Mark />
      </div>
      <span className="orbit-dot dot-one" />
      <span className="orbit-dot dot-two" />
      <span className="orbit-caption caption-one">SIGNAL FOUND</span>
      <span className="orbit-caption caption-two">YOUR NEXT CHAPTER ↗</span>
      <div className="orbital-floor" />
    </div>
  );
}
