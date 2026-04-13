export const RESUME_TEMPLATES = [
  {
    id: "classic-professional",
    name: "Classic Professional",
    description: "Balanced, recruiter-friendly layout with strong ATS safety.",
    atsLevel: "High",
  },
  {
    id: "contemporary-accent",
    name: "Contemporary Accent",
    description: "Modern professional design with subtle accent framing.",
    atsLevel: "High",
  },
];

export const DEFAULT_TEMPLATE_ID = RESUME_TEMPLATES[0].id;

export function getTemplateMeta(templateId) {
  return RESUME_TEMPLATES.find((template) => template.id === templateId) || RESUME_TEMPLATES[0];
}
