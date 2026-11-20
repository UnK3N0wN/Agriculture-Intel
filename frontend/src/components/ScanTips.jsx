import Icon from "./Icon.jsx";

const TIPS = [
  { icon: "leaf", text: "Photograph one affected leaf, filling most of the frame." },
  { icon: "camera", text: "Use daylight. Avoid harsh shadows and flash." },
  { icon: "search", text: "Keep the leaf in focus and hold the phone steady." },
  { icon: "alert", text: "Include both healthy and spotted areas if you can." },
];

export default function ScanTips() {
  return (
    <aside className="card tips" aria-label="Photo tips">
      <h3>Tips for a better result</h3>
      <ul>
        {TIPS.map((tip) => (
          <li key={tip.text}>
            <Icon name={tip.icon} size={18} />
            <span>{tip.text}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}