import { motion } from "motion/react";
import { type PropsWithChildren } from "react";

import { TopNavigation } from "./TopNavigation";

type LearningSpaceShellProps = PropsWithChildren<{
  hideTopNavigation?: boolean;
  mainClassName?: string;
  surfaceClassName?: string;
}>;

export function LearningSpaceShell({
  children,
  hideTopNavigation = false,
  mainClassName,
  surfaceClassName
}: LearningSpaceShellProps) {
  const surfaceClasses = [hideTopNavigation ? "app-surface edge-app-surface" : "app-surface", surfaceClassName]
    .filter(Boolean)
    .join(" ");
  const mainClasses = [hideTopNavigation ? "learning-shell edge-shell" : "learning-shell", mainClassName]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={surfaceClasses}>
      <div className="ambient-layer" aria-hidden="true" />
      {hideTopNavigation ? null : <TopNavigation />}
      <motion.main
        className={mainClasses}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.main>
    </div>
  );
}
