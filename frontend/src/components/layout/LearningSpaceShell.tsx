import { motion } from "motion/react";
import { type PropsWithChildren } from "react";

import { TopNavigation } from "./TopNavigation";

export function LearningSpaceShell({ children }: PropsWithChildren) {
  return (
    <div className="app-surface">
      <div className="ambient-layer" aria-hidden="true" />
      <TopNavigation />
      <motion.main
        className="learning-shell"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.main>
    </div>
  );
}
