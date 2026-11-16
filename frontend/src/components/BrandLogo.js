import Image from "next/image";

export default function BrandLogo({ size = 60, className = "", priority = false }) {
  return (
    <span
      className={`brand-logo ${className}`.trim()}
      style={{ "--brand-logo-size": `${size}px` }}
      role="img"
      aria-label="AVSAR"
    >
      <Image className="brand-logo-light" src="/avsar-logo-light.png" alt="" width={size} height={size} priority={priority} />
      <Image className="brand-logo-dark" src="/avsar-logo-dark.png" alt="" width={size} height={size} priority={priority} />
    </span>
  );
}
