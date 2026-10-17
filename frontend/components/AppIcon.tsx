import type { CSSProperties } from "react";

export type AppIconName = "overview" | "systems" | "investigations" | "assistant" | "knowledge" | "simulator";

export function AppIcon({ name, size = 18, className = "" }: { name: AppIconName; size?: number; className?: string }) {
  const source = `/icons/freeicons/${name}.png`;
  const style: CSSProperties = {
    width: size,
    height: size,
    backgroundColor: "currentColor",
    WebkitMaskImage: `url(${source})`,
    maskImage: `url(${source})`,
    WebkitMaskPosition: "center",
    maskPosition: "center",
    WebkitMaskRepeat: "no-repeat",
    maskRepeat: "no-repeat",
    WebkitMaskSize: "contain",
    maskSize: "contain",
  };

  return <span aria-hidden="true" className={`inline-block shrink-0 ${className}`} style={style} />;
}
