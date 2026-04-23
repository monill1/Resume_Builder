export const RESUME_TEMPLATES = [
  {
    id: "classic-professional",
    name: "Classic Professional",
    description: "Balanced, recruiter-friendly layout with strong ATS safety.",
    atsLevel: "High",
    defaultSectionColor: "#1c5fdb",
  },
  {
    id: "contemporary-accent",
    name: "Contemporary Accent",
    description: "Modern professional design with subtle accent framing.",
    atsLevel: "High",
    defaultSectionColor: "#1e3a8a",
  },
  {
    id: "executive-elegance",
    name: "Executive Elegance",
    description: "Elegant executive layout with a polished sidebar and refined hierarchy.",
    atsLevel: "High",
    defaultSectionColor: "#8a6430",
  },
  {
    id: "profile-banner",
    name: "Profile Banner",
    description: "Bold top banner with a circular profile mark, info sidebar, and roomy main column.",
    atsLevel: "Medium",
    defaultSectionColor: "#dc5b60",
  },
];

export const DEFAULT_TEMPLATE_ID = RESUME_TEMPLATES[0].id;

export function getTemplateMeta(templateId) {
  return RESUME_TEMPLATES.find((template) => template.id === templateId) || RESUME_TEMPLATES[0];
}
