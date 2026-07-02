import { motion } from "motion/react";
import { type PropsWithChildren } from "react";

import { TopNavigation } from "./TopNavigation";

type LearningSpaceShellProps = PropsWithChildren<{
  hideTopNavigation?: boolean;
}>;

export function LearningSpaceShell({ children, hideTopNavigation = false }: LearningSpaceShellProps) {
  return (
    <div className="app-surface">
      <div className="ambient-layer" aria-hidden="true" />
      {hideTopNavigation ? null : <TopNavigation />}
      <motion.main
        className={hideTopNavigation ? "learning-shell edge-shell" : "learning-shell"}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.main>
    </div>
  );
}
