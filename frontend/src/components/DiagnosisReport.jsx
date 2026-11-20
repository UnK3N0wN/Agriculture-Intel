import { motion } from "motion/react";
import { scoreTone } from "../lib/utils.js";
import AuthedImage from "./AuthedImage.jsx";
import Icon from "./Icon.jsx";
import { ScoreRing } from "./Meters.jsx";

const container = { hidden: {}, show: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } } };
const rise = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

const PATHOGEN_LABELS = {
  fungal: "Fungal disease",
  bacterial: "Bacterial disease",
  viral: "Viral disease",
  pest: "Pest",
  nutrient: "Nutrient deficiency",
};

function Section({ title, icon, items, className = "" }) {
  if (!items || !items.length) return null;
  return (
    <motion.section variants={rise} className={`report-section ${className}`}>
      <h3>
        <Icon name={icon} size={18} /> {title}
      </h3>
      <ul>
        {items.map((text, index) => (
          <li key={index}>{text}</li>
        ))}
      </ul>
    </motion.section>
  );
}

export default function DiagnosisReport({ diagnosis, imageSrc, split = true }) {
  const confidence = Math.round((diagnosis.confidence ?? 0) * 100);
  const status = diagnosis.health_status;
  const lowConfidence = status === "unknown" || confidence < 50;
  const title =
    diagnosis.common_name || (status === "healthy" ? "Healthy leaf" : "We couldn't identify a problem");

  return (
    <motion.article className={`report ${split ? "report-split" : ""}`} variants={container} initial="hidden" animate="show">
      <motion.div className="report-visual" variants={rise}>
        {imageSrc ? (
          <img src={imageSrc} alt="Your scanned leaf" />
        ) : (
          <AuthedImage src={diagnosis.image_url} alt="Your scanned leaf" />
        )}
        <span className={`badge badge-${status}`}>
          {status === "healthy" ? "Healthy" : status === "unhealthy" ? "Needs attention" : "Unclear"}
        </span>
      </motion.div>

      <div className="report-body">
        <motion.header variants={rise}>
          <h2>{title}</h2>
          {diagnosis.scientific_name && <p className="muted"><em>{diagnosis.scientific_name}</em></p>}
          {PATHOGEN_LABELS[diagnosis.pathogen_type] && <span className="pill">{PATHOGEN_LABELS[diagnosis.pathogen_type]}</span>}
        </motion.header>

        <motion.div variants={rise} className="confidence-row">
          <ScoreRing value={confidence} size={92} stroke={10} caption="confidence" tone={scoreTone(confidence)} />
          <p className="muted">
            {confidence >= 80
              ? "High confidence. Still check the symptoms against your plant."
              : confidence >= 50
                ? "Moderate confidence. Compare the symptoms below before treating."
                : "Low confidence. Treat this as a guess."}
          </p>
        </motion.div>

        {lowConfidence && (
          <motion.div variants={rise} className="notice" role="note">
            <Icon name="alert" size={18} />
            <p>
              For a better result, take a sharp, well-lit photo of one affected leaf filling most of the frame, or
              ask your local agricultural extension officer.
            </p>
          </motion.div>
        )}

        <Section title="Symptoms" icon="alert" items={diagnosis.symptoms} />
        <Section title="Organic treatment" icon="leaf" items={diagnosis.organic_treatment} className="organic" />
        <Section title="Chemical treatment" icon="flask" items={diagnosis.chemical_treatment} className="chemical" />
        <Section title="Prevention" icon="shield" items={diagnosis.prevention} />

        {diagnosis.chemical_treatment?.length > 0 && (
          <motion.p variants={rise} className="fine-print">
            Always follow the product label and local regulations for any chemical, and wear protective equipment.
          </motion.p>
        )}
        <motion.p variants={rise} className="fine-print">
          AI diagnoses can be wrong. This is guidance, not a substitute for an agronomist.
        </motion.p>
      </div>
    </motion.article>
  );
}