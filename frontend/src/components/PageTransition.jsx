import { motion } from "motion/react";

const variants = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.18 } },
};

export default function PageTransition({ children, className = "" }) {
  return (
    <motion.main
      id="main"
      className={`page ${className}`}
      variants={variants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {children}
    </motion.main>
  );
}