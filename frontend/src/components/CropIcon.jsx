const BY_SLUG = { maize: "🌽", tomato: "🍅", potato: "🥔", onion: "🧅", groundnut: "🥜", rice: "🌾", wheat: "🌾" };
const BY_CATEGORY = {
  cereal: "🌾", pulse: "🫘", vegetable: "🥬", fruit: "🍎", oilseed: "🌻", fibre: "🧵", spice: "🌶️", other: "🌱",
};

export default function CropIcon({ slug, category, size = 46 }) {
  return (
    <span
      className={`crop-icon cat-${category}`}
      style={{ width: size, height: size, fontSize: size * 0.55 }}
      aria-hidden="true"
    >
      {BY_SLUG[slug] || BY_CATEGORY[category] || "🌱"}
    </span>
  );
}