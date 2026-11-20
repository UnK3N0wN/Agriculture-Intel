import { useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { validateImage } from "../lib/utils.js";
import Icon from "./Icon.jsx";

export default function ScannerZone({ file, previewUrl, onFile, onClear, onReject, disabled }) {
  const [dragging, setDragging] = useState(false);
  const depth = useRef(0);
  const browseRef = useRef(null);
  const cameraRef = useRef(null);

  function take(files) {
    const picked = files && files[0];
    if (!picked) return;
    const problem = validateImage(picked);
    if (problem) {
      onReject(problem);
      return;
    }
    onFile(picked);
  }

  function handleDrop(event) {
    event.preventDefault();
    depth.current = 0;
    setDragging(false);
    if (!disabled) take(event.dataTransfer.files);
  }
  function handleEnter(event) {
    event.preventDefault();
    if (disabled) return;
    depth.current += 1;
    setDragging(true);
  }
  function handleLeave() {
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) setDragging(false);
  }
  function handleInput(event) {
    take(event.target.files);
    event.target.value = ""; // lets you pick the same file again
  }

  const buttons = (
    <div className="drop-actions">
      <button type="button" className="btn btn-primary" onClick={() => browseRef.current?.click()} disabled={disabled}>
        <Icon name="upload" size={18} />
        {file ? "Replace photo" : "Choose photo"}
      </button>
      <button type="button" className="btn btn-ghost" onClick={() => cameraRef.current?.click()} disabled={disabled}>
        <Icon name="camera" size={18} />
        Use camera
      </button>
      {file && (
        <button type="button" className="btn btn-ghost" onClick={onClear} disabled={disabled}>
          <Icon name="trash" size={18} />
          Remove
        </button>
      )}
    </div>
  );

  return (
    <motion.div
      className={`drop-zone ${dragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
      role="group"
      aria-label="Photo upload area. Drag a photo here, or use the buttons."
      onDragEnter={handleEnter}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={handleLeave}
      onDrop={handleDrop}
      animate={{ scale: dragging ? 1.02 : 1 }}
      whileHover={disabled || file ? undefined : { scale: 1.01 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
    >
      <input ref={browseRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={handleInput} />
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={handleInput} />

      <AnimatePresence mode="wait" initial={false}>
        {file && previewUrl ? (
          <motion.div key="preview" className="drop-preview" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
            <img src={previewUrl} alt="Your selected leaf" />
            <p className="muted small">
              {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB
            </p>
            {buttons}
          </motion.div>
        ) : (
          <motion.div key="empty" className="drop-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.div
              className="drop-icon"
              animate={dragging ? { y: [0, -10, 0] } : { y: 0 }}
              transition={dragging ? { duration: 0.8, repeat: Infinity } : { duration: 0.2 }}
            >
              <Icon name="upload" size={38} />
            </motion.div>
            <p className="drop-title">{dragging ? "Drop it here" : "Drag a leaf photo here"}</p>
            <p className="muted small">JPEG, PNG or WebP · up to 8 MB · one leaf, good light, in focus</p>
            {buttons}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}