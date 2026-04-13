import { formatDateRange, normalizeSectionOrder, normalizeUrl } from "../resumeData";

const SECTION_TITLES = {
  summary: "Summary",
  skills: "Skills",
  experience: "Experience",
  projects: "Projects",
  education: "Education",
  certifications: "Certifications",
};

const SIDEBAR_SECTION_KEYS = ["skills", "certifications"];
const TWO_COLUMN_LEFT_KEYS = ["skills", "education", "certifications"];

function hasText(...values) {
  return values.some((value) => String(value || "").trim());
}

function cleanList(items = []) {
  return items.map((item) => String(item || "").trim()).filter(Boolean);
}

export function getSectionTitle(sectionKey, count = 0) {
  if (sectionKey === "certifications" && count === 1) {
    return "Certification";
  }
  return SECTION_TITLES[sectionKey] || sectionKey;
}

export function buildResumeViewModel(resume) {
  const basics = {
    full_name: resume?.basics?.full_name || "",
    headline: resume?.basics?.headline || "",
    email: resume?.basics?.email || "",
    phone: resume?.basics?.phone || "",
    location: resume?.basics?.location || "",
    linkedin: resume?.basics?.linkedin ? normalizeUrl(resume.basics.linkedin) : "",
    github: resume?.basics?.github ? normalizeUrl(resume.basics.github) : "",
    website: resume?.basics?.website ? normalizeUrl(resume.basics.website) : "",
    summary: resume?.basics?.summary || "",
  };

  const contacts = [
    basics.phone ? { type: "phone", label: basics.phone, href: null } : null,
    basics.email ? { type: "email", label: basics.email, href: `mailto:${basics.email}` } : null,
    basics.location ? { type: "location", label: basics.location, href: null } : null,
    basics.linkedin ? { type: "linkedin", label: "LinkedIn", href: basics.linkedin } : null,
    basics.github ? { type: "github", label: "GitHub", href: basics.github } : null,
    basics.website ? { type: "website", label: "Portfolio", href: basics.website } : null,
  ].filter(Boolean);

  const skills = (resume?.skills || [])
    .map((item) => ({
      ...item,
      name: String(item?.name || "").trim(),
      items: cleanList(item?.items),
    }))
    .filter((item) => item.name || item.items.length);

  const experience = (resume?.experience || [])
    .map((item) => ({
      ...item,
      company: String(item?.company || "").trim(),
      company_link: item?.company_link ? normalizeUrl(item.company_link) : "",
      role: String(item?.role || "").trim(),
      location: String(item?.location || "").trim(),
      start_date: String(item?.start_date || "").trim(),
      end_date: String(item?.end_date || "").trim(),
      achievements: cleanList(item?.achievements),
      date_label: formatDateRange(item).replace(/\s+-\s+$/, "").trim(),
    }))
    .filter((item) =>
      hasText(item.company, item.role, item.location, item.start_date, item.end_date, ...item.achievements)
    );

  const projects = (resume?.projects || [])
    .map((item) => ({
      ...item,
      name: String(item?.name || "").trim(),
      tech_stack: String(item?.tech_stack || "").trim(),
      link: item?.link ? normalizeUrl(item.link) : "",
      highlights: cleanList(item?.highlights),
    }))
    .filter((item) => hasText(item.name, item.tech_stack, item.link, ...item.highlights));

  const education = (resume?.education || [])
    .map((item) => ({
      ...item,
      institution: String(item?.institution || "").trim(),
      degree: String(item?.degree || "").trim(),
      duration: String(item?.duration || "").trim(),
      score: String(item?.score || "").trim(),
      location: String(item?.location || "").trim(),
    }))
    .filter((item) => hasText(item.institution, item.degree, item.duration, item.score, item.location));

  const certifications = (resume?.certifications || [])
    .map((item) => ({
      ...item,
      title: String(item?.title || "").trim(),
      issuer: String(item?.issuer || "").trim(),
      year: String(item?.year || "").trim(),
    }))
    .filter((item) => hasText(item.title, item.issuer, item.year));

  const data = { basics, contacts, skills, experience, projects, education, certifications };
  const orderedSections = normalizeSectionOrder(resume?.section_order).filter((sectionKey) => sectionHasContent(data, sectionKey));

  return {
    ...data,
    orderedSections,
  };
}

export function sectionHasContent(data, sectionKey) {
  if (sectionKey === "summary") return !!String(data?.basics?.summary || "").trim();
  if (sectionKey === "skills") return !!data?.skills?.length;
  if (sectionKey === "experience") return !!data?.experience?.length;
  if (sectionKey === "projects") return !!data?.projects?.length;
  if (sectionKey === "education") return !!data?.education?.length;
  if (sectionKey === "certifications") return !!data?.certifications?.length;
  return false;
}

export function getSidebarSectionKeys(data) {
  return data.orderedSections.filter((key) => SIDEBAR_SECTION_KEYS.includes(key));
}

export function getMainSectionKeys(data) {
  return data.orderedSections.filter((key) => !SIDEBAR_SECTION_KEYS.includes(key));
}

export function getTwoColumnLeftKeys(data) {
  return data.orderedSections.filter((key) => TWO_COLUMN_LEFT_KEYS.includes(key));
}

export function getTwoColumnRightKeys(data) {
  return data.orderedSections.filter((key) => !TWO_COLUMN_LEFT_KEYS.includes(key));
}
