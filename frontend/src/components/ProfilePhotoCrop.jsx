import { useEffect, useState } from "react";
import { normalizePhotoOffset } from "../resumeData";

function buildProfilePhotoStyle(naturalWidth, naturalHeight, size, offsetY) {
  const safeSize = Math.max(1, Number(size) || 1);
  const safeOffset = normalizePhotoOffset(offsetY);

  if (!(naturalWidth > 0) || !(naturalHeight > 0)) {
    return {
      width: "100%",
      height: "100%",
      transform: "none",
    };
  }

  if (naturalHeight > naturalWidth) {
    const scale = safeSize / naturalWidth;
    const renderedHeight = naturalHeight * scale;
    const overflow = Math.max(0, renderedHeight - safeSize);
    const top = (overflow / 2) + ((safeOffset / 40) * (overflow / 2));
    return {
      width: "100%",
      height: "auto",
      maxWidth: "none",
      transform: `translateY(${-top}px)`,
    };
  }

  const scale = safeSize / naturalHeight;
  const renderedWidth = naturalWidth * scale;
  const overflow = Math.max(0, renderedWidth - safeSize);
  const left = overflow / 2;
  return {
    width: "auto",
    height: "100%",
    maxWidth: "none",
    transform: `translateX(${-left}px)`,
  };
}

export default function ProfilePhotoCrop({ src, alt = "", size, offsetY = 0, className = "" }) {
  const [dimensions, setDimensions] = useState(null);

  useEffect(() => {
    setDimensions(null);
  }, [src]);

  const imageStyle = dimensions
    ? buildProfilePhotoStyle(dimensions.width, dimensions.height, size, offsetY)
    : { width: "100%", height: "100%", transform: "none" };

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      draggable={false}
      onLoad={(event) => {
        setDimensions({
          width: event.currentTarget.naturalWidth || Number(size) || 1,
          height: event.currentTarget.naturalHeight || Number(size) || 1,
        });
      }}
      style={imageStyle}
    />
  );
}
