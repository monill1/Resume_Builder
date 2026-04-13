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

export const normalizeResumeData = (data) => ({
  ...data,
  section_order: normalizeSectionOrder(data?.section_order),
});

export const normalizeUrl = (value) => {
  const trimmed = String(value || "").trim();
  if (!trimmed) return "";
  if (trimmed.includes("://")) return trimmed;
  return `https://${trimmed}`;
};

export const formatDateRange = (item) => `${item.start_date} - ${item.current ? "Current" : item.end_date || ""}`.trim();
