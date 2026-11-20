import { motion } from "motion/react";
import PageTransition from "./PageTransition.jsx";
import Icon from "./Icon.jsx";

const LEAVES = [
  { size: 96, left: "10%", top: "14%", rotate: 18, duration: 6 },
  { size: 64, left: "68%", top: "26%", rotate: -24, duration: 7.5 },
  { size: 120, left: "38%", top: "58%", rotate: 8, duration: 8.5 },
  { size: 52, left: "80%", top: "72%", rotate: 40, duration: 6.5 },
];

const BENEFITS = ["Crops matched to your climate and season", "Leaf photo diagnosis in seconds", "Organic and chemical treatment options"];

export default function AuthLayout({ title, subtitle, children }) {
  return (
    <PageTransition className="auth-page">
      <div className="auth-hero" aria-hidden="false">
        {LEAVES.map((leaf, index) => (
          <motion.div
            key={index}
            className="float-leaf"
            style={{ left: leaf.left, top: leaf.top, rotate: leaf.rotate }}
            animate={{ y: [0, -16, 0], rotate: [leaf.rotate, leaf.rotate + 10, leaf.rotate] }}
            transition={{ duration: leaf.duration, repeat: Infinity, ease: "easeInOut" }}
          >
            <Icon name="leaf" size={leaf.size} strokeWidth={1.2} />
          </motion.div>
        ))}
        <div className="auth-hero-text">
          <span className="brand-mark brand-mark-lg">
            <Icon name="leaf" size={28} />
          </span>
          <h1>AgriIntel</h1>
          <p>Grow with confidence. Know what to plant and catch problems early.</p>
          <ul>
            {BENEFITS.map((text, i) => (
              <motion.li key={text} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.12 }}>
                <Icon name="check" size={16} /> {text}
              </motion.li>
            ))}
          </ul>
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-card">
          <h2>{title}</h2>
          <p className="muted">{subtitle}</p>
          {children}
        </div>
      </div>
    </PageTransition>
  );
}