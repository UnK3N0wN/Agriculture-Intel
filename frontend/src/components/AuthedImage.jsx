import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { fetchImageObjectUrl } from "../api.js";
import Icon from "./Icon.jsx";

export default function AuthedImage({ src, alt, className = "" }) {
  const [url, setUrl] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setUrl(null);
    setFailed(false);
    if (!src) return undefined;
    fetchImageObjectUrl(src)
      .then((objectUrl) => alive && setUrl(objectUrl))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [src]);

  if (failed || !src) {
    return (
      <div className={`img-fallback ${className}`} role="img" aria-label={alt}>
        <Icon name="leaf" size={28} />
      </div>
    );
  }
  if (!url) return <div className={`img-loading skeleton ${className}`} aria-hidden="true" />;
  return (
    <motion.img
      className={className}
      src={url}
      alt={alt}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    />
  );
}