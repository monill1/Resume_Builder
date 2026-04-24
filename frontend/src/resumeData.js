export const DEFAULT_SECTION_ORDER = ["summary", "skills", "experience", "projects", "education", "certifications"];

export const SECTION_LABELS = {
  summary: "Summary",
  skills: "Skills",
  experience: "Experience",
  projects: "Projects",
  education: "Education",
  certifications: "Certifications",
};

export const normalizeSectionOrder = (order = []) => {
  const safeOrder = Array.isArray(order) ? order : [];
  const uniqueKnown = safeOrder.filter((key, index) => DEFAULT_SECTION_ORDER.includes(key) && safeOrder.indexOf(key) === index);
  const missing = DEFAULT_SECTION_ORDER.filter((key) => !uniqueKnown.includes(key));
  return [...uniqueKnown, ...missing];
};

export const normalizeLayoutOptions = (options = {}) => ({
  executive_certifications_in_sidebar: Boolean(options?.executive_certifications_in_sidebar),
});

export const normalizePhotoDataUrl = (value) => {
  const trimmed = String(value || "").trim();
  return trimmed.startsWith("data:image/") ? trimmed : "";
};

export const normalizePhotoOffset = (value) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(-40, Math.min(40, Math.round(parsed)));
};

export const normalizeResumeData = (data) => ({
  ...data,
  basics: {
    ...(data?.basics || {}),
    photo: normalizePhotoDataUrl(data?.basics?.photo),
    photo_offset_y: normalizePhotoOffset(data?.basics?.photo_offset_y),
  },
  layout_options: normalizeLayoutOptions(data?.layout_options),
  section_order: normalizeSectionOrder(data?.section_order),
});

export const normalizeUrl = (value) => {
  const trimmed = String(value || "").trim();
  if (!trimmed) return "";
  if (trimmed.includes("://")) return trimmed;
  return `https://${trimmed}`;
};

export const formatDateRange = (item) => `${item.start_date} - ${item.current ? "Current" : item.end_date || ""}`.trim();
