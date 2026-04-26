import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "./config";
import ProfilePhotoCrop from "./components/ProfilePhotoCrop";
import { stripRichText } from "./richText";
import ResumePreviewPanel from "./resumeTemplates/ResumePreview";
import { DEFAULT_TEMPLATE_ID, RESUME_TEMPLATES, getTemplateMeta } from "./resumeTemplates/templateMeta";
import { sampleResume } from "./sampleResume";
import { normalizeLayoutOptions, normalizePhotoDataUrl, normalizePhotoOffset, normalizeResumeData, normalizeSectionOrder, normalizeUrl, SECTION_LABELS } from "./resumeData";

const RESUME_DRAFT_KEY = "ats-resume-builder-draft";
const RESUME_PROFILE_DRAFT_PREFIX = "ats-resume-builder-profile-draft:";
const RESUME_ACTIVE_PROFILE_KEY = "ats-resume-builder-active-profile";
const RESUME_TEMPLATE_KEY = "ats-resume-builder-template";
const RESUME_TEMPLATE_COLOR_KEY = "ats-resume-builder-template-section-colors";
const WORKSPACE_VIEW_KEY = "ats-resume-builder-workspace-view";
const AUTH_TOKEN_KEY = "ats-resume-builder-auth-token";
const ATS_DEMO_ROLE = {
  title: "Backend Developer",
  description: `Backend Developer
Required qualifications:
- 3+ years of experience building Python backend services.
- Strong experience with FastAPI or Django, REST APIs, PostgreSQL, Docker, and AWS.
- Experience designing scalable microservices and CI/CD pipelines.
- Bachelor's degree in Computer Science or related field.
Preferred qualifications:
- Experience with Kafka, Redis, and Kubernetes.
- Strong communication and stakeholder collaboration.
Responsibilities:
- Build APIs, own backend architecture, and partner with frontend and product teams.`,
};
const emptySkill = { name: "", items: [] };
const emptyExperience = { company: "", company_link: "", role: "", location: "", start_date: "", end_date: "", current: false, achievements: [""] };
const emptyProject = { name: "", tech_stack: "", year: "", link: "", highlights: [""] };
const emptyEducation = { institution: "", degree: "", duration: "", score: "", location: "" };
const emptyCertification = { title: "", issuer: "", year: "" };
const SECTION_SCORE_META = {
  skills_match: {
    title: "Skills Match",
    caption: "Required and preferred skills, with extra credit for evidence in experience and projects.",
  },
  experience_relevance: {
    title: "Experience Relevance",
    caption: "Role title fit, domain overlap, years alignment, and proof inside work history.",
  },
  keyword_coverage: {
    title: "Keyword Coverage",
    caption: "Natural contextual usage across summary, bullets, projects, and achievements.",
  },
  education_certifications: {
    title: "Education & Certifications",
    caption: "Degree, certification, location, and work authorization checks when relevant.",
  },
  formatting_parseability: {
    title: "Formatting & Parseability",
    caption: "ATS-safe structure, standard headings, readable flow, and parsing confidence.",
  },
  completeness: {
    title: "Completeness",
    caption: "Contact details, summary quality, quantified impact, and expected sections.",
  },
};
const SKILL_PLACEMENT_RULES = [
  {
    groupName: "AI & ML",
    groupPattern: /(ai|ml|machine learning|llm|gen ai|generative|agent|rag)/i,
    skillPattern: /(tensorflow|pytorch|keras|scikit-learn|sklearn|machine learning|nlp|langchain|langgraph|llamaindex|autogen|agentic ai|generative ai|prompt engineering|vector db|rag|pinecone|weaviate|chroma|faiss|qdrant)/i,
    signalPattern: /(langchain|langgraph|llamaindex|autogen|agentic ai|generative ai|prompt engineering|vector db|rag|machine learning|scikit|tensorflow|pytorch)/i,
  },
  {
    groupName: "Cloud & DevOps",
    groupPattern: /(cloud|devops|platform|infrastructure|tools)/i,
    skillPattern: /(aws|azure|gcp|docker|kubernetes|ci\/cd|cicd|jenkins|github actions|terraform|linux)/i,
    signalPattern: /(aws|azure|gcp|docker|kubernetes|ci\/cd|cicd|jenkins|github actions|terraform|linux|git)/i,
  },
  {
    groupName: "Backend Engineering",
    groupPattern: /(backend|api|engineering|framework|server)/i,
    skillPattern: /(fastapi|django|flask|rest api|rest apis|graphql|microservices|node\.js|node|redis|kafka)/i,
    signalPattern: /(fastapi|django|flask|rest api|rest apis|graphql|microservices|node\.js|node|redis|kafka|python)/i,
  },
  {
    groupName: "Data & Analytics",
    groupPattern: /(data|analytics|visualization|bi|reporting)/i,
    skillPattern: /(sql|postgresql|snowflake|bigquery|pandas|numpy|tableau|power bi|looker|excel|data visualization|a\/b testing|experimentation|etl|dbt)/i,
    signalPattern: /(sql|postgresql|snowflake|bigquery|pandas|numpy|tableau|power bi|looker|excel|data visualization|a\/b testing|experimentation|etl|dbt)/i,
  },
  {
    groupName: "Frontend",
    groupPattern: /(frontend|ui|web)/i,
    skillPattern: /(react|javascript|typescript|html|css|streamlit)/i,
    signalPattern: /(react|javascript|typescript|html|css|streamlit)/i,
  },
  {
    groupName: "Product & Delivery",
    groupPattern: /(product|project|delivery|agile|scrum|program)/i,
    skillPattern: /(product management|roadmap|user stories|requirements|stakeholder management|agile|scrum|jira|confluence|prioritization|release planning)/i,
    signalPattern: /(roadmap|user stories|requirements|stakeholder|agile|scrum|jira|confluence|prioritization|release)/i,
  },
  {
    groupName: "Business & Operations",
    groupPattern: /(business|operations|process|strategy|analysis)/i,
    skillPattern: /(business analysis|process improvement|operations|kpi|stakeholder management|documentation|sop|gap analysis|requirement gathering)/i,
    signalPattern: /(business analysis|process|operations|kpi|stakeholder|documentation|sop|gap analysis|requirement)/i,
  },
  {
    groupName: "Marketing & Growth",
    groupPattern: /(marketing|growth|campaign|seo|content|social)/i,
    skillPattern: /(seo|sem|google analytics|campaign management|content strategy|social media|email marketing|performance marketing|conversion optimization|crm)/i,
    signalPattern: /(seo|sem|analytics|campaign|content|social|email marketing|performance marketing|conversion|crm)/i,
  },
  {
    groupName: "Sales & Customer",
    groupPattern: /(sales|customer|client|account|support|success)/i,
    skillPattern: /(salesforce|crm|lead generation|account management|customer success|client relationship|negotiation|pipeline management|customer support)/i,
    signalPattern: /(salesforce|crm|lead|account|customer success|client|negotiation|pipeline|support)/i,
  },
  {
    groupName: "Finance & Compliance",
    groupPattern: /(finance|accounting|audit|tax|compliance|risk)/i,
    skillPattern: /(financial analysis|accounting|reconciliation|budgeting|forecasting|audit|taxation|compliance|risk analysis|tally|quickbooks)/i,
    signalPattern: /(financial|accounting|reconciliation|budget|forecast|audit|tax|compliance|risk|tally|quickbooks)/i,
  },
  {
    groupName: "People & Hiring",
    groupPattern: /(hr|human resources|people|talent|recruit)/i,
    skillPattern: /(recruitment|talent acquisition|hr operations|onboarding|employee engagement|payroll|performance management|sourcing|interviewing)/i,
    signalPattern: /(recruit|talent|hr|onboarding|employee|payroll|performance|sourcing|interview)/i,
  },
  {
    groupName: "Design & Research",
    groupPattern: /(design|ux|ui|research|creative)/i,
    skillPattern: /(figma|wireframing|prototyping|user research|usability testing|design systems|adobe|photoshop|illustrator)/i,
    signalPattern: /(figma|wireframe|prototype|user research|usability|design system|adobe|photoshop|illustrator)/i,
  },
];

const RESUME_EXPORT_RULES = [
  { path: ["basics", "full_name"], label: "Full Name", minLength: 2 },
  { path: ["basics", "email"], label: "Email", minLength: 3, validate: (value) => /\S+@\S+\.\S+/.test(value) || "Email must be valid." },
  { path: ["basics", "phone"], label: "Phone", minLength: 7 },
  { path: ["basics", "location"], label: "Location", minLength: 2 },
  { path: ["basics", "summary"], label: "Professional Summary", minLength: 30 },
];
const BOLD_MARKER = "**";
const HEX_COLOR_RE = /^#[0-9a-f]{6}$/i;
const PROFILE_PHOTO_MAX_BYTES = 4 * 1024 * 1024;
const RAZORPAY_CHECKOUT_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

function loadRazorpayCheckout() {
  if (window.Razorpay) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const existingScript = document.querySelector(`script[src="${RAZORPAY_CHECKOUT_SCRIPT}"]`);
    if (existingScript) {
      existingScript.addEventListener("load", resolve, { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Unable to load Razorpay Checkout.")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = RAZORPAY_CHECKOUT_SCRIPT;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error("Unable to load Razorpay Checkout."));
    document.body.appendChild(script);
  });
}

function getValueAtPath(source, path) {
  return path.reduce((current, key) => current?.[key], source);
}

function formatValidationLocation(path) {
  const cleanedPath = path.filter((part) => part !== "body" && part !== "resume");
  if (!cleanedPath.length) return "Resume data";

  const lastPart = cleanedPath[cleanedPath.length - 1];
  return String(lastPart)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatValidationDetail(detail) {
  const label = Array.isArray(detail?.loc) ? formatValidationLocation(detail.loc) : "Resume data";
  const message = detail?.msg || detail?.message || "is invalid.";
  return `${label}: ${message}`;
}

function validateResumeForExport(resumePayload) {
  for (const rule of RESUME_EXPORT_RULES) {
    const value = stripRichText(getValueAtPath(resumePayload, rule.path)).trim();

    if (value.length < rule.minLength) {
      return `${rule.label} must be at least ${rule.minLength} characters.`;
    }

    if (rule.validate) {
      const result = rule.validate(value);
      if (result !== true) {
        return result;
      }
    }
  }

  return null;
}

function normalizeHexColor(value, fallback) {
  const normalized = String(value || "").trim().toLowerCase();
  return HEX_COLOR_RE.test(normalized) ? normalized : fallback;
}

function readTemplateSectionColorMap() {
  try {
    const rawValue = window.localStorage.getItem(RESUME_TEMPLATE_COLOR_KEY);
    const parsedValue = rawValue ? JSON.parse(rawValue) : {};
    if (!parsedValue || typeof parsedValue !== "object") return {};

    return Object.fromEntries(
      Object.entries(parsedValue)
        .filter(([templateId, color]) => typeof templateId === "string" && HEX_COLOR_RE.test(String(color || "")))
        .map(([templateId, color]) => [templateId, String(color).toLowerCase()])
    );
  } catch {
    return {};
  }
}

function getTemplateSectionColor(templateId, colorMap) {
  const templateMeta = getTemplateMeta(templateId);
  return normalizeHexColor(colorMap?.[templateMeta.id], templateMeta.defaultSectionColor);
}

function updateSelectionAfterFormat(input, selectionStart, selectionEnd) {
  window.requestAnimationFrame(() => {
    input.focus({ preventScroll: true });
    input.setSelectionRange(selectionStart, selectionEnd);
  });
}

function applyBoldFormatting(input, value, onChange) {
  if (!input) return;

  const text = String(value || "");
  const selectionStart = input.selectionStart ?? 0;
  const selectionEnd = input.selectionEnd ?? selectionStart;

  if (selectionStart === selectionEnd) {
    const nextValue = `${text.slice(0, selectionStart)}${BOLD_MARKER}${BOLD_MARKER}${text.slice(selectionEnd)}`;
    onChange(nextValue);
    updateSelectionAfterFormat(input, selectionStart + BOLD_MARKER.length, selectionStart + BOLD_MARKER.length);
    return;
  }

  const before = text.slice(0, selectionStart);
  const selectedText = text.slice(selectionStart, selectionEnd);
  const after = text.slice(selectionEnd);
  const isWrapped = before.endsWith(BOLD_MARKER) && after.startsWith(BOLD_MARKER);

  if (isWrapped) {
    const nextValue = `${before.slice(0, -BOLD_MARKER.length)}${selectedText}${after.slice(BOLD_MARKER.length)}`;
    onChange(nextValue);
    updateSelectionAfterFormat(input, selectionStart - BOLD_MARKER.length, selectionEnd - BOLD_MARKER.length);
    return;
  }

  const nextValue = `${before}${BOLD_MARKER}${selectedText}${BOLD_MARKER}${after}`;
  onChange(nextValue);
  updateSelectionAfterFormat(input, selectionStart + BOLD_MARKER.length, selectionEnd + BOLD_MARKER.length);
}

function handleBoldShortcut(event, input, value, onChange) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "b") {
    event.preventDefault();
    applyBoldFormatting(input, value, onChange);
  }
}

function buildFallbackResumeFilename(fullName) {
  const normalizedName = String(fullName || "")
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1F]+/g, "")
    .replace(/\s+/g, "_");
  return `${normalizedName || "resume"}.pdf`;
}

function parseCommaSeparatedSkills(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatCommaSeparatedSkills(items) {
  return (items || []).map((item) => String(item || "").trim()).filter(Boolean).join(", ");
}

function getAvatarInitials(fullName) {
  const parts = String(fullName || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  const initials = parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("");
  return initials || "CV";
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Unable to read the selected image."));
    reader.readAsDataURL(file);
  });
}

function loadImageElement(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Unable to process the selected image."));
    image.src = src;
  });
}

async function buildProfilePhotoDataUrl(file) {
  if (!file) {
    return "";
  }

  if (!String(file.type || "").startsWith("image/")) {
    throw new Error("Please upload an image file for the profile photo.");
  }

  if (file.size > PROFILE_PHOTO_MAX_BYTES) {
    throw new Error("Profile photo must be 4 MB or smaller.");
  }

  const source = await readFileAsDataUrl(file);
  const image = await loadImageElement(source);
  const width = image.naturalWidth || image.width;
  const height = image.naturalHeight || image.height;
  const longestSide = Math.max(width, height);
  const scale = longestSide > 1200 ? 1200 / longestSide : 1;
  const targetWidth = Math.max(1, Math.round(width * scale));
  const targetHeight = Math.max(1, Math.round(height * scale));

  const canvas = document.createElement("canvas");
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Unable to prepare the profile photo.");
  }

  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.9);
}

function getDownloadFilename(headers, fallbackFilename) {
  const disposition = headers.get("Content-Disposition") || headers.get("content-disposition") || "";
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]).replace(/^["']|["']$/g, "");
  }

  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (filenameMatch?.[1]) {
    return filenameMatch[1].trim();
  }

  return fallbackFilename;
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  window.setTimeout(() => {
    window.URL.revokeObjectURL(url);
  }, 1000);
}

function getProfileDraftKey(profileId) {
  return profileId ? `${RESUME_PROFILE_DRAFT_PREFIX}${profileId}` : RESUME_DRAFT_KEY;
}

function getProfileQuery(profileId) {
  return profileId ? `?profile_id=${encodeURIComponent(profileId)}` : "";
}

function removeBrowserProfileDrafts() {
  const keysToRemove = [RESUME_DRAFT_KEY, RESUME_ACTIVE_PROFILE_KEY];
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key?.startsWith(RESUME_PROFILE_DRAFT_PREFIX)) {
      keysToRemove.push(key);
    }
  }
  keysToRemove.forEach((key) => window.localStorage.removeItem(key));
}

async function readErrorMessage(response, fallbackMessage) {
  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string" && payload.detail.trim()) {
        return payload.detail;
      }
      if (Array.isArray(payload?.detail) && payload.detail.length) {
        return payload.detail.map(formatValidationDetail).join(", ") || fallbackMessage;
      }
    } catch {
      return fallbackMessage;
    }
  }

  try {
    const errorText = await response.text();
    return errorText || fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}

function backendReachabilityMessage(error) {
  const rawMessage = error?.message || "";
  if (rawMessage && rawMessage !== "Failed to fetch") {
    return rawMessage;
  }
  const target = API_BASE_URL || "the local /api proxy";
  return `Could not reach the backend through ${target}. Make sure the FastAPI server is running on port 8007 and restart the Vite dev server after config changes.`;
}

function App() {
  const [resume, setResume] = useState(() => normalizeResumeData(structuredClone(sampleResume)));
  const [selectedTemplate, setSelectedTemplate] = useState(() => getTemplateMeta(window.localStorage.getItem(RESUME_TEMPLATE_KEY)).id);
  const [templateSectionColors, setTemplateSectionColors] = useState(() => readTemplateSectionColorMap());
  const [activeWorkspace, setActiveWorkspace] = useState(() => (window.localStorage.getItem(WORKSPACE_VIEW_KEY) === "ats" ? "ats" : "editor"));
  const [authToken, setAuthToken] = useState(() => window.localStorage.getItem(AUTH_TOKEN_KEY) || "");
  const [authUser, setAuthUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(() => Boolean(window.localStorage.getItem(AUTH_TOKEN_KEY)));
  const [authMode, setAuthMode] = useState("signin");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authOtp, setAuthOtp] = useState("");
  const [authStatus, setAuthStatus] = useState("Sign in to access your resume workspace.");
  const [authLoading, setAuthLoading] = useState(false);
  const [resumeProfiles, setResumeProfiles] = useState([]);
  const [activeProfileId, setActiveProfileId] = useState(() => window.localStorage.getItem(RESUME_ACTIVE_PROFILE_KEY) || "");
  const [profileName, setProfileName] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("Ready to build a polished resume and score it against a target job.");
  const [atsTargetTitle, setAtsTargetTitle] = useState("");
  const [atsJobUrl, setAtsJobUrl] = useState("");
  const [atsJobDescription, setAtsJobDescription] = useState("");
  const [atsResumePdf, setAtsResumePdf] = useState(null);
  const [atsReviewSource, setAtsReviewSource] = useState("editor");
  const [atsLoading, setAtsLoading] = useState(false);
  const [atsFixing, setAtsFixing] = useState(false);
  const [atsStatus, setAtsStatus] = useState("Paste a public job URL, a job description, or both to run a recruiter-style ATS check.");
  const [atsResult, setAtsResult] = useState(null);
  const [atsResultSource, setAtsResultSource] = useState("editor");
  const [atsOptimization, setAtsOptimization] = useState(null);
  const [hasSavedDraft, setHasSavedDraft] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState(null);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [paymentMessage, setPaymentMessage] = useState("");

  const hasAnyText = (...values) => values.some((value) => String(value || "").trim());
  const authHeaders = (headers = {}) => ({
    ...headers,
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  });
  const activeProfile = resumeProfiles.find((profile) => String(profile.id) === String(activeProfileId)) || null;
  const activeProfileLabel = activeProfile?.name || "selected profile";
  const paymentPlans = Array.isArray(paymentStatus?.plans) ? paymentStatus.plans : [];
  const remainingDownloads = Number(paymentStatus?.remaining_downloads || 0);
  const isPaymentExempt = Boolean(paymentStatus?.exempt);

  useEffect(() => {
    let active = true;

    async function verifySession() {
      if (!authToken) {
        setAuthUser(null);
        setAuthChecking(false);
        return;
      }

      setAuthChecking(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          headers: authHeaders(),
        });
        if (!response.ok) {
          throw new Error("Session expired.");
        }
        const data = await response.json();
        if (!active) return;
        setAuthUser(data);
      } catch {
        if (!active) return;
        window.localStorage.removeItem(AUTH_TOKEN_KEY);
        setAuthToken("");
        setAuthUser(null);
        setAuthStatus("Please sign in again to continue.");
      } finally {
        if (active) setAuthChecking(false);
      }
    }

    verifySession();
    return () => {
      active = false;
    };
  }, [authToken]);

  useEffect(() => {
    let active = true;

    async function hydrateProfiles() {
      if (!authToken) {
        setResumeProfiles([]);
        setActiveProfileId("");
        return;
      }

      setProfileLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/resume/profiles`, {
          headers: authHeaders(),
        });
        if (!response.ok) {
          const message = await readErrorMessage(response, "Unable to load resume profiles.");
          throw new Error(message);
        }

        const data = await response.json();
        if (!active) return;
        const profiles = Array.isArray(data?.profiles) ? data.profiles : [];
        setResumeProfiles(profiles);

        const storedProfileId = window.localStorage.getItem(RESUME_ACTIVE_PROFILE_KEY);
        const preferredProfile = profiles.find((profile) => String(profile.id) === String(activeProfileId || storedProfileId));
        const nextProfile = preferredProfile || profiles[0] || null;
        setActiveProfileId(nextProfile ? String(nextProfile.id) : "");
      } catch (error) {
        if (active) {
          setStatus(`Unable to load resume profiles: ${error.message}`);
        }
      } finally {
        if (active) setProfileLoading(false);
      }
    }

    hydrateProfiles();
    return () => {
      active = false;
    };
  }, [authToken]);

  useEffect(() => {
    if (activeProfileId) {
      window.localStorage.setItem(RESUME_ACTIVE_PROFILE_KEY, activeProfileId);
    }
  }, [activeProfileId]);

  const refreshPaymentStatus = async () => {
    if (!authToken) {
      setPaymentStatus(null);
      return null;
    }

    const response = await fetch(`${API_BASE_URL}/api/payments/status`, {
      headers: authHeaders(),
    });
    if (!response.ok) {
      const message = await readErrorMessage(response, "Unable to load payment status.");
      throw new Error(message);
    }

    const data = await response.json();
    setPaymentStatus(data);
    return data;
  };

  useEffect(() => {
    let active = true;

    async function hydratePaymentStatus() {
      if (!authToken) {
        setPaymentStatus(null);
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/payments/status`, {
          headers: authHeaders(),
        });
        if (!response.ok) {
          throw new Error("Unable to load payment status.");
        }
        const data = await response.json();
        if (active) setPaymentStatus(data);
      } catch {
        if (active) setPaymentMessage("Payment status could not be loaded.");
      }
    }

    hydratePaymentStatus();
    return () => {
      active = false;
    };
  }, [authToken]);

  useEffect(() => {
    let active = true;

    async function hydrateFromBackend() {
      if (!authToken || !activeProfileId) return;

      try {
        const response = await fetch(`${API_BASE_URL}/api/resume/latest${getProfileQuery(activeProfileId)}`, {
          headers: authHeaders(),
        });
        if (response.ok) {
          const data = await response.json();
          if (!active) return;
          if (data?.resume) {
            setResume(normalizeResumeData(data.resume));
            if (data.template_id) {
              setSelectedTemplate(getTemplateMeta(data.template_id).id);
            }
            if (data.template_id && HEX_COLOR_RE.test(String(data.section_color || ""))) {
              setTemplateSectionColors((current) => ({
                ...current,
                [getTemplateMeta(data.template_id).id]: String(data.section_color).toLowerCase(),
              }));
            }
            setHasSavedDraft(true);
            setStatus(`Saved draft restored for ${activeProfileLabel}.`);
            return;
          }
          setHasSavedDraft(false);
          setResume(normalizeResumeData(structuredClone(sampleResume)));
          setStatus(`${activeProfileLabel} has no saved draft yet. Edit the resume and save it to this profile.`);
          return;
        }
        if (response.status === 401) {
          window.localStorage.removeItem(AUTH_TOKEN_KEY);
          setAuthToken("");
          setAuthStatus("Your session expired. Sign in again to load saved data.");
          return;
        }
      } catch {
        // Fall back to browser storage or bundled sample data when the backend is offline.
      }

      try {
        const savedDraft = window.localStorage.getItem(getProfileDraftKey(activeProfileId));
        const legacyDraft = window.localStorage.getItem(RESUME_DRAFT_KEY);
        const draftToRestore = savedDraft || (activeProfile?.name === "Default Profile" ? legacyDraft : null);
        if (draftToRestore) {
          const parsedDraft = JSON.parse(draftToRestore);
          if (!active) return;
          setResume(normalizeResumeData(parsedDraft));
          setHasSavedDraft(true);
          setStatus(`Browser fallback draft restored for ${activeProfileLabel}.`);
          return;
        }
      } catch {
        // Ignore local draft parse errors and fall back to sample data.
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/sample`);
        if (!response.ok) {
          if (active) setResume(normalizeResumeData(structuredClone(sampleResume)));
          return;
        }
        const data = await response.json();
        if (active && data?.resume) setResume(normalizeResumeData(data.resume));
      } catch {
        if (active) setResume(normalizeResumeData(structuredClone(sampleResume)));
      }
    }

    hydrateFromBackend();
    return () => {
      active = false;
    };
  }, [authToken, activeProfileId, activeProfileLabel]);

  useEffect(() => {
    window.localStorage.setItem(RESUME_TEMPLATE_KEY, selectedTemplate);
  }, [selectedTemplate]);

  useEffect(() => {
    window.localStorage.setItem(RESUME_TEMPLATE_COLOR_KEY, JSON.stringify(templateSectionColors));
  }, [templateSectionColors]);

  useEffect(() => {
    window.localStorage.setItem(WORKSPACE_VIEW_KEY, activeWorkspace);
  }, [activeWorkspace]);

  const changeAuthMode = (mode) => {
    const statusByMode = {
      signin: "Sign in to access your resume workspace.",
      signup: "Create an account and verify it by email.",
      forgot: "Enter your account email to receive a password reset code.",
    };
    setAuthMode(mode);
    setAuthOtp("");
    setAuthPassword("");
    setAuthStatus(statusByMode[mode] || "Continue with email verification.");
  };

  const completeAuthSession = (data) => {
    window.localStorage.setItem(AUTH_TOKEN_KEY, data.token);
    setAuthToken(data.token);
    setAuthUser(data.user);
    setAuthPassword("");
    setAuthOtp("");
    setHasSavedDraft(false);
    setStatus("Signed in. Your resume workspace is ready.");
    setAuthStatus("Signed in successfully.");
  };

  const submitAuth = async (event) => {
    event.preventDefault();
    setAuthLoading(true);
    const email = authEmail.trim();

    const statusByMode = {
      signin: "Signing you in...",
      signup: "Sending verification code...",
      "signup-verify": "Verifying your account...",
      forgot: "Sending reset code...",
      "reset-verify": "Updating your password...",
    };
    setAuthStatus(statusByMode[authMode] || "Please wait...");

    try {
      if (authMode === "signup") {
        const response = await fetch(`${API_BASE_URL}/api/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password: authPassword }),
        });

        if (!response.ok) {
          const message = await readErrorMessage(response, "Unable to send verification code.");
          throw new Error(message);
        }

        const data = await response.json();
        setAuthMode("signup-verify");
        setAuthPassword("");
        setAuthStatus(data.message || "Verification code sent. Check your email.");
        return;
      }

      if (authMode === "signup-verify") {
        const response = await fetch(`${API_BASE_URL}/api/auth/signup/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, otp: authOtp.trim() }),
        });

        if (!response.ok) {
          const message = await readErrorMessage(response, "Unable to verify account.");
          throw new Error(message);
        }

        const data = await response.json();
        completeAuthSession(data);
        return;
      }

      if (authMode === "forgot") {
        const response = await fetch(`${API_BASE_URL}/api/auth/password/forgot`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });

        if (!response.ok) {
          const message = await readErrorMessage(response, "Unable to send reset code.");
          throw new Error(message);
        }

        const data = await response.json();
        setAuthMode("reset-verify");
        setAuthPassword("");
        setAuthOtp("");
        setAuthStatus(data.message || "Password reset code sent if the account exists.");
        return;
      }

      if (authMode === "reset-verify") {
        const response = await fetch(`${API_BASE_URL}/api/auth/password/reset`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, otp: authOtp.trim(), password: authPassword }),
        });

        if (!response.ok) {
          const message = await readErrorMessage(response, "Unable to reset password.");
          throw new Error(message);
        }

        const data = await response.json();
        setAuthMode("signin");
        setAuthPassword("");
        setAuthOtp("");
        setAuthStatus(data.message || "Password updated. Sign in with your new password.");
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: authPassword }),
      });

      if (!response.ok) {
        const message = await readErrorMessage(response, "Unable to sign in.");
        throw new Error(message);
      }

      const data = await response.json();
      completeAuthSession(data);
    } catch (error) {
      setAuthStatus(backendReachabilityMessage(error));
    } finally {
      setAuthLoading(false);
    }
  };

  const logOut = async () => {
    const token = authToken;
    try {
      if (token) {
        await fetch(`${API_BASE_URL}/api/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch {
      // The local session is still cleared even if the backend is unreachable.
    }

    window.localStorage.removeItem(AUTH_TOKEN_KEY);
    removeBrowserProfileDrafts();
    setAuthToken("");
    setAuthUser(null);
    setResumeProfiles([]);
    setActiveProfileId("");
    setHasSavedDraft(false);
    setResume(normalizeResumeData(structuredClone(sampleResume)));
    setAuthStatus("Signed out successfully.");
  };

  const saveDraft = async () => {
    setStatus(`Saving resume data to ${activeProfileLabel}...`);
    try {
      const response = await fetch(`${API_BASE_URL}/api/resume/save`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          profile_id: activeProfileId ? Number(activeProfileId) : null,
          template_id: selectedTemplate,
          section_color: currentSectionColor,
          resume,
        }),
      });

      if (!response.ok) {
        const message = await readErrorMessage(response, "Unable to save resume data");
        throw new Error(message);
      }

      try {
        window.localStorage.setItem(getProfileDraftKey(activeProfileId), JSON.stringify(resume));
      } catch {
        // Database save succeeded, so browser storage is only a convenience.
      }
      setHasSavedDraft(true);
      setResumeProfiles((current) =>
        current.map((profile) =>
          String(profile.id) === String(activeProfileId) ? { ...profile, has_saved_draft: true, latest_saved_at: new Date().toISOString() } : profile
        )
      );
      setStatus(`Resume data saved to ${activeProfileLabel}.`);
    } catch (error) {
      try {
        window.localStorage.setItem(getProfileDraftKey(activeProfileId), JSON.stringify(resume));
        setHasSavedDraft(true);
        setStatus(`Database save failed, but a browser fallback draft was saved for ${activeProfileLabel}: ${error.message}`);
      } catch {
        setStatus(`Unable to save the draft: ${error.message}`);
      }
    }
  };

  const clearSavedDraft = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/resume/saved${getProfileQuery(activeProfileId)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!response.ok) {
        const message = await readErrorMessage(response, "Unable to clear saved database drafts");
        throw new Error(message);
      }
      window.localStorage.removeItem(getProfileDraftKey(activeProfileId));
      setHasSavedDraft(false);
      setResumeProfiles((current) =>
        current.map((profile) => (String(profile.id) === String(activeProfileId) ? { ...profile, has_saved_draft: false, latest_saved_at: null } : profile))
      );
      setStatus(`Saved drafts cleared for ${activeProfileLabel}.`);
    } catch (error) {
      try {
        window.localStorage.removeItem(getProfileDraftKey(activeProfileId));
        setHasSavedDraft(false);
      } catch {
        // Keep the database error visible below.
      }
      setStatus(`Unable to clear saved drafts for ${activeProfileLabel}: ${error.message}`);
    }
  };

  const createProfile = async (event) => {
    event?.preventDefault();
    const nextProfileName = profileName.trim();
    if (nextProfileName.length < 2) {
      setStatus("Profile name must be at least 2 characters.");
      return;
    }

    setProfileLoading(true);
    setStatus(`Creating ${nextProfileName} profile...`);
    try {
      const createResponse = await fetch(`${API_BASE_URL}/api/resume/profiles`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ name: nextProfileName }),
      });
      if (!createResponse.ok) {
        const message = await readErrorMessage(createResponse, "Unable to create profile.");
        throw new Error(message);
      }

      const createdProfile = await createResponse.json();
      let saveError = "";
      try {
        const saveResponse = await fetch(`${API_BASE_URL}/api/resume/save`, {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            profile_id: createdProfile.id,
            template_id: selectedTemplate,
            section_color: currentSectionColor,
            resume,
          }),
        });
        if (!saveResponse.ok) {
          saveError = await readErrorMessage(saveResponse, "Profile created, but unable to save current resume data.");
        }
      } catch (error) {
        saveError = error.message;
      }

      try {
        window.localStorage.setItem(getProfileDraftKey(createdProfile.id), JSON.stringify(resume));
      } catch {
        // The in-memory editor state still switches to the new profile.
      }

      setResumeProfiles((current) => [
        { ...createdProfile, has_saved_draft: !saveError, latest_saved_at: saveError ? null : new Date().toISOString() },
        ...current.filter((profile) => String(profile.id) !== String(createdProfile.id)),
      ]);
      setActiveProfileId(String(createdProfile.id));
      setProfileName("");
      setHasSavedDraft(true);
      setStatus(
        saveError
          ? `${createdProfile.name} profile created. Database save failed, but a browser fallback draft was saved: ${saveError}`
          : `${createdProfile.name} profile created and current resume saved into it.`
      );
    } catch (error) {
      setStatus(`Unable to create profile: ${error.message}`);
    } finally {
      setProfileLoading(false);
    }
  };

  const updateBasics = (key, value) => {
    setResume((current) => ({ ...current, basics: { ...current.basics, [key]: value } }));
  };

  const handleProfilePhotoUpload = async (file) => {
    try {
      const photo = await buildProfilePhotoDataUrl(file);
      setResume((current) => ({
        ...current,
        basics: {
          ...current.basics,
          photo,
          photo_offset_y: 0,
        },
      }));
      setStatus("Profile photo added. The Profile Banner preview and PDF will use it instead of initials.");
    } catch (error) {
      setStatus(`Unable to add profile photo: ${error.message}`);
    }
  };

  const clearProfilePhoto = () => {
    setResume((current) => ({
      ...current,
      basics: {
        ...current.basics,
        photo: "",
        photo_offset_y: 0,
      },
    }));
    setStatus("Profile photo removed. The Profile Banner will fall back to initials.");
  };

  const updateLayoutOption = (key, value) => {
    setResume((current) => ({
      ...current,
      layout_options: {
        ...normalizeLayoutOptions(current.layout_options),
        [key]: value,
      },
    }));
  };

  const updateArrayItem = (section, index, key, value) => {
    setResume((current) => ({
      ...current,
      [section]: current[section].map((item, itemIndex) => (itemIndex === index ? { ...item, [key]: value } : item)),
    }));
  };

  const updateNestedItem = (section, index, key, itemIndex, value) => {
    setResume((current) => ({
      ...current,
      [section]: current[section].map((item, sectionIndex) => {
        if (sectionIndex !== index) return item;
        return {
          ...item,
          [key]: item[key].map((entry, nestedIndex) => (nestedIndex === itemIndex ? value : entry)),
        };
      }),
    }));
  };

  const addNestedItem = (section, index, key) => {
    setResume((current) => ({
      ...current,
      [section]: current[section].map((item, sectionIndex) => {
        if (sectionIndex !== index) return item;
        return {
          ...item,
          [key]: [...item[key], ""],
        };
      }),
    }));
  };

  const removeNestedItem = (section, index, key, itemIndex) => {
    setResume((current) => ({
      ...current,
      [section]: current[section].map((item, sectionIndex) => {
        if (sectionIndex !== index) return item;
        const nextItems = item[key].filter((_, nestedIndex) => nestedIndex !== itemIndex);
        return {
          ...item,
          [key]: nextItems.length ? nextItems : [""],
        };
      }),
    }));
  };

  const addItem = (section, factory) => {
    setResume((current) => ({ ...current, [section]: [...current[section], structuredClone(factory)] }));
  };

  const removeItem = (section, index) => {
    setResume((current) => ({ ...current, [section]: current[section].filter((_, itemIndex) => itemIndex !== index) }));
  };

  const selectedTemplateMeta = getTemplateMeta(selectedTemplate);
  const currentSectionColor = getTemplateSectionColor(selectedTemplate, templateSectionColors);

  const updateTemplateSectionColor = (templateId, nextColor) => {
    const normalizedColor = normalizeHexColor(nextColor, getTemplateMeta(templateId).defaultSectionColor);
    setTemplateSectionColors((current) => ({ ...current, [templateId]: normalizedColor }));
  };

  const resetTemplateSectionColor = (templateId) => {
    setTemplateSectionColors((current) => {
      const nextColors = { ...current };
      delete nextColors[templateId];
      return nextColors;
    });
  };

  const moveSection = (sectionKey, direction) => {
    setResume((current) => {
      const order = normalizeSectionOrder(current.section_order);
      const index = order.indexOf(sectionKey);
      const targetIndex = direction === "up" ? index - 1 : index + 1;
      if (index === -1 || targetIndex < 0 || targetIndex >= order.length) return current;
      const nextOrder = [...order];
      [nextOrder[index], nextOrder[targetIndex]] = [nextOrder[targetIndex], nextOrder[index]];
      return { ...current, section_order: nextOrder };
    });
  };

  const cleanPayload = () => ({
    ...resume,
    basics: {
      ...resume.basics,
      linkedin: normalizeUrl(resume.basics.linkedin) || null,
      github: normalizeUrl(resume.basics.github) || null,
      website: normalizeUrl(resume.basics.website) || null,
      photo: normalizePhotoDataUrl(resume.basics.photo) || null,
      photo_offset_y: normalizePhotoOffset(resume.basics.photo_offset_y),
    },
    skills: resume.skills
      .map((item) => ({
        ...item,
        name: String(item.name || "").trim(),
        items: item.items.map((entry) => String(entry || "").trim()).filter(Boolean),
      }))
      .filter((item) => item.name || item.items.length),
    experience: resume.experience
      .filter((item) =>
        hasAnyText(item.company, item.company_link, item.role, item.location, item.start_date, item.end_date, ...item.achievements)
      )
      .map((item) => ({
        ...item,
        company_link: normalizeUrl(item.company_link) || null,
        end_date: item.current ? null : item.end_date || null,
        achievements: item.achievements.filter(Boolean),
      })),
    projects: resume.projects
      .filter((item) => hasAnyText(item.name, item.tech_stack, item.link, ...item.highlights))
      .map((item) => ({
        ...item,
        year: String(item.year || "").trim(),
        link: normalizeUrl(item.link) || null,
        highlights: item.highlights.filter(Boolean),
      })),
    education: resume.education.filter((item) => hasAnyText(item.institution, item.degree, item.duration, item.score, item.location)),
    certifications: resume.certifications
      .map((item) => ({
        ...item,
        title: String(item.title || "").trim(),
        issuer: String(item.issuer || "").trim(),
        year: String(item.year || "").trim(),
      }))
      .filter((item) => hasAnyText(item.title, item.issuer, item.year)),
    layout_options: normalizeLayoutOptions(resume.layout_options),
    section_order: normalizeSectionOrder(resume.section_order),
  });
  const currentResumePayload = cleanPayload();
  const buildAtsRequestPayload = () => {
    const normalizedJobUrl = normalizeUrl(atsJobUrl);
    const trimmedJobDescription = atsJobDescription.trim();
    const trimmedTargetTitle = atsTargetTitle.trim();

    return {
      normalizedJobUrl,
      trimmedJobDescription,
      requestBody: {
        profile_id: activeProfileId ? Number(activeProfileId) : null,
        job_url: normalizedJobUrl || null,
        job_description: trimmedJobDescription || null,
        target_title: trimmedTargetTitle || null,
        resume: currentResumePayload,
      },
    };
  };

  const purchasePdfPlan = async (planId) => {
    setPaymentLoading(true);
    setPaymentMessage("Opening secure Razorpay Checkout...");

    try {
      await loadRazorpayCheckout();
      const orderResponse = await fetch(`${API_BASE_URL}/api/payments/orders`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ plan: planId }),
      });
      if (!orderResponse.ok) {
        const message = await readErrorMessage(orderResponse, "Unable to create payment order.");
        throw new Error(message);
      }

      const order = await orderResponse.json();
      const checkout = new window.Razorpay({
        key: order.key_id,
        amount: order.amount_paise,
        currency: order.currency,
        name: "ResuME",
        description: order.description,
        order_id: order.order_id,
        prefill: {
          email: order.customer_email || authUser?.email || "",
        },
        theme: {
          color: "#1e3a8a",
        },
        handler: async (paymentResult) => {
          setPaymentLoading(true);
          setPaymentMessage("Verifying payment...");
          try {
            const verifyResponse = await fetch(`${API_BASE_URL}/api/payments/verify`, {
              method: "POST",
              headers: authHeaders({ "Content-Type": "application/json" }),
              body: JSON.stringify({
                razorpay_order_id: paymentResult.razorpay_order_id,
                razorpay_payment_id: paymentResult.razorpay_payment_id,
                razorpay_signature: paymentResult.razorpay_signature,
              }),
            });
            if (!verifyResponse.ok) {
              const message = await readErrorMessage(verifyResponse, "Payment verification failed.");
              throw new Error(message);
            }

            const verified = await verifyResponse.json();
            setPaymentStatus(verified.payment);
            setPaymentModalOpen(false);
            setPaymentMessage("");
            setStatus("Payment verified. Download credits are ready.");
            await generateResume({ skipPaymentPrompt: true });
          } catch (error) {
            setPaymentMessage(error.message);
          } finally {
            setPaymentLoading(false);
          }
        },
        modal: {
          ondismiss: () => {
            setPaymentLoading(false);
            setPaymentMessage("Payment was cancelled.");
          },
        },
      });

      checkout.on("payment.failed", (response) => {
        setPaymentLoading(false);
        setPaymentMessage(response?.error?.description || "Payment failed. Please try again.");
      });

      checkout.open();
    } catch (error) {
      setPaymentMessage(error.message);
    } finally {
      setPaymentLoading(false);
    }
  };

  const generateResume = async ({ skipPaymentPrompt = false } = {}) => {
    setLoading(true);
    setStatus("Generating PDF...");
    try {
      const validationMessage = validateResumeForExport(currentResumePayload);
      if (validationMessage) {
        throw new Error(validationMessage);
      }

      if (!skipPaymentPrompt) {
        let latestPaymentStatus = paymentStatus;
        if (!latestPaymentStatus) {
          latestPaymentStatus = await refreshPaymentStatus();
        }
        const hasDownloadAccess = latestPaymentStatus?.exempt || Number(latestPaymentStatus?.remaining_downloads || 0) > 0;
        if (!hasDownloadAccess) {
          setPaymentModalOpen(true);
          setPaymentMessage("Choose a payment option to unlock PDF downloads.");
          setStatus("Payment is required before downloading a PDF.");
          return;
        }
      }

      const response = await fetch(`${API_BASE_URL}/api/resume/generate`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          profile_id: activeProfileId ? Number(activeProfileId) : null,
          template_id: selectedTemplate,
          section_color: currentSectionColor,
          resume: currentResumePayload,
        }),
      });
      if (!response.ok) {
        if (response.status === 402 && !skipPaymentPrompt) {
          setPaymentModalOpen(true);
          setPaymentMessage("Choose a payment option to unlock PDF downloads.");
          setStatus("Payment is required before downloading a PDF.");
          return;
        }
        const message = await readErrorMessage(response, "Unable to generate resume");
        throw new Error(message);
      }

      const blob = await response.blob();
      if (!blob.size) {
        throw new Error("The server returned an empty PDF file.");
      }

      const filename = getDownloadFilename(response.headers, buildFallbackResumeFilename(resume.basics.full_name));
      downloadBlob(blob, filename);
      await refreshPaymentStatus();
      setStatus("Resume generated successfully.");
    } catch (error) {
      const isNetworkError = error instanceof TypeError;
      const message = isNetworkError
        ? `Could not reach the backend at ${API_BASE_URL}. Make sure the API server is running and allowed by CORS.`
        : error.message;
      setStatus(`Generation failed: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const analyzeEditorResume = async () => {
    const { normalizedJobUrl, trimmedJobDescription, requestBody } = buildAtsRequestPayload();
    if (!normalizedJobUrl && !trimmedJobDescription) {
      setAtsStatus("Add a public job link or paste the job description so the ATS checker has target requirements.");
      return;
    }

    setAtsLoading(true);
    setAtsOptimization(null);
    setAtsStatus("Extracting job requirements, scoring resume evidence, and checking ATS formatting risk...");
    try {
      const response = await fetch(`${API_BASE_URL}/api/ats/analyze`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        let message = "Unable to analyze the job link.";
        try {
          const parsed = JSON.parse(errorText);
          message = parsed?.detail || message;
        } catch {
          message = errorText || message;
        }
        throw new Error(message);
      }

      const data = await response.json();
      setAtsResult(data);
      setAtsResultSource("editor");
      setAtsStatus("ATS analysis complete. Review missing requirements, formatting risk, and exact next edits below.");
    } catch (error) {
      setAtsResult(null);
      setAtsStatus(`ATS analysis failed: ${error.message}`);
    } finally {
      setAtsLoading(false);
    }
  };

  const analyzeUploadedPdf = async () => {
    const { normalizedJobUrl, trimmedJobDescription } = buildAtsRequestPayload();
    if (!normalizedJobUrl && !trimmedJobDescription) {
      setAtsStatus("Add a public job link or paste the job description before scoring an uploaded PDF.");
      return;
    }
    if (!atsResumePdf) {
      setAtsStatus("Choose a resume PDF to upload before running the PDF ATS score.");
      return;
    }

    setAtsLoading(true);
    setAtsOptimization(null);
    setAtsStatus(`Reading ${atsResumePdf.name}, extracting resume text, and scoring it against the target role...`);
    try {
      const formData = new FormData();
      if (activeProfileId) formData.append("profile_id", String(activeProfileId));
      if (normalizedJobUrl) formData.append("job_url", normalizedJobUrl);
      if (trimmedJobDescription) formData.append("job_description", trimmedJobDescription);
      if (atsTargetTitle.trim()) formData.append("target_title", atsTargetTitle.trim());
      formData.append("resume_pdf", atsResumePdf);

      const response = await fetch(`${API_BASE_URL}/api/ats/analyze-pdf`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });

      if (!response.ok) {
        const message = await readErrorMessage(response, "Unable to analyze the uploaded PDF.");
        throw new Error(message);
      }

      const data = await response.json();
      setAtsResult(data);
      setAtsResultSource("pdf");
      setAtsStatus("PDF ATS analysis complete. The score below is based on text extracted from the uploaded resume PDF.");
    } catch (error) {
      setAtsResult(null);
      setAtsStatus(`PDF ATS analysis failed: ${error.message}`);
    } finally {
      setAtsLoading(false);
    }
  };

  const analyzeAts = async (sourceOverride) => {
    const source = sourceOverride === "pdf" || sourceOverride === "editor" ? sourceOverride : atsReviewSource;
    if (source === "pdf") {
      setAtsReviewSource("pdf");
      await analyzeUploadedPdf();
      return;
    }
    setAtsReviewSource("editor");
    await analyzeEditorResume();
  };

  const autoFixResume = async () => {
    const { normalizedJobUrl, trimmedJobDescription, requestBody } = buildAtsRequestPayload();
    if (!normalizedJobUrl && !trimmedJobDescription) {
      setAtsStatus("Add a public job link or paste the job description before using Auto Fix.");
      return;
    }

    setAtsFixing(true);
    setAtsStatus("Rewriting the resume with ATS-safe edits, surfacing supported JD keywords, and recalculating the score...");
    try {
      const response = await fetch(`${API_BASE_URL}/api/ats/optimize`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ ...requestBody, target_score: 100 }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        let message = "Unable to optimize the resume.";
        try {
          const parsed = JSON.parse(errorText);
          message = parsed?.detail || message;
        } catch {
          message = errorText || message;
        }
        throw new Error(message);
      }

      const data = await response.json();
      const normalizedOptimizedResume = normalizeResumeData({
        ...data.optimized_resume,
        basics: {
          ...(data.optimized_resume?.basics || {}),
          photo: data.optimized_resume?.basics?.photo || resume.basics.photo || "",
          photo_offset_y: data.optimized_resume?.basics?.photo_offset_y ?? resume.basics.photo_offset_y ?? 0,
        },
      });
      const normalizedCurrentResume = normalizeResumeData(structuredClone(resume));
      const resumeChanged = JSON.stringify(normalizedOptimizedResume) !== JSON.stringify(normalizedCurrentResume);
      setResume(normalizedOptimizedResume);
      setAtsResult(data.analysis);
      setAtsResultSource("editor");
      setAtsOptimization(data);
      setStatus("ATS auto-fix updated the editor data. Review the refreshed resume content and preview.");
      try {
        window.localStorage.setItem(getProfileDraftKey(activeProfileId), JSON.stringify(normalizedOptimizedResume));
        setHasSavedDraft(true);
      } catch {
        // Ignore local save failures and keep the in-memory update.
      }
      try {
        await fetch(`${API_BASE_URL}/api/resume/save`, {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            profile_id: activeProfileId ? Number(activeProfileId) : null,
            template_id: selectedTemplate,
            section_color: currentSectionColor,
            resume: normalizedOptimizedResume,
          }),
        });
      } catch {
        // The optimize endpoint already stores the full optimization record.
      }
      const noScoreSafeEdits = data.applied_changes?.[0]?.startsWith("No score-safe");
      if (data.score_delta > 0) {
        setAtsStatus(`Auto-fix updated the live resume and improved the ATS score to ${data.updated_score}/100. This is the strongest score the tool could safely reach from your current resume evidence.`);
      } else if (noScoreSafeEdits) {
        setAtsStatus(`Auto-fix found no stronger score-safe rewrite from the current resume. The score remains ${data.updated_score}/100 until more matching evidence is added manually.`);
      } else {
        setAtsStatus(`Auto-fix updated the live resume and kept the ATS score at ${data.updated_score}/100. The score is already near the maximum the current resume can support safely.`);
      }
      if (resumeChanged) {
        setActiveWorkspace("editor");
      }
    } catch (error) {
      setAtsStatus(`Auto-fix failed: ${error.message}`);
      setStatus(`ATS auto-fix failed: ${error.message}`);
    } finally {
      setAtsFixing(false);
    }
  };

  const loadDemoData = () => {
    setResume(normalizeResumeData(structuredClone(sampleResume)));
    setAtsOptimization(null);
    setStatus(`Demo resume loaded into ${activeProfileLabel}. Save it to keep it in this profile.`);
  };

  const loadDemoJob = () => {
    setAtsTargetTitle(ATS_DEMO_ROLE.title);
    setAtsJobDescription(ATS_DEMO_ROLE.description);
    setAtsStatus("Demo job description loaded. You can run the ATS checker immediately or swap in a real posting.");
    setActiveWorkspace("ats");
  };

  const handleTemplateChange = (templateId) => {
    setSelectedTemplate(templateId);
    const templateMeta = getTemplateMeta(templateId);
    setStatus(`${templateMeta.name} selected. Your resume data stays the same while the preview and PDF design update.`);
  };

  const openAtsWorkspace = () => setActiveWorkspace("ats");
  const openEditorWorkspace = () => setActiveWorkspace("editor");

  if (authChecking || !authToken || !authUser) {
    return (
      <AuthScreen
        mode={authMode}
        email={authEmail}
        password={authPassword}
        otp={authOtp}
        status={authChecking ? "Checking your saved session..." : authStatus}
        loading={authLoading || authChecking}
        onModeChange={changeAuthMode}
        onEmailChange={setAuthEmail}
        onPasswordChange={setAuthPassword}
        onOtpChange={setAuthOtp}
        onSubmit={submitAuth}
      />
    );
  }

  return (
    <div className={`page-shell ${activeWorkspace === "ats" ? "page-shell-ats" : ""}`}>
      <AppNavbar
        activeWorkspace={activeWorkspace}
        authUser={authUser}
        selectedTemplate={selectedTemplate}
        templates={RESUME_TEMPLATES}
        resumeProfiles={resumeProfiles}
        activeProfileId={activeProfileId}
        profileName={profileName}
        profileLoading={profileLoading}
        loading={loading}
        hasSavedDraft={hasSavedDraft}
        onTemplateChange={handleTemplateChange}
        onProfileChange={setActiveProfileId}
        onProfileNameChange={setProfileName}
        onCreateProfile={createProfile}
        onSaveDraft={saveDraft}
        onGenerateResume={generateResume}
        onLoadDemoData={loadDemoData}
        onClearSavedDraft={clearSavedDraft}
        onLogout={logOut}
        onJumpToAts={openAtsWorkspace}
        onJumpToEditor={openEditorWorkspace}
        paymentStatus={paymentStatus}
      />

      <PaymentModal
        open={paymentModalOpen}
        plans={paymentPlans}
        loading={paymentLoading}
        message={paymentMessage}
        remainingDownloads={remainingDownloads}
        onClose={() => {
          if (!paymentLoading) setPaymentModalOpen(false);
        }}
        onPurchase={purchasePdfPlan}
      />

      <div className={`page-container ${activeWorkspace === "ats" ? "page-container-ats" : ""}`}>
        {activeWorkspace === "editor" ? (
          <>
            <header className="hero">
              <div className="hero-panel">
                <div className="hero-layout">
                  <div className="hero-main">
                    <p className="eyebrow">ATS Resume Builder</p>
                    <h1>Build ATS-safe resumes and verify them against real job requirements.</h1>
                    <p className="hero-text">Create a structured resume, export a clean PDF, and run a weighted ATS score that explains what is missing, what may hurt parsing, and what to edit next.</p>
                    <p className="status-text">{status}</p>
                  </div>

                  <div className="hero-summary">
                    <span>Workflow</span>
                    <strong>Editor, PDF export, and ATS scoring in one place</strong>
                    <p>
                      Compare your resume against a public posting or pasted job description with section scores, risk checks, and edit-ready recommendations.
                    </p>
                    <Button
                      variant="secondary"
                      className="hero-ats-link"
                      onClick={openAtsWorkspace}
                    >
                      Open ATS Workspace
                    </Button>
                  </div>
                </div>
              </div>
            </header>
          <main id="editor-workspace" className="workspace">
            <section className="editor-panel">
            <div className="panel-lead">
              <p className="eyebrow">Resume Builder</p>
              <h2>Resume Editor</h2>
              <p>Keep all resume writing and ordering changes here while ATS scoring lives in its own separate page.</p>
            </div>
            <SectionTitle title="Basics" />
            <div className="grid two-col">
              <Field label="Full Name" value={resume.basics.full_name} onChange={(value) => updateBasics("full_name", value)} />
              <Field label="Headline" value={resume.basics.headline} onChange={(value) => updateBasics("headline", value)} />
              <Field label="Email" value={resume.basics.email} onChange={(value) => updateBasics("email", value)} spellCheck={false} />
              <Field label="Phone" value={resume.basics.phone} onChange={(value) => updateBasics("phone", value)} spellCheck={false} />
              <Field label="Location" value={resume.basics.location} onChange={(value) => updateBasics("location", value)} />
              <Field label="LinkedIn URL" value={resume.basics.linkedin || ""} onChange={(value) => updateBasics("linkedin", value)} spellCheck={false} />
              <Field label="GitHub URL" value={resume.basics.github || ""} onChange={(value) => updateBasics("github", value)} spellCheck={false} />
              <Field label="Website URL" value={resume.basics.website || ""} onChange={(value) => updateBasics("website", value)} spellCheck={false} />
            </div>
            <PhotoUploadField
              label="Profile Photo"
              value={resume.basics.photo}
              fullName={resume.basics.full_name}
              photoOffset={resume.basics.photo_offset_y}
              onPhotoOffsetChange={(value) => updateBasics("photo_offset_y", normalizePhotoOffset(value))}
              onSelectFile={handleProfilePhotoUpload}
              onRemove={clearProfilePhoto}
            />
            <TextArea label="Professional Summary" value={resume.basics.summary} onChange={(value) => updateBasics("summary", value)} rows={5} enableBold />
            <p className="field-help">Spelling suggestions appear automatically from your browser while typing. Select text and use `B` or `Ctrl+B` to bold summary and bullet text.</p>

            <SectionTitle title="Section Order" />
            <SectionOrderEditor order={normalizeSectionOrder(resume.section_order)} onMove={moveSection} />

            <SectionTitle title="Template Styling" />
            <TemplateStyleEditor
              templateName={selectedTemplateMeta.name}
              color={currentSectionColor}
              defaultColor={selectedTemplateMeta.defaultSectionColor}
              onColorChange={(nextColor) => updateTemplateSectionColor(selectedTemplate, nextColor)}
              onReset={() => resetTemplateSectionColor(selectedTemplate)}
            />

            <SectionTitle title="Skills" actionLabel="Add Skill Group" onAction={() => addItem("skills", emptySkill)} />
            {resume.skills.map((item, index) => (
              <Card key={`skill-${index}`}>
                <div className="card-head">
                  <strong>Skill Group {index + 1}</strong>
                  <Button variant="ghost" onClick={() => removeItem("skills", index)}>Remove</Button>
                </div>
                <Field label="Category Name" value={item.name} onChange={(value) => updateArrayItem("skills", index, "name", value)} />
                <CommaSeparatedSkillsField
                  label="Comma-separated Skills"
                  items={item.items}
                  onChange={(items) => updateArrayItem("skills", index, "items", items)}
                />
              </Card>
            ))}

            <SectionTitle title="Experience" actionLabel="Add Experience" onAction={() => addItem("experience", emptyExperience)} />
            {resume.experience.map((item, index) => (
              <Card key={`experience-${index}`}>
                <div className="card-head">
                  <strong>Experience {index + 1}</strong>
                  <Button variant="ghost" onClick={() => removeItem("experience", index)}>Remove</Button>
                </div>
                <div className="grid two-col">
                  <Field label="Company" value={item.company} onChange={(value) => updateArrayItem("experience", index, "company", value)} />
                  <Field label="Company Link" value={item.company_link || ""} onChange={(value) => updateArrayItem("experience", index, "company_link", value)} spellCheck={false} />
                  <Field label="Role" value={item.role} onChange={(value) => updateArrayItem("experience", index, "role", value)} />
                  <Field label="Location" value={item.location} onChange={(value) => updateArrayItem("experience", index, "location", value)} />
                  <Field label="Start Date" value={item.start_date} onChange={(value) => updateArrayItem("experience", index, "start_date", value)} spellCheck={false} />
                  <Field label="End Date" value={item.end_date || ""} onChange={(value) => updateArrayItem("experience", index, "end_date", value)} disabled={item.current} spellCheck={false} />
                </div>
                <label className="checkbox-row">
                  <input type="checkbox" checked={item.current} onChange={(event) => updateArrayItem("experience", index, "current", event.target.checked)} />
                  Current role
                </label>
                <BulletListEditor
                  label="Achievements"
                  items={item.achievements}
                  addLabel="Add Bullet"
                  onChange={(bulletIndex, value) => updateNestedItem("experience", index, "achievements", bulletIndex, value)}
                  onAdd={() => addNestedItem("experience", index, "achievements")}
                  onRemove={(bulletIndex) => removeNestedItem("experience", index, "achievements", bulletIndex)}
                />
              </Card>
            ))}

            <SectionTitle title="Projects" actionLabel="Add Project" onAction={() => addItem("projects", emptyProject)} />
            {resume.projects.map((item, index) => (
              <Card key={`project-${index}`}>
                <div className="card-head">
                  <strong>Project {index + 1}</strong>
                  <Button variant="ghost" onClick={() => removeItem("projects", index)}>Remove</Button>
                </div>
                <div className="grid two-col">
                  <Field label="Project Name" value={item.name} onChange={(value) => updateArrayItem("projects", index, "name", value)} />
                  <Field label="Tech Stack" value={item.tech_stack} onChange={(value) => updateArrayItem("projects", index, "tech_stack", value)} />
                  <Field label="Year" value={item.year || ""} onChange={(value) => updateArrayItem("projects", index, "year", value)} spellCheck={false} />
                  <Field label="Project Link" value={item.link || ""} onChange={(value) => updateArrayItem("projects", index, "link", value)} spellCheck={false} />
                </div>
                <BulletListEditor
                  label="Highlights"
                  items={item.highlights}
                  addLabel="Add Bullet"
                  onChange={(bulletIndex, value) => updateNestedItem("projects", index, "highlights", bulletIndex, value)}
                  onAdd={() => addNestedItem("projects", index, "highlights")}
                  onRemove={(bulletIndex) => removeNestedItem("projects", index, "highlights", bulletIndex)}
                />
              </Card>
            ))}

            <SectionTitle title="Education" actionLabel="Add Education" onAction={() => addItem("education", emptyEducation)} />
            {resume.education.map((item, index) => (
              <Card key={`education-${index}`}>
                <div className="card-head">
                  <strong>Education {index + 1}</strong>
                  <Button variant="ghost" onClick={() => removeItem("education", index)}>Remove</Button>
                </div>
                <div className="grid two-col">
                  <Field label="Institution" value={item.institution} onChange={(value) => updateArrayItem("education", index, "institution", value)} />
                  <Field label="Degree" value={item.degree} onChange={(value) => updateArrayItem("education", index, "degree", value)} />
                  <Field label="Duration" value={item.duration} onChange={(value) => updateArrayItem("education", index, "duration", value)} />
                  <Field label="Score / CGPA" value={item.score || ""} onChange={(value) => updateArrayItem("education", index, "score", value)} />
                  <Field label="Mode / Location" value={item.location || ""} onChange={(value) => updateArrayItem("education", index, "location", value)} />
                </div>
              </Card>
            ))}

            <SectionTitle title="Certifications" actionLabel="Add Certification" onAction={() => addItem("certifications", emptyCertification)} />
            {selectedTemplate === "executive-elegance" ? (
              <label className="checkbox-row template-section-option">
                <input
                  type="checkbox"
                  checked={Boolean(resume.layout_options?.executive_certifications_in_sidebar)}
                  onChange={(event) => updateLayoutOption("executive_certifications_in_sidebar", event.target.checked)}
                />
                <span>
                  <strong>Move certifications to sidebar</strong>
                  <small>Unchecked keeps certifications as a normal main section.</small>
                </span>
              </label>
            ) : null}
            {resume.certifications.map((item, index) => (
              <Card key={`certification-${index}`}>
                <div className="card-head">
                  <strong>Certification {index + 1}</strong>
                  <Button variant="ghost" onClick={() => removeItem("certifications", index)}>Remove</Button>
                </div>
                <div className="grid two-col">
                  <Field label="Title" value={item.title} onChange={(value) => updateArrayItem("certifications", index, "title", value)} />
                  <Field label="Issuer" value={item.issuer} onChange={(value) => updateArrayItem("certifications", index, "issuer", value)} />
                  <Field label="Year" value={item.year} onChange={(value) => updateArrayItem("certifications", index, "year", value)} />
                </div>
              </Card>
            ))}
            </section>

            <section className="preview-panel">
              <SectionTitle title="Resume Preview" />
              <ResumePreviewPanel resume={resume} selectedTemplate={selectedTemplate} sectionColor={currentSectionColor} />
            </section>
          </main>
          </>
        ) : (
          <main id="ats-workspace" className="ats-page-flow">
            <header className="hero hero-ats-mode">
              <div className="hero-panel hero-panel-ats">
                <div className="hero-layout">
                  <div className="hero-main">
                    <p className="eyebrow">ATS Resume Builder</p>
                    <h1>Build ATS-safe resumes and verify them against real job requirements.</h1>
                    <p className="hero-text">Create a structured resume, export a clean PDF, and run a weighted ATS score that explains what is missing, what may hurt parsing, and what to edit next.</p>
                    <p className="status-text">{status}</p>
                  </div>

                  <div className="hero-summary">
                    <span>Workflow</span>
                    <strong>ATS workspace with live editor data</strong>
                    <p>
                      Run ATS analysis in a dedicated page-style workspace while still using the current resume data from the editor.
                    </p>
                    <Button
                      variant="secondary"
                      className="hero-ats-link"
                      onClick={openEditorWorkspace}
                    >
                      Open Editor Workspace
                    </Button>
                  </div>
                </div>
              </div>
            </header>

            <ATSWorkspaceSection
              atsLoading={atsLoading}
              atsFixing={atsFixing}
              atsStatus={atsStatus}
              atsTargetTitle={atsTargetTitle}
              atsJobUrl={atsJobUrl}
              atsJobDescription={atsJobDescription}
              atsResumePdf={atsResumePdf}
              atsReviewSource={atsReviewSource}
              atsResult={atsResult}
              atsResultSource={atsResultSource}
              atsOptimization={atsOptimization}
              currentResume={currentResumePayload}
              onTargetTitleChange={setAtsTargetTitle}
              onJobUrlChange={setAtsJobUrl}
              onJobDescriptionChange={setAtsJobDescription}
              onResumePdfChange={(file) => {
                setAtsResumePdf(file);
                setAtsReviewSource(file ? "pdf" : "editor");
              }}
              onReviewSourceChange={setAtsReviewSource}
              onAnalyze={analyzeAts}
              onAutoFix={autoFixResume}
              onLoadDemoJob={loadDemoJob}
            />
          </main>
        )}
      </div>
    </div>
  );
}

function AuthScreen({
  mode,
  email,
  password,
  otp,
  status,
  loading,
  onModeChange,
  onEmailChange,
  onPasswordChange,
  onOtpChange,
  onSubmit,
}) {
  const isSignUp = mode === "signup";
  const isSignupVerify = mode === "signup-verify";
  const isForgot = mode === "forgot";
  const isResetVerify = mode === "reset-verify";
  const needsOtp = isSignupVerify || isResetVerify;
  const needsPassword = !isForgot && !isSignupVerify;
  const tabMode = isSignUp || isSignupVerify ? "signup" : isForgot || isResetVerify ? "forgot" : "signin";
  const heading = isSignupVerify
    ? "Verify your resume account."
    : isForgot || isResetVerify
      ? "Reset your password."
      : isSignUp
        ? "Create your resume account."
        : "Sign in to your resume workspace.";
  const buttonLabel = loading
    ? "Please wait..."
    : isSignupVerify
      ? "Verify Account"
      : isForgot
        ? "Send Reset Code"
        : isResetVerify
          ? "Update Password"
          : isSignUp
            ? "Create Account"
            : "Sign In";

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="auth-copy">
          <p className="eyebrow">ATS Resume Builder</p>
          <h1>{heading}</h1>
          <p>
            Manage your drafts, PDF exports, and ATS checks securely from one workspace.
          </p>
        </div>

        <form className="auth-card" onSubmit={onSubmit}>
          <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              className={tabMode === "signin" ? "auth-tab is-active" : "auth-tab"}
              onClick={() => onModeChange("signin")}
            >
              Sign In
            </button>
            <button
              type="button"
              className={tabMode === "signup" ? "auth-tab is-active" : "auth-tab"}
              onClick={() => onModeChange("signup")}
            >
              Sign Up
            </button>
            <button
              type="button"
              className={tabMode === "forgot" ? "auth-tab is-active" : "auth-tab"}
              onClick={() => onModeChange("forgot")}
            >
              Reset Password
            </button>
          </div>

          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              autoComplete="email"
              spellCheck={false}
              onChange={(event) => onEmailChange(event.target.value)}
              required
            />
          </label>

          {needsOtp ? (
            <label className="field">
              <span>Verification Code</span>
              <input
                type="text"
                value={otp}
                inputMode="numeric"
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                autoComplete="one-time-code"
                spellCheck={false}
                onChange={(event) => onOtpChange(event.target.value.replace(/\D/g, "").slice(0, 6))}
                required
              />
            </label>
          ) : null}

          {needsPassword ? (
            <label className="field">
              <span>{isResetVerify ? "New Password" : "Password"}</span>
              <input
                type="password"
                value={password}
                minLength={8}
                maxLength={128}
                autoComplete={isSignUp || isResetVerify ? "new-password" : "current-password"}
                onChange={(event) => onPasswordChange(event.target.value)}
                required
              />
            </label>
          ) : null}

          <Button variant="primary" type="submit" disabled={loading}>
            {buttonLabel}
          </Button>

          <p className="auth-status">{status}</p>
        </form>
      </section>
    </main>
  );
}

function formatRupees(amountPaise) {
  return `Rs. ${Math.round(Number(amountPaise || 0) / 100)}`;
}

function PaymentModal({
  open,
  plans,
  loading,
  message,
  remainingDownloads,
  onClose,
  onPurchase,
}) {
  if (!open) return null;

  const singlePlan = plans.find((plan) => plan.id === "single_pdf");
  const monthlyPlan = plans.find((plan) => plan.id === "monthly_pack");
  const orderedPlans = [singlePlan, monthlyPlan].filter(Boolean);

  return (
    <div className="payment-modal-backdrop" role="presentation">
      <section className="payment-modal" role="dialog" aria-modal="true" aria-labelledby="payment-modal-title">
        <div className="payment-modal-head">
          <div>
            <p className="eyebrow">Secure Payment</p>
            <h2 id="payment-modal-title">Unlock PDF download</h2>
          </div>
          <button type="button" className="payment-modal-close" onClick={onClose} disabled={loading} aria-label="Close payment dialog">
            X
          </button>
        </div>

        <p className="payment-modal-copy">
          Pay with UPI QR, credit card, debit card, net banking, or wallet through Razorpay Checkout.
        </p>

        <div className="payment-plan-grid">
          {orderedPlans.map((plan) => (
            <article className="payment-plan" key={plan.id}>
              <span>{plan.label}</span>
              <strong>{formatRupees(plan.amount_paise)}</strong>
              <p>
                {plan.id === "monthly_pack"
                  ? `${plan.download_credits} PDF downloads valid for ${plan.valid_days} days.`
                  : "One PDF download credit."}
              </p>
              <Button variant={plan.id === "monthly_pack" ? "primary" : "secondary"} onClick={() => onPurchase(plan.id)} disabled={loading}>
                {loading ? "Please wait..." : plan.id === "monthly_pack" ? "Buy Monthly Pack" : "Pay and Download"}
              </Button>
            </article>
          ))}
        </div>

        <p className="payment-status-line">
          Current PDF credits: <strong>{remainingDownloads}</strong>
        </p>
        {message ? <p className="payment-message">{message}</p> : null}
      </section>
    </div>
  );
}

function AppNavbar({
  activeWorkspace,
  authUser,
  loading,
  hasSavedDraft,
  selectedTemplate,
  templates,
  resumeProfiles,
  activeProfileId,
  profileName,
  profileLoading,
  onTemplateChange,
  onProfileChange,
  onProfileNameChange,
  onCreateProfile,
  onSaveDraft,
  onGenerateResume,
  onLoadDemoData,
  onClearSavedDraft,
  onLogout,
  onJumpToAts,
  onJumpToEditor,
  paymentStatus,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const paymentLabel = paymentStatus?.exempt
    ? "PDF: Admin"
    : `PDF Credits: ${Number(paymentStatus?.remaining_downloads || 0)}`;
  const closeMenu = () => setMenuOpen(false);
  const runAndClose = (handler) => {
    closeMenu();
    handler();
  };

  useEffect(() => {
    if (!menuOpen) {
      return undefined;
    }

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        closeMenu();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [menuOpen]);

  return (
    <nav className="app-navbar">
      <div className="app-navbar-inner">
        <div className="app-navbar-brand">
          <span className="app-navbar-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false">
              <path d="M8 3.5h6l4.5 4.5V20a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6.5 20V5A1.5 1.5 0 0 1 8 3.5Z" />
              <path d="M14 3.5V8h4.5" />
              <path d="M9 11.5h6" />
              <path d="M9 15h6" />
            </svg>
          </span>
          <div className="app-navbar-brand-copy">
            <span className="app-navbar-label">ATS Resume Builder</span>
            <strong>Save, export &amp; manage</strong>
          </div>
        </div>

        <button
          type="button"
          className={`mobile-menu-toggle ${menuOpen ? "is-open" : ""}`}
          aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-controls="app-navbar-actions"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((current) => !current)}
        >
          <span />
          <span />
          <span />
        </button>

        <button
          type="button"
          className={`app-navbar-backdrop ${menuOpen ? "is-open" : ""}`}
          aria-label="Close navigation menu"
          onClick={closeMenu}
        />

        <div id="app-navbar-actions" className={`app-navbar-actions ${menuOpen ? "is-open" : ""}`}>
          <div className="mobile-menu-head">
            <div>
              <span className="mobile-menu-kicker">Menu</span>
              <strong>Resume actions</strong>
            </div>
            <button type="button" className="mobile-menu-close" aria-label="Close navigation menu" onClick={closeMenu}>
              x
            </button>
          </div>

          <Button variant="nav" className={activeWorkspace === "editor" ? "nav-pill-active" : ""} onClick={() => runAndClose(onJumpToEditor)}>
            Editor
          </Button>
          <Button variant="nav" className={activeWorkspace === "ats" ? "nav-pill-active" : ""} onClick={() => runAndClose(onJumpToAts)}>
            ATS Test
          </Button>
          <ProfilePicker
            profiles={resumeProfiles}
            activeProfileId={activeProfileId}
            profileName={profileName}
            profileLoading={profileLoading}
            onProfileChange={onProfileChange}
            onProfileNameChange={onProfileNameChange}
            onCreateProfile={onCreateProfile}
          />
          <TemplatePicker selectedTemplate={selectedTemplate} templates={templates} onTemplateChange={onTemplateChange} />
          <SaveActionsMenu
            hasSavedDraft={hasSavedDraft}
            onSaveDraft={onSaveDraft}
            onClearSavedDraft={onClearSavedDraft}
            onLoadDemoData={onLoadDemoData}
            onActionComplete={closeMenu}
          />
          <span className="app-navbar-payment">{paymentLabel}</span>
          <Button variant="nav" className="app-navbar-download" onClick={() => runAndClose(onGenerateResume)} disabled={loading}>
            {loading ? "Generating..." : "Download PDF"}
          </Button>
          <Button variant="nav" className="app-navbar-account" onClick={() => runAndClose(onLogout)} title={`Signed in as ${authUser.email}`}>
            Logout
          </Button>
        </div>
      </div>
    </nav>
  );
}

function ATSWorkspaceSection({
  atsLoading,
  atsFixing,
  atsStatus,
  atsTargetTitle,
  atsJobUrl,
  atsJobDescription,
  atsResumePdf,
  atsReviewSource,
  atsResult,
  atsResultSource,
  atsOptimization,
  currentResume,
  onTargetTitleChange,
  onJobUrlChange,
  onJobDescriptionChange,
  onResumePdfChange,
  onReviewSourceChange,
  onAnalyze,
  onAutoFix,
  onLoadDemoJob,
}) {
  const filledSectionCount = [
    currentResume.basics.summary?.trim(),
    currentResume.skills.length,
    currentResume.experience.length,
    currentResume.projects.length,
    currentResume.education.length,
    currentResume.certifications.length,
  ].filter(Boolean).length;
  const reviewPdf = atsReviewSource === "pdf";
  const selectedResumeLabel = reviewPdf ? "Uploaded PDF" : "Resume Editor";

  return (
    <section id="ats-workbench" className="ats-section">
      <div className="ats-shell">
        <div className="ats-shell-head">
          <div className="ats-shell-copy">
            <p className="eyebrow">ATS Workspace</p>
            <h2>Run a clean recruiter-style ATS check in its own dedicated space.</h2>
            <p>
              Paste a public job URL, add a role title, or drop in the description directly. The result stays organized here so your
              resume editor and preview remain focused.
            </p>
          </div>

          <div className="ats-shell-summary">
            <div className="ats-summary-card">
              <span>Current Flow</span>
              <strong>1. Add the target role 2. Run the ATS test 3. Review gaps and exact edits</strong>
            </div>
            <div className="ats-summary-card">
              <span>What it checks</span>
              <strong>Job matching, formatting risk, missing keywords, proof in resume sections, and next-step improvements</strong>
            </div>
          </div>
        </div>

        <div className="ats-workbench-grid">
          <div className="ats-composer-card">
            <div className="ats-composer-topline">
              <div>
                <p className="ats-kicker">ATS Test</p>
                <h3>Job Target Input</h3>
              </div>
              <span className="ats-workbench-pill">Reviewing {selectedResumeLabel}</span>
            </div>

            <div className="ats-source-switch" role="radiogroup" aria-label="Choose resume source for ATS review">
              <button
                type="button"
                className={`ats-source-option ${!reviewPdf ? "is-active" : ""}`}
                onClick={() => onReviewSourceChange("editor")}
                aria-pressed={!reviewPdf}
              >
                <span>Resume Editor</span>
                <strong>Score current editor data</strong>
              </button>
              <button
                type="button"
                className={`ats-source-option ${reviewPdf ? "is-active" : ""}`}
                onClick={() => onReviewSourceChange("pdf")}
                disabled={!atsResumePdf}
                aria-pressed={reviewPdf}
              >
                <span>Uploaded PDF</span>
                <strong>{atsResumePdf ? "Score uploaded PDF text" : "Upload PDF to enable"}</strong>
              </button>
            </div>

            <div className="grid two-col ats-input-grid">
              <Field label="Target Role Title" value={atsTargetTitle} onChange={onTargetTitleChange} />
              <label className="field ats-url-field">
                <span>Public Job URL</span>
                <input
                  value={atsJobUrl}
                  spellCheck={false}
                  autoCorrect="off"
                  autoCapitalize="off"
                  placeholder="Paste a public job posting URL"
                  onChange={(event) => onJobUrlChange(event.target.value)}
                />
              </label>
            </div>

            <TextArea
              label="Job Description"
              value={atsJobDescription}
              onChange={onJobDescriptionChange}
              rows={8}
              spellCheck={true}
            />

            <div className="ats-pdf-upload-card">
              <div className="ats-pdf-upload-copy">
                <p className="ats-kicker">Resume PDF Upload</p>
                <h4>Score an existing resume PDF</h4>
                <p>{atsResumePdf ? atsResumePdf.name : "Upload a text-based PDF resume and score it against the same target role."}</p>
              </div>
              <div className="ats-pdf-upload-actions">
                <label className="ui-btn ui-btn-secondary ats-file-button">
                  Choose PDF
                  <input
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={(event) => onResumePdfChange(event.target.files?.[0] || null)}
                  />
                </label>
                {atsResumePdf ? (
                  <Button variant="ghost" onClick={() => onResumePdfChange(null)}>
                    Clear
                  </Button>
                ) : null}
                <Button variant="secondary" onClick={() => onAnalyze("pdf")} disabled={atsLoading || !atsResumePdf}>
                  {atsLoading && reviewPdf ? "Reading..." : "Review PDF"}
                </Button>
              </div>
            </div>

            <div className="ats-toolbar">
              <Button
                variant="primary"
                className="ats-action-btn"
                onClick={() => onAnalyze(atsReviewSource)}
                disabled={atsLoading || (reviewPdf && !atsResumePdf)}
              >
                {atsLoading ? (reviewPdf ? "Reading PDF..." : "Analyzing...") : `Run ATS Test on ${selectedResumeLabel}`}
              </Button>
              <Button variant="secondary" className="ats-action-btn" onClick={onAutoFix} disabled={atsLoading || atsFixing || reviewPdf}>
                {atsFixing ? "Fixing..." : "Auto Fix Score"}
              </Button>
              <Button variant="secondary" onClick={onLoadDemoJob}>
                Load Demo Job
              </Button>
            </div>

            <div className="ats-helper-stack">
              <p className="field-help ats-help">
                If URL scraping fails, the pasted job description is used automatically for scoring.
              </p>
              <p className="field-help ats-help">
                Auto Fix is available only for Resume Editor reviews because it updates the live editor data.
              </p>
              <p className="field-help ats-help">
                PDF scoring works best with exported text PDFs; scanned image resumes may not have readable text.
              </p>
            </div>
          </div>

          <div className="ats-sidekick-card">
            <div className="ats-sidekick-block">
              <p className="ats-kicker">Selected Resume</p>
              <h3>{reviewPdf ? "Uploaded PDF used for ATS" : "Current editor data used for ATS"}</h3>
              <div className="ats-resume-sync-card">
                <strong>{reviewPdf ? atsResumePdf?.name || "No PDF selected" : currentResume.basics.full_name || "Untitled resume"}</strong>
                <p>{reviewPdf ? "The ATS score will use text extracted from the selected PDF." : currentResume.basics.headline?.trim() || "No headline added yet."}</p>
                <div className="ats-sync-metrics">
                  {reviewPdf ? (
                    <>
                      <span>PDF review</span>
                      <span>{atsResumePdf ? "file ready" : "upload needed"}</span>
                    </>
                  ) : (
                    <>
                      <span>{currentResume.experience.length} experience</span>
                      <span>{currentResume.projects.length} projects</span>
                      <span>{currentResume.skills.length} skill groups</span>
                      <span>{filledSectionCount} filled sections</span>
                    </>
                  )}
                </div>
                <p className="ats-sync-note">
                  {reviewPdf
                    ? "Run ATS Test will score the uploaded PDF, not the resume editor."
                    : "Run ATS Test will score the latest content from the editor section."}
                </p>
              </div>
            </div>

            <div className="ats-sidekick-block">
              <p className="ats-kicker">Live Status</p>
              <h3>ATS analysis state</h3>
              <p className="ats-sidekick-status">{atsStatus}</p>
            </div>

            <div className="ats-sidekick-block">
              <p className="ats-kicker">Best Use</p>
              <ul className="ats-checklist">
                <li>Use a public job URL when possible for the most accurate requirement extraction.</li>
                <li>Paste the full job description when a site blocks scraping or hides important keywords.</li>
                <li>Keep your editor updated first, then rerun this section to compare improvements.</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="ats-results-stage">
          {atsResult ? (
            <>
              <div className="ats-results-head">
                <div>
                  <p className="ats-kicker">Results</p>
                  <h3>Simple ATS dashboard</h3>
                </div>
                <div className="ats-results-actions">
                  <span className="ats-workbench-pill is-result">
                    {atsResultSource === "pdf" ? "Uploaded PDF analysis loaded" : "Latest editor analysis loaded"}
                  </span>
                </div>
              </div>
              <ATSSimpleResultPanel
                result={atsResult}
                optimization={atsOptimization}
                currentResume={currentResume}
                onAutoFix={onAutoFix}
                autoFixDisabled={atsLoading || atsFixing || atsResultSource === "pdf"}
                autoFixing={atsFixing}
                resultSource={atsResultSource}
              />
            </>
          ) : (
            <div className="ats-empty-state">
              <p className="ats-kicker">Ready</p>
              <h3>Your ATS dashboard will appear here.</h3>
              <p>Run the ATS test from this section to see the score, critical gaps, matched skills, and clear next steps.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function ProfilePicker({ profiles, activeProfileId, profileName, profileLoading, onProfileChange, onProfileNameChange, onCreateProfile }) {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createSubmitted, setCreateSubmitted] = useState(false);
  const pickerRef = useRef(null);
  const activeProfile = profiles.find((profile) => String(profile.id) === String(activeProfileId)) || profiles[0] || null;

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (pickerRef.current && !pickerRef.current.contains(event.target)) {
        setOpen(false);
        setCreating(false);
        setCreateSubmitted(false);
      }
    };

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
        setCreating(false);
        setCreateSubmitted(false);
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    if (createSubmitted && !profileLoading && !profileName.trim()) {
      setOpen(false);
      setCreating(false);
      setCreateSubmitted(false);
    }
  }, [createSubmitted, profileLoading, profileName]);

  const chooseProfile = (profileId) => {
    onProfileChange(String(profileId));
    setOpen(false);
    setCreating(false);
    setCreateSubmitted(false);
  };

  const submitProfile = async (event) => {
    event.preventDefault();
    setCreateSubmitted(true);
    await onCreateProfile(event);
  };

  return (
    <div className={`profile-picker ${open ? "is-open" : ""}`} ref={pickerRef}>
      <span className="profile-picker-label">Profile</span>
      <button
        type="button"
        className="profile-picker-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Select resume profile"
        disabled={profileLoading}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="profile-picker-value">{activeProfile?.name || "Choose profile"}</span>
        <span className="profile-picker-icon" aria-hidden="true">
          <svg viewBox="0 0 12 12" focusable="false">
            <path d="M2 4.5 6 8l4-3.5" />
          </svg>
        </span>
      </button>

      {open ? (
        <div className="profile-picker-menu" role="listbox" aria-label="Resume profiles">
          {profiles.map((profile) => (
            <button
              key={profile.id}
              type="button"
              role="option"
              aria-selected={String(profile.id) === String(activeProfileId)}
              className={`profile-picker-option ${String(profile.id) === String(activeProfileId) ? "is-selected" : ""}`}
              onClick={() => chooseProfile(profile.id)}
            >
              <span>{profile.name}</span>
              {String(profile.id) === String(activeProfileId) ? <span className="profile-picker-check">Active</span> : null}
            </button>
          ))}

          <div className="profile-picker-divider" />

          {creating ? (
            <form className="profile-create-form" onSubmit={submitProfile}>
              <input
                type="text"
                value={profileName}
                placeholder="Profile name"
                maxLength={80}
                autoFocus
                onChange={(event) => onProfileNameChange(event.target.value)}
                disabled={profileLoading}
              />
              <Button variant="primary" size="small" type="submit" disabled={profileLoading || profileName.trim().length < 2}>
                {profileLoading ? "Saving..." : "Save"}
              </Button>
            </form>
          ) : (
            <button type="button" className="profile-picker-option profile-picker-create" onClick={() => {
              setCreating(true);
              setCreateSubmitted(false);
            }}>
              <span className="profile-plus" aria-hidden="true">+</span>
              <span>New profile</span>
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}

function SaveActionsMenu({ hasSavedDraft, onSaveDraft, onClearSavedDraft, onLoadDemoData, onActionComplete }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const runAction = (handler) => {
    setOpen(false);
    handler();
    onActionComplete?.();
  };

  return (
    <div className={`save-menu ${open ? "is-open" : ""}`} ref={menuRef}>
      <button
        type="button"
        className="ui-btn ui-btn-nav save-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>Save Data</span>
        <span className="save-menu-icon" aria-hidden="true">
          <svg viewBox="0 0 12 12" focusable="false">
            <path d="M2 4.5 6 8l4-3.5" />
          </svg>
        </span>
      </button>

      {open ? (
        <div className="save-menu-list" role="menu" aria-label="Save actions">
          <button type="button" role="menuitem" className="save-menu-option" onClick={() => runAction(onSaveDraft)}>
            Save Data
          </button>
          <button
            type="button"
            role="menuitem"
            className="save-menu-option"
            onClick={() => runAction(onClearSavedDraft)}
            disabled={!hasSavedDraft}
          >
            Clear Saved
          </button>
          <button type="button" role="menuitem" className="save-menu-option" onClick={() => runAction(onLoadDemoData)}>
            Load Demo Data
          </button>
        </div>
      ) : null}
    </div>
  );
}

function TemplatePicker({ selectedTemplate, templates, onTemplateChange }) {
  const [open, setOpen] = useState(false);
  const pickerRef = useRef(null);
  const activeTemplate = templates.find((template) => template.id === selectedTemplate) || templates[0];

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (pickerRef.current && !pickerRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const chooseTemplate = (templateId) => {
    onTemplateChange(templateId);
    setOpen(false);
  };

  return (
    <div className={`template-picker ${open ? "is-open" : ""}`} ref={pickerRef}>
      <span className="template-picker-label">Template</span>
      <button
        type="button"
        className="template-picker-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Select resume template"
        onClick={() => setOpen((current) => !current)}
      >
        <span className="template-picker-value">{activeTemplate?.name || "Choose template"}</span>
        <span className="template-picker-icon" aria-hidden="true">
          <svg viewBox="0 0 12 12" focusable="false">
            <path d="M2 4.5 6 8l4-3.5" />
          </svg>
        </span>
      </button>

      {open ? (
        <div className="template-picker-menu" role="listbox" aria-label="Resume templates">
          {templates.map((template) => (
            <button
              key={template.id}
              type="button"
              role="option"
              aria-selected={template.id === selectedTemplate}
              className={`template-picker-option ${template.id === selectedTemplate ? "is-selected" : ""}`}
              onClick={() => chooseTemplate(template.id)}
            >
              <span>{template.name}</span>
              {template.id === selectedTemplate ? <span className="template-picker-check">Active</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Button({ variant = "secondary", size = "default", className = "", type = "button", children, ...props }) {
  const classes = ["ui-btn", `ui-btn-${variant}`, size === "small" ? "ui-btn-small" : "", className].filter(Boolean).join(" ");
  return (
    <button type={type} className={classes} {...props}>
      {children}
    </button>
  );
}

function SectionTitle({ title, actionLabel, onAction }) {
  return (
    <div className="section-title">
      <h2>{title}</h2>
      {actionLabel ? <Button variant="secondary" size="small" onClick={onAction}>{actionLabel}</Button> : null}
    </div>
  );
}

function SectionOrderEditor({ order, onMove }) {
  return (
    <div className="editor-card section-order-card">
      {order.map((sectionKey, index) => (
        <div className="section-order-row" key={sectionKey}>
          <span>{SECTION_LABELS[sectionKey]}</span>
          <div className="section-order-actions">
            <Button variant="secondary" size="small" onClick={() => onMove(sectionKey, "up")} disabled={index === 0}>
              Move Up
            </Button>
            <Button variant="secondary" size="small" onClick={() => onMove(sectionKey, "down")} disabled={index === order.length - 1}>
              Move Down
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

function TemplateStyleEditor({ templateName, color, defaultColor, onColorChange, onReset }) {
  return (
    <div className="editor-card template-style-card">
      <div className="template-style-copy">
        <strong>{templateName}</strong>
        <p>Choose the theme color used for accents, links, rules, and supporting surfaces in the preview and downloaded PDF.</p>
      </div>
      <div className="template-style-controls">
        <label className="field color-field">
          <span>Theme Color</span>
          <div className="color-field-row">
            <input type="color" value={color} className="color-input" onChange={(event) => onColorChange(event.target.value)} aria-label="Section heading color" />
            <span className="color-value">{color.toUpperCase()}</span>
          </div>
        </label>
        <Button variant="secondary" size="small" onClick={onReset} disabled={color === defaultColor}>
          Reset Default
        </Button>
      </div>
    </div>
  );
}

function Card({ children }) {
  return <div className="editor-card">{children}</div>;
}

function Field({ label, value, onChange, disabled = false, spellCheck = true }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        value={value}
        disabled={disabled}
        spellCheck={spellCheck}
        autoCorrect={spellCheck ? "on" : "off"}
        autoCapitalize={spellCheck ? "sentences" : "off"}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function PhotoUploadField({ label, value, fullName, photoOffset, onPhotoOffsetChange, onSelectFile, onRemove }) {
  const inputRef = useRef(null);

  return (
    <div className="photo-field">
      <div className="photo-field-media">
        <div className="photo-field-preview" aria-hidden="true">
          {value ? <ProfilePhotoCrop src={value} alt="" size={88} offsetY={photoOffset} /> : <span>{getAvatarInitials(fullName)}</span>}
        </div>
        <div className="photo-field-copy">
          <strong>{label}</strong>
          <p>Upload a headshot for the `Profile Banner` template. You can move it up or down so the preview and PDF show the best framing.</p>
        </div>
      </div>

      <div className="photo-field-actions">
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="photo-field-input"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              onSelectFile(file);
            }
            event.target.value = "";
          }}
        />
        <Button variant="secondary" size="small" onClick={() => inputRef.current?.click()}>
          {value ? "Change Photo" : "Upload Photo"}
        </Button>
        {value ? (
          <Button variant="ghost" size="small" className="photo-field-remove" onClick={onRemove}>
            Remove
          </Button>
        ) : null}
      </div>

      {value ? (
        <label className="photo-position-field">
          <div className="photo-position-head">
            <span>Photo Vertical Position</span>
            <strong>{photoOffset > 0 ? `+${photoOffset}` : photoOffset}</strong>
          </div>
          <input
            type="range"
            min="-40"
            max="40"
            step="1"
            value={photoOffset}
            onChange={(event) => onPhotoOffsetChange(Number(event.target.value))}
          />
          <div className="photo-position-scale" aria-hidden="true">
            <span>Up</span>
            <span>Center</span>
            <span>Down</span>
          </div>
        </label>
      ) : null}
    </div>
  );
}

function CommaSeparatedSkillsField({ label, items, onChange }) {
  const [draft, setDraft] = useState(() => formatCommaSeparatedSkills(items));
  const [isFocused, setIsFocused] = useState(false);
  const itemsSignature = JSON.stringify(items || []);

  useEffect(() => {
    if (!isFocused) {
      setDraft(formatCommaSeparatedSkills(items));
    }
  }, [isFocused, itemsSignature, items]);

  const handleChange = (value) => {
    setDraft(value);
    onChange(parseCommaSeparatedSkills(value));
  };

  const normalizeDraft = () => {
    const normalizedItems = parseCommaSeparatedSkills(draft);
    setDraft(formatCommaSeparatedSkills(normalizedItems));
    onChange(normalizedItems);
  };

  return (
    <label className="field">
      <span>{label}</span>
      <input
        value={draft}
        spellCheck={false}
        autoCorrect="off"
        autoCapitalize="off"
        onFocus={() => setIsFocused(true)}
        onBlur={() => {
          setIsFocused(false);
          normalizeDraft();
        }}
        onChange={(event) => handleChange(event.target.value)}
      />
    </label>
  );
}

function BoldButton({ onClick }) {
  return (
    <button
      type="button"
      className="format-btn"
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      aria-label="Bold selected text"
      title="Bold selected text (Ctrl+B)"
    >
      B
    </button>
  );
}

function TextArea({ label, value, onChange, rows, spellCheck = true, enableBold = false }) {
  const inputRef = useRef(null);

  return (
    <label className="field">
      <div className="field-head">
        <span>{label}</span>
        {enableBold ? <BoldButton onClick={() => applyBoldFormatting(inputRef.current, value, onChange)} /> : null}
      </div>
      <textarea
        ref={inputRef}
        rows={rows}
        value={value}
        spellCheck={spellCheck}
        autoCorrect={spellCheck ? "on" : "off"}
        autoCapitalize={spellCheck ? "sentences" : "off"}
        onKeyDown={(event) => handleBoldShortcut(event, inputRef.current, value, onChange)}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function BulletEditorRow({ label, index, value, onChange, onRemove }) {
  const inputRef = useRef(null);

  return (
    <div className="bullet-input-row">
      <span className="bullet-input-dot">{"\u2022"}</span>
      <input
        ref={inputRef}
        value={value}
        spellCheck={true}
        autoCorrect="on"
        autoCapitalize="sentences"
        onKeyDown={(event) => handleBoldShortcut(event, inputRef.current, value, (nextValue) => onChange(index, nextValue))}
        onChange={(event) => onChange(index, event.target.value)}
        placeholder="Write one bullet point"
      />
      <BoldButton onClick={() => applyBoldFormatting(inputRef.current, value, (nextValue) => onChange(index, nextValue))} />
      <Button variant="ghost" className="bullet-remove-btn" onClick={() => onRemove(index)}>
        Remove
      </Button>
    </div>
  );
}

function BulletListEditor({ label, items, addLabel, onChange, onAdd, onRemove }) {
  return (
    <div className="field bullet-editor">
      <div className="bullet-editor-head">
        <span>{label}</span>
        <Button variant="secondary" size="small" onClick={onAdd}>
          {addLabel}
        </Button>
      </div>
      <div className="bullet-editor-list">
        {items.map((item, index) => (
          <BulletEditorRow key={`${label}-${index}`} label={label} index={index} value={item} onChange={onChange} onRemove={onRemove} />
        ))}
      </div>
    </div>
  );
}

function ATSSimpleResultPanel({ result, optimization, currentResume, onAutoFix, autoFixDisabled, autoFixing, resultSource = "editor" }) {
  const overallScore = normalizeScore(result.overall_ats_score ?? result.overall_score);
  const status = simpleAtsStatus(overallScore);
  const analyzedResume = resultSource === "pdf" && result.analyzed_resume ? normalizeResumeData(result.analyzed_resume) : currentResume;
  const metrics = [
    { label: "Job Match", value: normalizeScore(result.job_match_score ?? result.overall_score), tone: "blue" },
    { label: "Role Fit", value: normalizeScore(result.score_breakdown?.job_match?.role_context_fit ?? result.score_breakdown?.job_match?.role_alignment), tone: "green" },
    { label: "Requirement Evidence", value: normalizeScore(result.score_breakdown?.job_match?.semantic_requirement_match ?? result.semantic_coverage), tone: "blue" },
    { label: "Experience Match", value: normalizeScore(result.section_scores?.experience_relevance ?? result.responsibility_match_score), tone: "yellow" },
    { label: "Keyword Coverage", value: normalizeScore(result.section_scores?.keyword_coverage ?? result.section_scores?.skills_match), tone: "green" },
  ];
  const allFixes = buildSimpleFixes(result, optimization);
  const fixes = allFixes.slice(0, 5);
  const skills = buildSimpleSkills(result);
  const skillGroups = [
    { title: "Strong", icon: "check", tone: "strong", items: skills.strong },
    { title: "Needs Improvement", icon: "warning", tone: "warning", items: skills.needsImprovement },
    { title: "Missing", icon: "cross", tone: "missing", items: skills.missing },
  ].filter((group) => group.items.length);
  const roleFits = buildSimpleRoleFit(result, skills);
  const summary = buildSimpleAtsSummary(result, status, fixes.length, optimization);
  const actionPlanLabel = allFixes.length > fixes.length ? `Showing ${fixes.length} of ${allFixes.length}` : `${fixes.length} item${fixes.length === 1 ? "" : "s"}`;
  const correctionPlan = buildAtsCorrectionPlan(result, analyzedResume, overallScore);

  return (
    <div className="ats-simple-result">
      <section className={`ats-simple-score-card tone-${status.tone}`}>
        <div className="ats-simple-score-main">
          <div className="ats-simple-score-number" style={{ "--score": overallScore }}>
            <div className="ats-simple-score-ring">
              <div className="ats-simple-score-ring-core">
                <strong>{overallScore}</strong>
                <span>/100</span>
              </div>
            </div>
          </div>
          <div className="ats-simple-score-copy">
            <p className="ats-simple-label">ATS Score</p>
            <h3>{status.label}</h3>
            <p className="ats-simple-role-caption">{result.job_title || "Target role"}</p>
            <p className="ats-simple-summary">{summary}</p>
            <Button variant="primary" className="ats-simple-cta" onClick={onAutoFix} disabled={autoFixDisabled}>
              <span className="ats-simple-cta-sheen" aria-hidden="true" />
              <span className="ats-simple-cta-text">
                {resultSource === "pdf" ? "Auto Fix Uses Editor Resume" : autoFixing ? "Fixing..." : "Fix My Resume Automatically"}
              </span>
            </Button>
          </div>
        </div>
        <div className="ats-simple-metrics">
          {metrics.map((metric) => (
            <div className={`ats-simple-metric tone-${metric.tone}`} key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          ))}
        </div>
      </section>

      {fixes.length ? (
        <section className="ats-simple-card">
          <div className="ats-simple-section-head">
            <div>
              <p className="ats-simple-label">Action Plan</p>
              <h4>Fix These to Improve Score</h4>
            </div>
            <span className="ats-simple-pill warning">{actionPlanLabel}</span>
          </div>
          <div className="ats-simple-action-list">
            {fixes.map((item, index) => (
              <SimpleFixItem item={item} key={`simple-fix-${index}`} />
            ))}
          </div>
        </section>
      ) : null}

      {correctionPlan.items.length ? (
        <section className="ats-simple-card ats-correction-card">
          <div className="ats-simple-section-head">
            <div>
              <p className="ats-simple-label">Correction Suggestions</p>
              <h4>Professional Coach Rewrite and Score Lift</h4>
            </div>
            <span className="ats-simple-pill success">
              {overallScore} -&gt; {correctionPlan.projectedScore}
            </span>
          </div>

          <div className="ats-correction-summary">
            <div>
              <span>Estimated lift</span>
              <strong>+{correctionPlan.totalImpact} points</strong>
            </div>
            <p>
              These edits are personalized suggestions based on this resume and JD. Your editor resume is unchanged until you manually add the lines you trust.
            </p>
          </div>

          <div className="ats-correction-list">
            {correctionPlan.items.map((item) => (
              <CorrectionSuggestionCard item={item} key={item.id} />
            ))}
          </div>

          {correctionPlan.projectIdeas.length ? (
            <div className="ats-project-coach-block">
              <div className="ats-simple-section-head">
                <div>
                  <p className="ats-simple-label">Project Coach</p>
                  <h4>Projects to Build and Add Before Applying</h4>
                </div>
                <span className="ats-simple-pill success">Up to +{correctionPlan.projectImpact} more</span>
              </div>
              <div className="ats-project-idea-grid">
                {correctionPlan.projectIdeas.map((project) => (
                  <ProjectIdeaCard project={project} key={project.id} />
                ))}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {skillGroups.length ? (
        <section className="ats-simple-card">
          <div className="ats-simple-section-head">
            <div>
              <p className="ats-simple-label">Skills Match</p>
              <h4>Strong, Needs Improvement, Missing</h4>
            </div>
          </div>
          <div className={`ats-simple-skill-grid columns-${skillGroups.length}`}>
            {skillGroups.map((group) => (
              <SkillColumn title={group.title} icon={group.icon} tone={group.tone} items={group.items} key={group.title} />
            ))}
          </div>
        </section>
      ) : null}

      {roleFits.length ? (
        <section className="ats-simple-card">
          <div className="ats-simple-section-head">
            <div>
              <p className="ats-simple-label">Role Fit Snapshot</p>
              <h4>Skill to status</h4>
            </div>
            <span className="ats-simple-pill neutral">Max 5</span>
          </div>
          <div className="ats-simple-role-snapshot">
            {roleFits.map((item) => (
              <div className="ats-simple-role-row" key={`role-fit-${item.skill}`}>
                <strong>{item.skill}</strong>
                <span aria-hidden="true">-&gt;</span>
                <span className={`ats-simple-status ${item.tone}`}>{item.status}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

    </div>
  );
}

function CorrectionSuggestionCard({ item }) {
  return (
    <article className="ats-correction-item">
      <div className="ats-correction-topline">
        <span className="ats-simple-status strong">+{item.impact} score</span>
        <strong>{item.skill}</strong>
        <span>{item.action}</span>
      </div>
      <div className="ats-correction-lines">
        <div>
          <span>Old resume line</span>
          <p>{item.oldLine}</p>
        </div>
        <div className="is-new">
          <span>Professional coach suggestion</span>
          <p>{item.newLine}</p>
        </div>
      </div>
      <div className="ats-skill-placement">
        <span>Where to place it</span>
        <strong>{item.skillPlacement}</strong>
        <p>{item.guidance}</p>
      </div>
    </article>
  );
}

function ProjectIdeaCard({ project }) {
  return (
    <article className="ats-project-idea-card">
      <div className="ats-correction-topline">
        <span className="ats-simple-status strong">+{project.impact} score</span>
        <strong>{project.title}</strong>
        <span>Add in Projects</span>
      </div>
      <p>{project.why}</p>
      {project.buildSummary ? (
        <div className="ats-project-build-summary">
          <span>What to build</span>
          <p>{project.buildSummary}</p>
        </div>
      ) : null}
      <div className="ats-project-idea-columns">
        <div>
          <span>Project section entry</span>
          <strong>{project.projectName}</strong>
          <p>{project.stack}</p>
        </div>
        <div>
          <span>Resume bullets</span>
          <ul>
            {project.bullets.map((bullet) => (
              <li key={bullet}>{bullet}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="ats-project-detail-grid">
        {project.coreFeatures?.length ? (
          <div>
            <span>Core build features</span>
            <ul>
              {project.coreFeatures.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {project.technologyPlan?.length ? (
          <div>
            <span>Technology map</span>
            <ul>
              {project.technologyPlan.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {project.evaluationPlan?.length ? (
          <div>
            <span>How to evaluate it</span>
            <ul>
              {project.evaluationPlan.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {project.proofArtifacts?.length ? (
          <div>
            <span>Proof to collect</span>
            <p>{project.proofArtifacts.join(", ")}</p>
          </div>
        ) : null}
      </div>
      {project.learnBeforeSubmit.length ? (
        <div className="ats-learning-plan">
          <span>Learn before submitting</span>
          <p>{project.learnBeforeSubmit.join(", ")}</p>
        </div>
      ) : null}
      {project.readinessRule ? (
        <div className="ats-project-readiness">
          <span>When to add it</span>
          <p>{project.readinessRule}</p>
        </div>
      ) : null}
    </article>
  );
}

function SimpleFixItem({ item }) {
  return (
    <div className={`ats-simple-list-item tone-${item.icon}`}>
      <span className={`ats-simple-icon ${item.icon}`} aria-hidden="true">
        {simpleIconText(item.icon)}
      </span>
      <div className="ats-simple-list-copy">
        <div className="ats-simple-fix-line">
          <span>Problem</span>
          <strong>{item.problem}</strong>
        </div>
        <div className="ats-simple-fix-line">
          <span>Fix</span>
          <p>{item.fix}</p>
        </div>
      </div>
    </div>
  );
}

function buildAtsCorrectionPlan(result, resume, overallScore) {
  const skills = uniqueDisplayItems([
    ...(result.missing_required_skills ?? []).map((item) => item.keyword),
    ...(result.missing_keywords ?? []).filter((item) => ["high", "medium"].includes(String(item.importance || "").toLowerCase())).map((item) => item.keyword),
    ...(result.weak_evidence_skills ?? []).map((item) => item.keyword),
  ]).filter(isSkillLikeTerm);

  const resumeLines = collectResumeEvidenceLines(resume);
  const usedSuggestionFingerprints = new Set();
  const usedEvidenceKeys = new Set();
  const items = skills.slice(0, 5).map((skill, index) => {
    const oldLine = findBestOldLineForSkill(skill, resumeLines, index, result, resume, usedEvidenceKeys);
    const context = detectResumeBulletContext(skill, result, resume);
    const shouldPreferProject = oldLine.synthetic && shouldSuggestProjectEvidence(skill, context, result, resume);
    const section = shouldPreferProject || oldLine.section === "projects" ? "Projects" : "Experience";
    const action = oldLine.synthetic || shouldPreferProject ? `Add to ${section}` : oldLine.weakEvidence ? `Improve ${section}` : `Rewrite in ${section}`;
    const targetPlacement = oldLine.synthetic ? findBestAddTarget(skill, section, result, resume, context) : null;
    const placement = findSkillPlacement(resume, skill);
    const newLine = ensureUniqueCoachSuggestion(
      buildModelResumeLine(skill, result, oldLine, section, resume, index, targetPlacement),
      skill,
      result,
      resume,
      context,
      section,
      usedSuggestionFingerprints,
      index,
      targetPlacement,
    );
    const impact = estimateSkillImpact(skill, result, index);

    return {
      id: `${skill.toLowerCase()}-${index}`,
      skill,
      oldLine: oldLine.synthetic ? targetPlacement.oldLineText : oldLine.text,
      newLine,
      action,
      impact,
      skillPlacement: oldLine.synthetic
        ? buildDeferredSkillPlacementText(skill, placement, targetPlacement)
        : buildSkillPlacementText(skill, placement),
      guidance: oldLine.synthetic
        ? buildMissingEvidenceGuidance(skill, result.job_title, placement, targetPlacement)
        : buildSkillGuidance(skill, result.job_title, section, placement),
      placement,
    };
  });
  const projectIdeas = buildSuggestedProjectIdeas(result, resume, skills).slice(0, 3);
  const projectImpact = Math.min(14, projectIdeas.reduce((sum, item) => sum + item.impact, 0));
  const totalImpact = Math.min(38, items.reduce((sum, item) => sum + item.impact, 0) + projectImpact);
  const projectedScore = Math.min(100, normalizeScore(overallScore) + totalImpact);
  const skillGroups = buildPreviewSkillGroups(items);
  const primarySkillGroup = skillGroups[0] ?? { groupName: "Technical Skills", skillLine: items.map((item) => item.skill).join(", ") };

  return {
    items,
    totalImpact,
    projectedScore,
    skillGroupName: primarySkillGroup.groupName,
    skillLine: primarySkillGroup.skillLine,
    skillGroups,
    projectIdeas,
    projectImpact,
    targetRole: result.job_title || "",
    previewBullets: items.map((item) => item.newLine),
  };
}

function collectResumeEvidenceLines(resume) {
  const lines = [];
  (resume?.experience ?? []).forEach((item, itemIndex) => {
    (item.achievements ?? []).forEach((achievement, lineIndex) => {
      const text = cleanDisplayText(stripRichText(achievement));
      if (isUsefulResumeEvidenceLine(text)) lines.push({ text, section: "experience", itemIndex, lineIndex });
    });
  });
  (resume?.projects ?? []).forEach((item, itemIndex) => {
    (item.highlights ?? []).forEach((highlight, lineIndex) => {
      const text = cleanDisplayText(stripRichText(highlight));
      if (isUsefulResumeEvidenceLine(text)) lines.push({ text, section: "projects", itemIndex, lineIndex });
    });
  });
  return lines;
}

function findBestAddTarget(skill, section, result, resume, context) {
  const targetSection = section === "Projects" ? "Projects" : "Experience";
  const allCandidates = collectProjectTargets(resume).concat(collectExperienceTargets(resume));
  const scored = allCandidates.map((candidate, index) => ({
    ...candidate,
    score: scoreAddTarget(candidate, skill, result, resume, context) + (candidate.section === targetSection ? 1 : 0),
    index,
  })).sort((left, right) => right.score - left.score || left.index - right.index);

  const selected = scored.find((candidate) => candidate.score >= minimumAddTargetScore(skill, context));
  if (!selected) {
    return {
      section: targetSection,
      label: "",
      name: "",
      oldLineText: `No existing Experience or Projects entry strongly matches ${skill}. Add this only after you build or document relevant proof.`,
    };
  }
  return {
    ...selected,
    oldLineText: `Add this as a new bullet under ${selected.label}; no strong existing line matched ${skill}.`,
  };
}

function collectProjectTargets(resume) {
  return (resume?.projects ?? []).map((project, index) => ({
    section: "Projects",
    name: cleanDisplayText(project.name || `Project ${index + 1}`),
    label: `Projects: ${cleanDisplayText(project.name || `Project ${index + 1}`)}`,
    tech: cleanDisplayText(project.tech_stack),
    text: cleanDisplayText([project.name, project.tech_stack, ...(project.highlights ?? [])].join(" ")),
  })).filter((item) => item.text);
}

function collectExperienceTargets(resume) {
  return (resume?.experience ?? []).map((job, index) => {
    const role = cleanDisplayText(job.role || `Experience ${index + 1}`);
    const company = cleanDisplayText(job.company);
    return {
      section: "Experience",
      name: role,
      label: `Experience: ${role}${company ? ` at ${company}` : ""}`,
      tech: "",
      text: cleanDisplayText([job.role, job.company, job.description, ...(job.achievements ?? [])].join(" ")),
    };
  }).filter((item) => item.text);
}

function scoreAddTarget(candidate, skill, result, resume, context) {
  const text = cleanDisplayText(candidate.text).toLowerCase();
  const normalizedSkill = cleanDisplayText(skill).toLowerCase();
  const terms = uniqueDisplayItems([
    ...skillEvidenceTokens(skill),
    ...meaningfulCoachTerms(contextualSkillFamilyText(context, skill)),
    ...meaningfulCoachTerms(result?.job_title),
    ...meaningfulCoachTerms(resume?.basics?.headline),
  ]).slice(0, 30);
  let score = terms.reduce((sum, term) => sum + (text.includes(term.toLowerCase()) ? 1 : 0), 0);
  if (normalizedSkill && text.includes(normalizedSkill)) score += 8;
  if (hasStrongContextMatch(candidate, skill, result, resume)) score += 3;
  score += specificDomainEvidenceScore(text, context, skill);
  if (candidate.section === "Projects" && ["ai", "data", "cloud", "security", "mobile", "frontend", "backend"].includes(context)) score += 1;
  if (candidate.section === "Experience" && ["product", "sales", "finance", "hr", "marketing", "it", "network", "sap"].includes(context)) score += 1;
  return score;
}

function minimumAddTargetScore(skill, context) {
  const normalized = cleanDisplayText(skill).toLowerCase();
  if (/(aws|azure|gcp|kubernetes|docker|terraform|ci\/cd|jenkins|github actions)/i.test(normalized)) return 7;
  if (["cloud", "security", "sap", "network", "database"].includes(context)) return 6;
  return 5;
}

function specificDomainEvidenceScore(text, context, skill) {
  const normalizedSkill = cleanDisplayText(skill).toLowerCase();
  let score = 0;

  if (context === "cloud") {
    if (/\b(aws|azure|gcp|cloud|terraform|iam|vpc|compute|storage)\b/i.test(text)) score += 4;
    if (/\b(docker|kubernetes|container|ci\/cd|github actions|jenkins|deployment|release|rollback|monitoring)\b/i.test(text)) score += 3;
    if (/\b(model|scikit|pandas|numpy|recommendation|classification|prediction)\b/i.test(text) && !/\b(deploy|deployment|cloud|docker|kubernetes|gcp|aws|azure)\b/i.test(text)) score -= 3;
  }
  if (context === "ai" && /\b(model|ml|machine learning|scikit|tensorflow|pytorch|nlp|rag|llm|evaluation)\b/i.test(text)) score += 3;
  if (context === "data" && /\b(sql|dashboard|analytics|kpi|etl|pandas|tableau|power bi|reporting)\b/i.test(text)) score += 3;
  if (context === "frontend" && /\b(react|javascript|typescript|component|ui|css|accessibility)\b/i.test(text)) score += 3;
  if (context === "backend" && /\b(api|backend|fastapi|node|django|database|postgres|endpoint)\b/i.test(text)) score += 3;
  if (normalizedSkill && text.includes(normalizedSkill)) score += 2;
  return score;
}

function isUsefulResumeEvidenceLine(text) {
  const cleaned = cleanDisplayText(text);
  if (cleaned.length < 38) return false;
  const lowered = cleaned.toLowerCase();
  if (/^(software engineer|developer|intern|hyderabad|india|remote|present|education|skills|projects)\b/.test(lowered) && cleaned.split(/\s+/).length <= 8) return false;
  if (!/\b(built|created|developed|designed|implemented|managed|led|optimized|automated|improved|delivered|trained|analyzed|deployed|integrated|configured|reduced|increased|generated|documented|collaborated|worked|owned|launched|maintained)\b/i.test(cleaned)) {
    return false;
  }
  return true;
}

function shouldSuggestProjectEvidence(skill, context, result, resume) {
  const hasProjects = (resume?.projects ?? []).some((project) =>
    cleanDisplayText([project.name, project.tech_stack, ...(project.highlights ?? [])].join(" "))
  );
  const required = (result.missing_required_skills ?? []).some((item) => sameDisplayText(item.keyword, skill));
  const missing = (result.missing_keywords ?? []).some((item) => sameDisplayText(item.keyword, skill));
  const projectFriendly = ["ai", "data", "frontend", "backend", "cloud", "product", "marketing", "sales", "finance", "hr", "design", "security", "mobile"].includes(context);
  return projectFriendly && (required || missing || !hasProjects);
}

function buildSuggestedProjectIdeas(result, resume, skills) {
  const role = professionalRoleLabel(result, resume);
  const context = detectResumeBulletContext(skills.join(" "), result, resume);
  const missing = uniqueDisplayItems(skills).filter(isSkillLikeTerm).slice(0, 10);
  const resumeSummary = cleanDisplayText([resume?.basics?.headline, resume?.basics?.summary].join(" "));
  const roleProjects = buildRealWorldProjectIdeas(result, resume, missing, context, role);
  const ragProjects = buildRagProjectIdeas(result, resume, missing, context, role);
  const projectFocuses = buildTailoredProjectFocuses(context, role, missing, result, resumeSummary);
  const tailoredProjects = projectFocuses.map((focus, index) => buildCoachProjectIdea(focus, role, context, missing, result, resume, index));
  const fallbackProject = projectTemplateForContext(context, role, missing[0] || "role-specific skills", missing[1] || role, missing);
  return [...roleProjects, ...ragProjects, ...tailoredProjects, fallbackProject]
    .filter(Boolean)
    .filter((item, index, list) => list.findIndex((candidate) => candidate.projectName === item.projectName) === index)
    .map((project, index) => enrichProjectIdea(project, context, role, missing, result, resume, index));
}

function buildRealWorldProjectIdeas(result, resume, missingSkills, context, role) {
  const profileText = cleanDisplayText([
    role,
    result?.job_title,
    result?.detected_role_family,
    result?.detected_resume_role_family,
    resume?.basics?.headline,
    resume?.basics?.summary,
    ...(resume?.skills ?? []).map((group) => `${group.name} ${(group.items ?? []).join(" ")}`),
    ...(result?.missing_required_skills ?? []).map((item) => item.keyword),
    ...(result?.missing_keywords ?? []).map((item) => item.keyword),
    ...(result?.unmatched_requirements ?? []).map((item) => item.requirement || item.keyword || item.text),
  ].join(" ")).toLowerCase();
  const archetypes = realWorldProjectArchetypesForRole(profileText, context, role);
  return archetypes.slice(0, 3).map((project, index) => {
    const stack = uniqueDisplayItems([...project.stack, ...missingSkills.slice(index, index + 3)]).slice(0, 8);
    return {
      id: `real-world-${project.projectName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
      title: `Real-world ${project.domain} project: ${project.projectName}`,
      projectName: project.projectName,
      stack: stack.join(", "),
      why: project.why,
      bullets: project.bullets,
      learnBeforeSubmit: uniqueDisplayItems([...project.learnBeforeSubmit, ...missingSkills.slice(0, 3)]).slice(0, 8),
      impact: Math.max(7, 10 - index),
      realWorldDomain: project.domain,
    };
  });
}

function realWorldProjectArchetypesForRole(profileText, context, role) {
  if (/\b(data scientist|machine learning|ml engineer|ai engineer|nlp|predictive|model|scikit|tensorflow|pytorch)\b/i.test(profileText)) {
    return [
      {
        domain: "data science",
        projectName: "Customer Churn Prediction and Retention Insights",
        stack: ["Python", "SQL", "Pandas", "Scikit-learn", "feature engineering", "model evaluation", "SHAP"],
        why: `This is a professional ${role} portfolio project because it mirrors a common business problem: predicting churn, explaining drivers, and recommending retention actions.`,
        bullets: [
          "Built a churn prediction pipeline with SQL/Python feature engineering, baseline comparison, and precision/recall evaluation.",
          "Explained churn drivers with feature importance and translated model output into retention recommendations for business stakeholders.",
        ],
        learnBeforeSubmit: ["classification metrics", "feature engineering", "model explainability"],
      },
      {
        domain: "data science",
        projectName: "Demand Forecasting and Inventory Risk Dashboard",
        stack: ["Python", "Pandas", "time-series forecasting", "Power BI", "error analysis", "business recommendations"],
        why: "Forecasting projects look practical to recruiters because they connect historical data, model quality, inventory risk, and decisions a business can act on.",
        bullets: [
          "Created a demand forecasting workflow using historical sales data, seasonality features, and forecast-error tracking.",
          "Built an inventory risk dashboard highlighting stockout risk, reorder signals, and recommendations for operations teams.",
        ],
        learnBeforeSubmit: ["time-series validation", "forecast error", "dashboard storytelling"],
      },
      {
        domain: "AI/ML",
        projectName: "RAG Policy Knowledge Assistant",
        stack: ["Python", "FastAPI", "RAG", "embeddings", "vector database", "citations", "LLM evaluation"],
        why: "A RAG assistant is a current real-world AI project when it includes retrieval quality checks, citations, fallback behavior, and hallucination review.",
        bullets: [
          "Built a RAG assistant that retrieves policy/document passages, generates cited answers, and handles low-confidence queries with fallback responses.",
          "Evaluated retrieval quality with test questions, relevance labels, citation checks, and hallucination-risk notes.",
        ],
        learnBeforeSubmit: ["embeddings", "chunking", "retrieval evaluation"],
      },
    ];
  }

  if (/\b(data analyst|business analyst|bi analyst|analytics|dashboard|power bi|tableau|sql)\b/i.test(profileText) || context === "data") {
    return [
      {
        domain: "analytics",
        projectName: "Revenue KPI and Cohort Analytics Dashboard",
        stack: ["SQL", "Power BI", "Excel", "cohort analysis", "KPI definitions", "stakeholder reporting"],
        why: "This resembles real analyst work: define metrics, clean data, explain trends, and recommend business actions.",
        bullets: [
          "Built a KPI dashboard tracking revenue, retention, cohorts, and conversion trends from cleaned SQL datasets.",
          "Documented metric definitions, data-quality checks, and action recommendations for stakeholder review.",
        ],
        learnBeforeSubmit: ["SQL joins", "KPI design", "Power BI storytelling"],
      },
      {
        domain: "analytics",
        projectName: "E-commerce Funnel Drop-off Analysis",
        stack: ["SQL", "Python", "funnel analysis", "A/B testing", "Tableau", "conversion metrics"],
        why: "Funnel analysis is a practical project for product, marketing, and BI roles because it turns behavior data into conversion decisions.",
        bullets: [
          "Analyzed browse-to-checkout funnel drop-offs using SQL cohorts and conversion-rate metrics.",
          "Recommended A/B test hypotheses and UX fixes tied to measurable conversion improvement.",
        ],
        learnBeforeSubmit: ["funnel analysis", "cohort metrics", "A/B testing basics"],
      },
    ];
  }

  if (/\b(backend|software engineer|full stack|api|fastapi|node|django|spring|microservice)\b/i.test(profileText) || ["backend", "frontend"].includes(context)) {
    return [
      {
        domain: "software engineering",
        projectName: "Role-Based SaaS Admin Portal",
        stack: ["React", "FastAPI", "PostgreSQL", "authentication", "RBAC", "REST APIs", "audit logs"],
        why: "This is a strong real-world engineering project because it shows product workflow, API design, database persistence, access control, and operational evidence.",
        bullets: [
          "Built a role-based admin portal with authentication, CRUD workflows, PostgreSQL persistence, and protected API routes.",
          "Added validation, audit logs, error states, and API tests to improve reliability and reviewer trust.",
        ],
        learnBeforeSubmit: ["API contracts", "RBAC", "database schema design"],
      },
      {
        domain: "software engineering",
        projectName: "Customer Support Ticketing and SLA Tracker",
        stack: ["React", "Node.js", "SQL", "SLA tracking", "notifications", "dashboarding"],
        why: "Ticketing systems are recognizable business software and let candidates show workflow ownership, data modeling, and reporting.",
        bullets: [
          "Built a support ticketing workflow with intake, assignment, SLA timers, status updates, and escalation rules.",
          "Created dashboard views for ticket volume, resolution time, overdue items, and recurring issue categories.",
        ],
        learnBeforeSubmit: ["workflow modeling", "SQL reporting", "error handling"],
      },
    ];
  }

  if (/\b(devops|cloud|sre|aws|azure|gcp|docker|kubernetes|terraform|ci\/cd)\b/i.test(profileText) || context === "cloud") {
    return [
      {
        domain: "cloud",
        projectName: "Cloud Cost and Reliability Dashboard",
        stack: ["AWS or GCP", "Docker", "Terraform", "GitHub Actions", "Prometheus", "Grafana", "runbooks"],
        why: "This mirrors practical cloud/SRE work by showing deployment health, cost awareness, alerts, and operational readiness.",
        bullets: [
          "Built a cloud reliability dashboard tracking deployment status, service health, alert rules, and cost indicators.",
          "Documented infrastructure setup, rollback notes, runbook steps, and validation evidence for production readiness.",
        ],
        learnBeforeSubmit: ["cloud IAM basics", "CI/CD", "monitoring"],
      },
      {
        domain: "cloud",
        projectName: "Containerized CI/CD Release Pipeline",
        stack: ["Docker", "GitHub Actions", "Kubernetes", "environment variables", "tests", "rollback"],
        why: "A release pipeline project proves you can ship software reliably, not only list cloud keywords.",
        bullets: [
          "Automated test, build, containerization, and deployment steps for a sample backend service.",
          "Added environment configuration, release logs, health checks, and rollback documentation.",
        ],
        learnBeforeSubmit: ["Dockerfiles", "pipeline validation", "rollback planning"],
      },
    ];
  }

  if (/\b(cyber|security|soc|siem|vulnerability|iam|risk|owasp)\b/i.test(profileText) || context === "security") {
    return [
      {
        domain: "cybersecurity",
        projectName: "SOC Alert Triage and Incident Report Simulator",
        stack: ["SIEM logs", "Splunk or Sentinel", "incident response", "severity scoring", "reporting"],
        why: "This looks professional for security roles because it shows evidence handling, severity judgment, escalation, and reporting.",
        bullets: [
          "Built a SOC alert triage simulator that classifies suspicious events, captures evidence, and recommends escalation paths.",
          "Generated incident reports with timeline, impacted asset, severity, root cause, and containment recommendations.",
        ],
        learnBeforeSubmit: ["SIEM basics", "incident timeline", "severity scoring"],
      },
      {
        domain: "cybersecurity",
        projectName: "OWASP API Vulnerability Tracker",
        stack: ["OWASP Top 10", "API security", "risk severity", "remediation tracking", "audit logs"],
        why: "A vulnerability tracker demonstrates security thinking plus practical documentation and remediation ownership.",
        bullets: [
          "Created an API vulnerability tracker with severity classification, reproduction notes, owners, and remediation status.",
          "Added audit evidence, risk summaries, and validation checks for security review.",
        ],
        learnBeforeSubmit: ["OWASP Top 10", "risk rating", "remediation evidence"],
      },
    ];
  }

  return [
    {
      domain: context || "professional",
      projectName: `${role} Operations Case Study`,
      stack: ["workflow design", "documentation", "metrics", "validation", "stakeholder reporting"],
      why: "This gives recruiters a concrete case study with problem, approach, tools, evidence, and outcome instead of a generic keyword project.",
      bullets: [
        `Built a ${role} case study documenting the problem, workflow, tools used, validation evidence, and measurable outcome.`,
        "Created a recruiter-ready README with screenshots, decisions, limitations, and next improvements.",
      ],
      learnBeforeSubmit: ["case study writing", "metrics", "documentation"],
    },
  ];
}

function enrichProjectIdea(project, context, role, missingSkills, result, resume, index = 0) {
  const projectName = cleanDisplayText(project.projectName || project.title || `${role} proof project`);
  const stack = parseProjectStack(project.stack, missingSkills);
  const jdSignals = uniqueDisplayItems([
    ...(result?.missing_required_skills ?? []).map((item) => item.keyword),
    ...(result?.missing_keywords ?? []).map((item) => item.keyword),
    ...(result?.unmatched_requirements ?? []).map((item) => item.requirement || item.keyword || item.text),
  ].map(cleanProjectSignal)).filter(Boolean).slice(0, 6);
  const resumeAnchor = cleanDisplayText(resume?.basics?.headline || resume?.experience?.[0]?.role || resume?.projects?.[0]?.name || role);
  const blueprint = projectBlueprintForContext(context, projectName, role, stack, jdSignals, resumeAnchor);
  const resumeBullets = strengthenProjectResumeBullets(project, blueprint, context, role, stack);

  return {
    ...project,
    projectName,
    stack: stack.join(", "),
    title: project.title || `Build role-specific proof: ${projectName}`,
    why: project.why || blueprint.why,
    buildSummary: blueprint.buildSummary,
    coreFeatures: blueprint.coreFeatures,
    technologyPlan: blueprint.technologyPlan,
    evaluationPlan: blueprint.evaluationPlan,
    proofArtifacts: blueprint.proofArtifacts,
    readinessRule: blueprint.readinessRule,
    bullets: resumeBullets,
    learnBeforeSubmit: uniqueDisplayItems([...(project.learnBeforeSubmit ?? []), ...blueprint.learnBeforeSubmit]).slice(0, 8),
    impact: project.impact || Math.max(6, 9 - index),
  };
}

function parseProjectStack(stack, missingSkills) {
  return uniqueDisplayItems([
    ...String(stack || "").split(",").map(cleanDisplayText),
    ...missingSkills.slice(0, 3),
  ].map(cleanProjectSignal).filter(Boolean)).slice(0, 10);
}

function cleanProjectSignal(value) {
  const text = cleanDisplayText(value)
    .replace(/^[-•*]\s*/, "")
    .replace(/\s*\([^)]{40,}\)\s*/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text || text.length > 64) return "";
  if (/[.!?]$/.test(text)) return "";
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length > 6) return "";
  if (/^(designing|developing|researching|building|creating|working|partnering|managing|owning|responsible|should|must|will)\b/i.test(text)) return "";
  if (/\b(requirements?|responsibilit|qualification|permanent|full.?time|part.?time|salary|location|years?)\b/i.test(text)) return "";
  if (isSkillLikeTerm(text)) return text;
  if (/\b(churn|forecasting|recommendation|ranking|classification|regression|retrieval|dashboard|pipeline|deployment|monitoring|ticketing|triage|cohort|funnel|retention|inventory|fraud|risk|sentiment|pricing|segmentation)\b/i.test(text)) return text;
  return "";
}

function projectBlueprintForContext(context, projectName, role, stack, jdSignals, resumeAnchor) {
  const primary = stack[0] || jdSignals[0] || "role-specific skills";
  const secondary = stack[1] || jdSignals[1] || "validation";
  const signalText = jdSignals.length ? jdSignals.slice(0, 4).join(", ") : primary;
  const base = {
    why: `This turns ${resumeAnchor} into concrete proof for ${role} by showing the problem, build, tools, validation, and recruiter-readable outcome.`,
    buildSummary: `Build a small but working ${projectName} that solves one realistic ${role} workflow and proves ${signalText} with visible outputs.`,
    coreFeatures: [
      `Define the user problem, input data, expected output, and success metric before writing the resume bullet.`,
      `Build the main workflow end to end instead of only creating a static demo.`,
      `Add error handling, sample data, screenshots, and clear setup instructions.`,
      `Write a short README explaining tradeoffs, limitations, and what you would improve next.`,
    ],
    technologyPlan: [
      `Use ${primary} for the core implementation and ${secondary} for validation or delivery support.`,
      `Keep the stack small enough that you can explain every tool in an interview.`,
      `Document where each technology is used so the resume bullet does not look keyword-stuffed.`,
    ],
    evaluationPlan: [
      "Create 5-10 test cases or sample scenarios that prove the project works.",
      "Capture before/after results, screenshots, logs, or metric output.",
      "Check edge cases and document failures honestly.",
    ],
    proofArtifacts: ["GitHub README", "screenshots or demo video", "sample input/output", "validation notes"],
    readinessRule: "Add this to Projects only after you can run it, explain the design choices, and show evidence that it works.",
    learnBeforeSubmit: [],
  };

  if (context === "ai") {
    return {
      ...base,
      buildSummary: `Build ${projectName} as a working AI/ML workflow: ingest data, prepare features or context, run the model/retrieval logic, evaluate output quality, and explain the result.`,
      coreFeatures: [
        "Data ingestion with a small clean sample dataset or document set.",
        "Preprocessing, chunking, feature engineering, or prompt/retrieval setup depending on the project.",
        "Model, RAG, or agent workflow that returns a visible answer, prediction, ranking, or recommendation.",
        "Evaluation view showing metrics, failed cases, hallucination checks, or error analysis.",
      ],
      technologyPlan: [
        `Use ${primary} for the main AI/ML workflow.`,
        "Use Python notebooks or FastAPI/Streamlit for a reviewer-friendly demo.",
        "Use MLflow, metric tables, cited answers, or logs to prove the output was evaluated.",
      ],
      evaluationPlan: [
        "Compare at least one baseline against the improved version.",
        "Track precision, recall, F1, relevance, groundedness, or task success depending on the project.",
        "Save 5 strong examples and 3 failure cases with notes on why the model behaved that way.",
      ],
      proofArtifacts: ["README architecture diagram", "sample dataset", "metrics table", "failure-case notes", "screenshots"],
      learnBeforeSubmit: ["model evaluation", "error analysis", "README documentation"],
    };
  }

  if (context === "cloud") {
    return {
      ...base,
      buildSummary: `Build ${projectName} by deploying a small service, automating release steps, and proving it can be configured, validated, monitored, and rolled back.`,
      coreFeatures: [
        "A deployable sample API or app with environment variables and health checks.",
        "Dockerfile or deployment configuration with clear setup steps.",
        "CI/CD workflow that runs validation before deployment.",
        "Monitoring, release log, rollback notes, and cost/access assumptions.",
      ],
      technologyPlan: [
        `Use ${primary} for the cloud or platform layer.`,
        "Use Docker and GitHub Actions for repeatable build and release evidence.",
        "Use logs, health checks, or simple monitoring output to prove operational readiness.",
      ],
      evaluationPlan: [
        "Run build validation and record the pass/fail output.",
        "Deploy once, capture endpoint or service health evidence, then document rollback steps.",
        "Check secrets, IAM/access notes, and environment configuration assumptions.",
      ],
      proofArtifacts: ["deployment README", "pipeline screenshot", "release log", "rollback checklist"],
      learnBeforeSubmit: ["deployment validation", "CI/CD basics", "monitoring basics"],
    };
  }

  if (context === "data") {
    return {
      ...base,
      buildSummary: `Build ${projectName} as an analytics workflow: collect data, clean it, define KPIs, create analysis or dashboard output, and turn findings into recommendations.`,
      coreFeatures: [
        "Raw dataset plus documented cleaning rules.",
        "SQL/Python transformations with repeatable data-quality checks.",
        "Dashboard, notebook, or report with KPI definitions.",
        "Business recommendations tied to the final numbers.",
      ],
      technologyPlan: [
        `Use ${primary} for analysis or transformation.`,
        "Use SQL/Pandas for cleaning and Power BI/Tableau/Streamlit for presentation if relevant.",
        "Keep metric definitions visible so recruiters understand the business logic.",
      ],
      evaluationPlan: [
        "Validate row counts, missing values, duplicates, and KPI formulas.",
        "Explain at least 3 insights and the decision each insight supports.",
        "Include one limitation or data-quality risk.",
      ],
      proofArtifacts: ["dashboard screenshot", "cleaning notebook", "KPI dictionary", "insight summary"],
      learnBeforeSubmit: ["KPI design", "data-quality checks", "dashboard storytelling"],
    };
  }

  if (context === "backend" || context === "frontend") {
    return {
      ...base,
      buildSummary: `Build ${projectName} as a usable product workflow with UI/API behavior, validation states, persistence or integration, and tests.`,
      coreFeatures: [
        "One clear user workflow from input to saved or returned result.",
        "Validation, loading, empty, and error states.",
        "API contract or component structure that is easy to explain.",
        "Basic tests plus screenshots or demo notes.",
      ],
      technologyPlan: [
        `Use ${primary} in the core app layer.`,
        "Use API docs, schema examples, or component notes to explain the implementation.",
        "Keep the feature small but complete enough to show shipped-work judgment.",
      ],
      evaluationPlan: [
        "Test happy path, validation failures, and one edge case.",
        "Record API response examples or UI screenshots.",
        "Document performance, accessibility, or reliability tradeoffs where relevant.",
      ],
      proofArtifacts: ["demo screenshots", "API examples", "test notes", "README setup"],
      learnBeforeSubmit: ["test cases", "error handling", "README documentation"],
    };
  }

  return base;
}

function strengthenProjectResumeBullets(project, blueprint, context, role, stack) {
  const existing = (project.bullets ?? []).map(cleanDisplayText).filter(isProfessionalProjectBullet);
  if (existing.length >= 3) return existing.slice(0, 4);
  const primary = stack[0] || "role-specific tools";
  const secondary = stack[1] || "validation checks";
  const generated = [
    `Built ${project.projectName} using ${primary} and ${secondary} to solve a realistic ${role} workflow with measurable validation evidence.`,
    `Implemented ${blueprint.coreFeatures[0].replace(/[.!?]*$/, "").toLowerCase()}, then documented setup, screenshots, and tradeoffs for recruiter review.`,
    `Evaluated the project with ${blueprint.evaluationPlan[0].replace(/[.!?]*$/, "").toLowerCase()} and summarized limitations, failures, and next improvements.`,
  ];
  return uniqueDisplayItems([...existing, ...generated]).slice(0, 4);
}

function isProfessionalProjectBullet(value) {
  const text = cleanDisplayText(value);
  if (!text || text.length < 35 || text.length > 240) return false;
  if (/\bDesigning, developing, and researching\b/i.test(text)) return false;
  if (/\bPermanent\/?\s*Full time\b/i.test(text)) return false;
  if (/\bworkflow tied to\s+(Design|Develop|Research|Requirement|Responsibilit)/i.test(text)) return false;
  return /\b(built|created|developed|designed|implemented|automated|analyzed|deployed|evaluated|documented|optimized|trained|integrated)\b/i.test(text);
}

function buildRagProjectIdeas(result, resume, missingSkills, context, role) {
  const contextItems = result?.market_context ?? [];
  const projectEntries = contextItems.flatMap((item) => parseRagProjectEntries(item?.text || ""));
  if (!projectEntries.length) return [];

  const query = cleanDisplayText([
    role,
    context,
    result?.job_title,
    ...(result?.missing_required_skills ?? []).map((item) => item.keyword),
    ...(result?.missing_keywords ?? []).map((item) => item.keyword),
    ...(result?.unmatched_requirements ?? []).map((item) => item.requirement || item.text),
    resume?.basics?.headline,
    resume?.basics?.summary,
  ].join(" ")).toLowerCase();
  const queryTerms = tokenSet(query);

  return projectEntries
    .map((entry, index) => ({ entry, score: scoreRagProject(entry, queryTerms, missingSkills, context), index }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .slice(0, 3)
    .map(({ entry }, index) => ragEntryToProjectIdea(entry, role, missingSkills, index));
}

function parseRagProjectEntries(text) {
  const entries = [];
  const pattern = /Project:\s*([^|]+)\|\s*Roles:\s*([^|]+)\|\s*Skills:\s*([^|]+)\|\s*Build:\s*([^|]+)\|\s*Bullets:\s*([^]+?)(?=\s+Project:\s|$)/gi;
  for (const match of text.matchAll(pattern)) {
    entries.push({
      name: cleanDisplayText(match[1]),
      roles: parseCommaLikeList(match[2]),
      skills: parseCommaLikeList(match[3]),
      build: cleanDisplayText(match[4]),
      bullets: cleanDisplayText(match[5]).split(";").map(cleanDisplayText).filter(Boolean),
    });
  }
  return entries;
}

function parseCommaLikeList(value) {
  return String(value || "")
    .split(",")
    .map(cleanDisplayText)
    .filter(Boolean);
}

function scoreRagProject(entry, queryTerms, missingSkills, context) {
  const entryText = cleanDisplayText([entry.name, entry.roles.join(" "), entry.skills.join(" "), entry.build].join(" ")).toLowerCase();
  const entryTerms = tokenSet(entryText);
  let score = 0;
  queryTerms.forEach((term) => {
    if (entryTerms.has(term)) score += 1;
  });
  missingSkills.forEach((skill) => {
    const normalizedSkill = cleanDisplayText(skill).toLowerCase();
    if (normalizedSkill && entryText.includes(normalizedSkill)) score += 4;
  });
  if (context && entryText.includes(context)) score += 2;
  return score;
}

function ragEntryToProjectIdea(entry, role, missingSkills, index) {
  const skills = uniqueDisplayItems([...entry.skills, ...missingSkills.slice(0, 3)]).slice(0, 8);
  const bullets = entry.bullets.length
    ? entry.bullets
    : [
        `Built ${entry.name} using ${skills.slice(0, 3).join(", ")} to solve a realistic ${role} workflow.`,
        "Documented setup, validation evidence, screenshots, tradeoffs, and recruiter-ready README notes.",
      ];
  return {
    id: `rag-project-${entry.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
    title: `Build role-specific proof: ${entry.name}`,
    projectName: entry.name,
    stack: skills.join(", "),
    why: `${entry.build} This avoids generic keyword stuffing by giving recruiters project evidence that matches the target role.`,
    bullets: bullets.slice(0, 4),
    learnBeforeSubmit: skills.slice(0, 6),
    impact: Math.max(6, 10 - index),
  };
}

function tokenSet(value) {
  return new Set(String(value || "").toLowerCase().match(/[a-z0-9+#./-]{3,}/g) || []);
}

function buildTailoredProjectFocuses(context, role, missingSkills, result, resumeSummary) {
  const requirements = uniqueDisplayItems([
    ...(result?.unmatched_requirements ?? []).map((item) => item.requirement || item.keyword || item.text),
    ...(result?.missing_responsibilities ?? []).map((item) => item.requirement || item.responsibility || item.text),
    ...(result?.missing_required_skills ?? []).map((item) => item.keyword),
  ].map(cleanProjectSignal)).filter(Boolean).slice(0, 6);
  const hasTeaching = /\b(trainer|teaching|mentor|instructor|education|curriculum)\b/i.test(`${role} ${resumeSummary}`) && !/\b(model training|machine learning|data scientist|ml engineer)\b/i.test(`${role} ${resumeSummary}`);
  const hasFullstack = /fullstack|full stack|react|node|frontend|backend|api/i.test(`${role} ${resumeSummary} ${missingSkills.join(" ")}`);
  const hasAgentic = /agentic|generative|langchain|rag|llm|vector|ai/i.test(`${role} ${requirements.join(" ")} ${missingSkills.join(" ")}`);
  const hasCloud = /aws|azure|gcp|docker|kubernetes|deployment|cloud|ci\/cd/i.test(`${requirements.join(" ")} ${missingSkills.join(" ")}`);
  const hasData = /sql|analytics|dashboard|pandas|numpy|reporting|data/i.test(`${requirements.join(" ")} ${missingSkills.join(" ")}`);

  const focuses = [];
  const push = (focus) => {
    if (!focuses.some((item) => item.id === focus.id)) focuses.push(focus);
  };

  if (hasAgentic || context === "ai") {
    push({ id: "enterprise-rag-assistant", theme: "enterprise RAG knowledge assistant", primary: "RAG", secondary: "LLM evaluation", outcome: "answer groundedness" });
    push({ id: "ml-risk-model", theme: "ML risk scoring model", primary: "Python", secondary: "model evaluation", outcome: "prediction quality" });
  }
  if (hasTeaching) {
    push({ id: "technical-training-lab", theme: "technical trainer lab", primary: "curriculum design", secondary: "hands-on labs", outcome: "course completion readiness" });
  }
  if (hasFullstack || context === "backend" || context === "frontend") {
    push({ id: "fullstack-role-portal", theme: "full-stack role portal", primary: "React", secondary: "FastAPI", outcome: "end-to-end workflow completion" });
  }
  if (hasCloud || context === "cloud") {
    push({ id: "cloud-release-system", theme: "cloud release system", primary: "Docker", secondary: "CI/CD", outcome: "release reliability" });
  }
  if (hasData || context === "data") {
    push({ id: "analytics-decision-board", theme: "analytics decision board", primary: "SQL", secondary: "dashboarding", outcome: "decision turnaround time" });
  }

  if (!focuses.length) {
    push({ id: `${context}-portfolio-proof`, theme: `${role} portfolio proof`, primary: missingSkills[0] || "core role skill", secondary: missingSkills[1] || "documentation", outcome: "screening confidence" });
  }

  return focuses.slice(0, 3).map((focus, index) => ({
    ...focus,
    primary: missingSkills[index * 2] || focus.primary,
    secondary: missingSkills[index * 2 + 1] || focus.secondary,
    requirements,
  }));
}

function buildCoachProjectIdea(focus, role, context, missingSkills, result, resume, index) {
  const projectName = titleCaseProjectName(focus.theme);
  const tools = uniqueDisplayItems([
    focus.primary,
    focus.secondary,
    ...missingSkills.slice(index, index + 4),
    ...defaultToolsForContext(context, focus.id),
  ]).slice(0, 7);
  const roleNoun = role.replace(/\b(role|job)\b/gi, "").trim() || "target role";
  const requirementText = cleanProjectSignal(focus.requirements?.[0]) || missingSkills.find((skill) => cleanProjectSignal(skill)) || `core ${roleNoun} requirements`;
  const resumeAnchor = cleanDisplayText(resume?.basics?.headline || resume?.experience?.[0]?.role || resume?.projects?.[0]?.name || roleNoun);

  return {
    id: `coach-${focus.id}`,
    title: `Build targeted proof for ${focus.primary}`,
    projectName,
    stack: tools.join(", "),
    why: `This is tailored for ${roleNoun}: it turns your current ${resumeAnchor} profile into proof for ${focus.primary}, ${focus.secondary}, and the JD requirement around ${requirementText}.`,
    bullets: [
      `Built ${projectName} using ${tools.slice(0, 3).join(", ")} to solve a ${roleNoun} workflow tied to ${requirementText}.`,
      `Designed the core flow, data model, and validation checks so users can complete the task end-to-end with clear error handling and traceable outputs.`,
      `Added measurable evaluation using ${focus.outcome}, before/after test cases, and a short decision log explaining tradeoffs, limitations, and next improvements.`,
      `Documented setup steps, screenshots, sample inputs, and recruiter-ready notes so the project can be reviewed quickly from the resume or GitHub README.`,
    ],
    learnBeforeSubmit: uniqueDisplayItems([...modernLearningForContext(context, missingSkills), ...tools]).slice(0, 6),
    impact: Math.max(6, 9 - index),
  };
}

function defaultToolsForContext(context, focusId) {
  if (focusId.includes("agentic")) return ["Python", "FastAPI", "Vector DB", "prompt evaluation"];
  if (focusId.includes("training")) return ["lesson plan", "assessment rubric", "demo app"];
  if (focusId.includes("fullstack")) return ["PostgreSQL", "REST APIs", "authentication"];
  if (focusId.includes("cloud")) return ["GitHub Actions", "AWS", "monitoring"];
  if (focusId.includes("analytics")) return ["Pandas", "Power BI", "KPI metrics"];
  if (context === "ai") return ["Python", "Scikit-learn", "evaluation metrics"];
  if (context === "data") return ["SQL", "Pandas", "dashboard"];
  if (context === "frontend") return ["React", "TypeScript", "API integration"];
  return ["documentation", "test cases", "measurable outcome"];
}

function titleCaseProjectName(value) {
  return cleanDisplayText(value)
    .split(" ")
    .map((word) => word ? `${word.charAt(0).toUpperCase()}${word.slice(1)}` : "")
    .join(" ");
}

function projectTemplateForContext(context, role, primarySkill, secondarySkill, missingSkills) {
  const skillsText = missingSkills.slice(0, 4).join(", ");
  if (context === "cloud") {
    return {
      id: "project-cloud-evidence",
      title: `Build deployment proof for ${primarySkill}`,
      projectName: "Cloud Release and Monitoring Lab",
      stack: `${primarySkill}, Docker, GitHub Actions, monitoring, rollback notes`,
      why: `For ${role}, this proves platform skill through deployment evidence instead of attaching the keyword to an unrelated app or ML project.`,
      bullets: [
        `Deployed a sample service using ${primarySkill}, environment configuration, and release validation to prove hands-on cloud delivery.`,
        "Documented build steps, deployment logs, monitoring checks, rollback notes, and cost or access assumptions for recruiter review.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 7,
    };
  }
  if (context === "ai") {
    return {
      id: "project-ai-evidence",
      title: `Build proof for ${primarySkill}`,
      projectName: "Job Description Match Predictor",
      stack: `Python, Pandas, Scikit-learn, ${skillsText || "model evaluation"}, Streamlit`,
      why: `For ${role}, this gives recruiters real project evidence instead of only a keyword. It can support missing ML, evaluation, and stakeholder-facing explanation signals.`,
      bullets: [
        `Built a resume-to-JD scoring tool using ${primarySkill}, feature extraction, and model evaluation to rank candidate fit against job requirements.`,
        "Created a Streamlit dashboard explaining missing skills, matched evidence, and recommended resume changes for non-technical stakeholders.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 7,
    };
  }
  if (context === "data") {
    return {
      id: "project-data-evidence",
      title: `Build data proof for ${primarySkill}`,
      projectName: "Business KPI Analytics Dashboard",
      stack: `SQL, Python, Pandas, ${skillsText || "Power BI/Tableau"}`,
      why: `A project section can show end-to-end analytics work: data cleaning, metrics, visualization, and business recommendations.`,
      bullets: [
        `Built an analytics dashboard using ${primarySkill} to track KPIs, clean raw datasets, and surface trends for business decision-making.`,
        "Documented stakeholder questions, metric definitions, and recommended actions to connect analysis with business outcomes.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 7,
    };
  }
  if (context === "product") {
    return {
      id: "project-product-evidence",
      title: `Build stakeholder proof for ${primarySkill}`,
      projectName: "Feature Prioritization and Launch Plan",
      stack: `Jira/Notion, roadmap, user stories, ${skillsText || "stakeholder management"}`,
      why: `This proves product/delivery thinking: stakeholders, prioritization, requirements, success metrics, and launch tradeoffs.`,
      bullets: [
        `Created a feature prioritization plan using ${primarySkill}, user pain points, effort scoring, and business impact to define a release roadmap.`,
        "Wrote user stories, acceptance criteria, stakeholder notes, and launch metrics to show end-to-end delivery readiness.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 7,
    };
  }
  if (context === "marketing") {
    return {
      id: "project-marketing-evidence",
      title: `Build campaign proof for ${primarySkill}`,
      projectName: "Performance Marketing Campaign Analysis",
      stack: `Google Analytics, SEO, content calendar, ${skillsText || "campaign reporting"}`,
      why: `This gives campaign evidence with audience, channel, metric, and optimization decisions.`,
      bullets: [
        `Planned a campaign using ${primarySkill}, audience segmentation, channel goals, and weekly conversion metrics.`,
        "Built a reporting sheet with traffic, leads, conversion rate, and recommendations for improving campaign ROI.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 6,
    };
  }
  if (context === "sales") {
    return {
      id: "project-sales-evidence",
      title: `Build pipeline proof for ${primarySkill}`,
      projectName: "CRM Pipeline Improvement Plan",
      stack: `CRM, lead scoring, account notes, ${skillsText || "pipeline management"}`,
      why: `This shows sales execution through pipeline hygiene, follow-up strategy, and measurable opportunity tracking.`,
      bullets: [
        `Designed a CRM pipeline workflow using ${primarySkill}, lead stages, follow-up SLAs, and account qualification notes.`,
        "Created a weekly dashboard for lead source, conversion stage, blocked deals, and next-best actions.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 6,
    };
  }
  if (context === "finance") {
    return {
      id: "project-finance-evidence",
      title: `Build finance proof for ${primarySkill}`,
      projectName: "Monthly Financial Reporting Pack",
      stack: `Excel, reconciliation, variance analysis, ${skillsText || "budgeting/forecasting"}`,
      why: `This shows accuracy, controls, and reporting judgment instead of only naming finance keywords.`,
      bullets: [
        `Created a monthly reporting pack using ${primarySkill}, variance checks, and reconciliation logic to improve financial review accuracy.`,
        "Documented assumptions, exceptions, and audit-ready notes for faster manager review.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 6,
    };
  }
  if (context === "hr") {
    return {
      id: "project-hr-evidence",
      title: `Build HR proof for ${primarySkill}`,
      projectName: "Recruitment Funnel and Onboarding Tracker",
      stack: `ATS tracker, sourcing sheet, onboarding checklist, ${skillsText || "HR operations"}`,
      why: `This gives people-operations evidence through process, tracking, and coordination outcomes.`,
      bullets: [
        `Built a hiring funnel tracker using ${primarySkill}, candidate stages, interview feedback, and turnaround-time metrics.`,
        "Created onboarding checklists and status reporting to improve joining readiness and coordination quality.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 6,
    };
  }
  if (context === "design") {
    return {
      id: "project-design-evidence",
      title: `Build design proof for ${primarySkill}`,
      projectName: "Usability Redesign Case Study",
      stack: `Figma, wireframes, prototype, ${skillsText || "user research"}`,
      why: `A design case study proves research, decisions, visual systems, and iteration quality.`,
      bullets: [
        `Designed a user flow redesign using ${primarySkill}, wireframes, and usability notes to reduce friction in a core workflow.`,
        "Built a clickable prototype and documented design decisions, edge cases, and stakeholder feedback.",
      ],
      learnBeforeSubmit: modernLearningForContext(context, missingSkills),
      impact: 6,
    };
  }
  return {
    id: "project-role-evidence",
    title: `Build role proof for ${primarySkill}`,
    projectName: `${role} Portfolio Project`,
    stack: `${primarySkill}, ${secondarySkill}, documentation, measurable outcomes`,
    why: `A project section can prove the missing skill in context and make the ATS match feel credible.`,
    bullets: [
      `Built a ${role} project using ${primarySkill} to solve a realistic business problem and document the measurable outcome.`,
      `Added clear project notes covering goal, approach, tools, stakeholders, and result so recruiters can verify ${primarySkill} quickly.`,
    ],
    learnBeforeSubmit: modernLearningForContext(context, missingSkills),
    impact: 6,
  };
}

function secondaryProjectTemplateForContext(context, role, missingSkills) {
  const learning = modernLearningForContext(context, missingSkills);
  if (!learning.length) return null;
  return {
    id: "project-modern-learning",
    title: "Interview-ready learning plan",
    projectName: "Modern Skills Practice Lab",
    stack: learning.join(", "),
    why: `Before submitting, learn enough of these tools to explain the project honestly in an interview. Add them only after you build or practice them.`,
    bullets: [
      `Completed a practical lab covering ${learning.slice(0, 3).join(", ")} and documented what each tool improves in ${role} work.`,
      "Prepared interview notes with tradeoffs, common mistakes, and one example of how the skill was applied in the project.",
    ],
    learnBeforeSubmit: learning,
    impact: 5,
  };
}

function modernLearningForContext(context, missingSkills) {
  const normalized = missingSkills.map((item) => cleanDisplayText(item).toLowerCase());
  const learning = [];
  const add = (items) => items.forEach((item) => {
    if (!learning.some((existing) => existing.toLowerCase() === item.toLowerCase())) learning.push(item);
  });
  if (context === "ai") add(["ML evaluation metrics", "feature engineering", "model explainability", "MLflow or experiment tracking"]);
  if (context === "data") add(["SQL window functions", "Power BI/Tableau storytelling", "dbt basics", "dashboard KPI design"]);
  if (context === "product") add(["user story writing", "prioritization frameworks", "stakeholder mapping", "Jira roadmap basics"]);
  if (context === "marketing") add(["Google Analytics 4", "SEO keyword research", "A/B testing basics", "campaign attribution"]);
  if (context === "sales") add(["CRM hygiene", "lead qualification", "pipeline forecasting", "discovery call notes"]);
  if (context === "finance") add(["variance analysis", "advanced Excel", "reconciliation controls", "forecasting basics"]);
  if (context === "hr") add(["ATS sourcing", "structured interviewing", "onboarding workflows", "HR metrics"]);
  if (context === "design") add(["Figma components", "usability testing", "design systems", "accessibility basics"]);
  if (context === "security") add(["OWASP Top 10", "SIEM basics", "incident triage", "IAM controls"]);
  if (context === "mobile") add(["app state management", "API integration", "release testing", "mobile UI patterns"]);
  if (context === "cloud") add(["cloud deployment basics", "Docker release flow", "CI/CD validation", "monitoring and rollback notes"]);
  normalized.forEach((skill) => {
    if (skill.includes("stakeholder")) add(["stakeholder mapping", "communication plan", "status reporting"]);
    if (skill.includes("computer")) add(["computer science fundamentals", "data structures basics"]);
    if (skill.includes("tensorflow")) add(["TensorFlow model training"]);
    if (skill.includes("pytorch")) add(["PyTorch training loops"]);
    if (skill.includes("sql")) add(["SQL joins and window functions"]);
    if (/(aws|azure|gcp|docker|kubernetes|terraform|ci\/cd)/i.test(skill)) add(["cloud deployment basics", "release validation", "rollback planning"]);
  });
  return learning.slice(0, 5);
}

function findBestOldLineForSkill(skill, lines, offset = 0, result = null, resume = null, usedEvidenceKeys = new Set()) {
  if (!lines.length) {
    return {
      text: `Add this as a new experience bullet; no strong existing line matched ${skill}.`,
      section: "experience",
      synthetic: true,
    };
  }

  const tokens = skillEvidenceTokens(skill);
  const scored = lines.filter((line) => !usedEvidenceKeys.has(evidenceLineKey(line))).map((line) => {
    const lowered = line.text.toLowerCase();
    const score = tokens.reduce((sum, token) => sum + (lowered.includes(token) ? 1 : 0), 0);
    return { ...line, score };
  });
  scored.sort((left, right) => right.score - left.score || left.text.length - right.text.length);
  if (scored[0]?.score > 0 && hasStrongContextMatch(scored[0], skill, result, resume)) {
    usedEvidenceKeys.add(evidenceLineKey(scored[0]));
    return scored[0];
  }

  const contextual = scoreContextualResumeLines(skill, lines, result, resume, usedEvidenceKeys);
  if (contextual.length) {
    const selected = contextual[offset % Math.min(3, contextual.length)];
    usedEvidenceKeys.add(evidenceLineKey(selected));
    return {
      ...selected,
      weakEvidence: true,
      text: selected.text,
    };
  }

  return {
    text: `Add this as a new project bullet; no strong existing line matched ${skill}.`,
    section: "projects",
    synthetic: true,
  };
}

function scoreContextualResumeLines(skill, lines, result, resume, usedEvidenceKeys = new Set()) {
  const context = detectResumeBulletContext(skill, result, resume);
  const roleTerms = meaningfulCoachTerms([
    result?.job_title,
    result?.detected_role_family,
    resume?.basics?.headline,
    ...(result?.unmatched_requirements ?? []).map((item) => item.requirement || item.keyword || item.text),
    ...(result?.matched_requirements ?? []).map((item) => item.requirement || item.keyword || item.text),
  ].join(" "));
  const skillFamilyTerms = meaningfulCoachTerms(contextualSkillFamilyText(context, skill));
  const combinedTerms = uniqueDisplayItems([...roleTerms, ...skillFamilyTerms]).slice(0, 28);

  return lines
    .filter((line) => !usedEvidenceKeys.has(evidenceLineKey(line)))
    .map((line) => {
      const text = cleanDisplayText(line.text).toLowerCase();
      const termHits = combinedTerms.reduce((sum, term) => sum + (text.includes(term.toLowerCase()) ? 1 : 0), 0);
      const familyHits = skillFamilyTerms.reduce((sum, term) => sum + (text.includes(term.toLowerCase()) ? 1 : 0), 0);
      const sectionBonus = line.section === "experience" ? 1 : 0;
      const metricBonus = /\b\d+%|\b\d+x|\b\d+\+|\b\d+\s*(users|apis|reports|models|dashboards|tickets|hours|days|records|tests)\b/i.test(line.text) ? 1 : 0;
      const score = termHits + familyHits + sectionBonus + metricBonus;
      return { ...line, score, familyHits, termHits };
    })
    .filter((line) => line.score >= 3 && line.familyHits >= 1 && hasStrongContextMatch(line, skill, result, resume))
    .sort((left, right) => right.score - left.score || left.text.length - right.text.length)
    .slice(0, 6);
}

function evidenceLineKey(line) {
  return `${line?.section || ""}:${line?.itemIndex ?? ""}:${line?.lineIndex ?? ""}:${cleanDisplayText(line?.text || "").slice(0, 80).toLowerCase()}`;
}

function hasStrongContextMatch(line, skill, result, resume) {
  const context = detectResumeBulletContext(skill, result, resume);
  const text = cleanDisplayText(line?.text || "").toLowerCase();
  const normalizedSkill = cleanDisplayText(skill).toLowerCase();
  if (normalizedSkill && text.includes(normalizedSkill)) return true;
  const matcher = CONTEXT_EVIDENCE_PATTERNS[context] || inferEvidencePatternForSkill(skill);
  if (matcher) return matcher.test(text);
  return skillEvidenceTokens(skill).some((token) => text.includes(token));
}

const CONTEXT_EVIDENCE_PATTERNS = {
  ai: /\b(ai|ml|machine learning|model|prediction|scikit|tensorflow|pytorch|nlp|rag|prompt|vector|embedding|evaluation|training|inference|agentic|generative|llm|langchain|langgraph)\b/i,
  backend: /\b(api|backend|server|database|postgres|mysql|mongodb|fastapi|django|node|spring|service|endpoint|authentication|authorization|integration|microservice|cache|redis)\b/i,
  cloud: /\b(aws|azure|gcp|cloud|docker|kubernetes|ci\/cd|jenkins|github actions|terraform|deployment|deployed|release|pipeline|monitoring|rollback|infrastructure|devops|sre)\b/i,
  data: /\b(sql|data|analytics|dashboard|report|etl|elt|pipeline|kpi|tableau|power bi|pandas|warehouse|insight|snowflake|bigquery|dbt|airflow)\b/i,
  database: /\b(database|sql|postgres|mysql|sql server|oracle|mongodb|index|query|backup|restore|replication|schema|performance tuning)\b/i,
  design: /\b(figma|wireframe|prototype|design system|user research|usability|accessibility|ux|ui|persona|journey|handoff)\b/i,
  finance: /\b(finance|financial|reconciliation|variance|budget|forecast|audit|ledger|invoice|accounting|reporting)\b/i,
  frontend: /\b(react|javascript|typescript|html|css|ui|frontend|component|accessibility|responsive|browser|user flow|state|redux|vite)\b/i,
  hr: /\b(hr|recruit|sourcing|candidate|onboarding|employee|payroll|interview|ats|talent|offer)\b/i,
  it: /\b(ticket|helpdesk|desktop|support|troubleshoot|sla|serviceNow|jira service|active directory|office 365|hardware|software|incident)\b/i,
  marketing: /\b(marketing|campaign|seo|sem|ga4|google analytics|conversion|content|email|social|attribution|a\/b)\b/i,
  mobile: /\b(android|ios|flutter|react native|kotlin|swift|mobile|app store|play store|push notification|offline|device)\b/i,
  network: /\b(network|dns|dhcp|vpn|firewall|routing|switch|lan|wan|tcp|ip|server|linux|windows server|patching)\b/i,
  product: /\b(stakeholder|requirement|roadmap|backlog|user stor|acceptance|sprint|jira|delivery|priorit|scrum|release planning)\b/i,
  qa: /\b(test|testing|qa|selenium|playwright|cypress|postman|jmeter|automation|regression|defect|bug|test case|quality)\b/i,
  sales: /\b(sales|crm|salesforce|pipeline|lead|account|customer|client|deal|forecast|conversion|prospect)\b/i,
  sap: /\b(sap|erp|s\/4hana|fico|mm|sd|abap|configuration|uat|functional specification|module)\b/i,
  security: /\b(security|risk|vulnerability|incident|iam|access|audit|siem|alert|control|owasp|soc|splunk|sentinel|mfa)\b/i,
};

function skillEvidenceTokens(skill) {
  const weak = new Set(["and", "for", "with", "the", "this", "that", "using", "role", "work", "job", "skill", "skills", "management", "communication", "collaboration", "problem", "solving", "development", "designing", "developing", "researching", "systems", "models", "schemes"]);
  return cleanDisplayText(skill)
    .toLowerCase()
    .split(/[\s/.,()_-]+/)
    .filter((token) => token.length > 2 && !weak.has(token));
}

function inferEvidencePatternForSkill(skill) {
  const normalized = cleanDisplayText(skill).toLowerCase();
  if (/(selenium|playwright|cypress|postman|jmeter|test|qa|sdet)/i.test(normalized)) return CONTEXT_EVIDENCE_PATTERNS.qa;
  if (/(sap|erp|s\/4hana|fico|mm|sd|abap)/i.test(normalized)) return CONTEXT_EVIDENCE_PATTERNS.sap;
  if (/(database|dba|postgres|mysql|sql server|oracle|mongodb|index|query tuning)/i.test(normalized)) return CONTEXT_EVIDENCE_PATTERNS.database;
  if (/(network|dns|dhcp|vpn|firewall|routing|linux|windows server)/i.test(normalized)) return CONTEXT_EVIDENCE_PATTERNS.network;
  if (/(helpdesk|desktop|ticket|sla|active directory|office 365|servicenow)/i.test(normalized)) return CONTEXT_EVIDENCE_PATTERNS.it;
  return null;
}

function meaningfulCoachTerms(value) {
  const stop = new Set(["and", "for", "with", "the", "this", "that", "using", "role", "work", "job", "skill", "skills", "required", "preferred", "designing", "developing", "researching", "systems", "models", "schemes"]);
  return uniqueDisplayItems(String(value || "")
    .toLowerCase()
    .match(/[a-z0-9+#./-]{3,}/g) || [])
    .filter((term) => !stop.has(term) && !/^\d+$/.test(term))
    .slice(0, 32);
}

function contextualSkillFamilyText(context, skill) {
  const normalized = cleanDisplayText(skill);
  if (context === "ai") return `${normalized} python model evaluation data pipeline experiment tracking api automation prompt retrieval validation`;
  if (context === "data") return `${normalized} sql dashboard reporting analytics kpi etl data quality business insights`;
  if (context === "frontend") return `${normalized} react ui component api validation performance accessibility user flow`;
  if (context === "backend") return `${normalized} api database authentication validation service performance testing`;
  if (context === "cloud") return `${normalized} deployment docker aws ci cd monitoring release infrastructure`;
  if (context === "security") return `${normalized} alert risk vulnerability incident access control audit`;
  if (context === "product") return `${normalized} requirement stakeholder roadmap backlog delivery acceptance criteria`;
  if (context === "mobile") return `${normalized} android ios flutter react native api offline release testing`;
  if (context === "design") return `${normalized} figma wireframe prototype user research usability accessibility handoff`;
  if (context === "marketing") return `${normalized} campaign seo ga4 conversion content attribution reporting`;
  if (context === "sales") return `${normalized} crm salesforce pipeline lead account conversion forecast`;
  if (context === "finance") return `${normalized} reconciliation variance budget forecast audit reporting`;
  if (context === "hr") return `${normalized} recruiting sourcing onboarding ats candidate employee workflow`;
  return normalized;
}

function findSkillPlacement(resume, skill) {
  const groups = resume?.skills ?? [];
  const rule = inferSkillPlacementRule(skill);
  const professional = isProfessionalSkillTerm(skill);
  const exactItemGroup = groups.find((group) => (group.items ?? []).some((item) => cleanDisplayText(item).toLowerCase() === cleanDisplayText(skill).toLowerCase()));
  const namedGroup = groups.find((group) => rule.groupPattern.test(group.name || ""));
  const signalGroup = groups.find((group) => (group.items ?? []).some((item) => rule.signalPattern.test(cleanDisplayText(item))));
  const fallbackGroup = groups.find((group) => /technical|skill|core|tools|technology/i.test(group.name || "")) || groups[0];
  const exactGroupLooksWrong = exactItemGroup && professional && /(programming|backend|frontend|cloud|devops|ai|ml|machine learning)/i.test(exactItemGroup.name || "");
  const preferredGroup = exactGroupLooksWrong ? namedGroup || signalGroup : exactItemGroup || namedGroup || signalGroup;

  if (preferredGroup) {
    return {
      groupName: preferredGroup.name || rule.groupName,
      existingItems: preferredGroup.items ?? [],
      shouldCreate: false,
      recommendedGroupName: rule.groupName,
    };
  }

  if (!fallbackGroup) {
    return {
      groupName: rule.groupName,
      existingItems: [],
      shouldCreate: true,
      recommendedGroupName: rule.groupName,
    };
  }

  return {
    groupName: rule.groupName,
    existingItems: [],
    shouldCreate: true,
    recommendedGroupName: rule.groupName,
    fallbackGroupName: fallbackGroup.name,
  };
}

function inferSkillPlacementRule(skill) {
  const normalized = cleanDisplayText(skill);
  return SKILL_PLACEMENT_RULES.find((rule) => rule.skillPattern.test(normalized)) || {
    groupName: "Technical Skills",
    groupPattern: /(technical|skill|core|tools|technology)/i,
    skillPattern: /.+/i,
    signalPattern: /.+/i,
  };
}

function buildSkillPlacementText(skill, placement) {
  const quotedSkill = `"${skill}"`;
  if (placement.shouldCreate) {
    return `Create ${placement.groupName} skill group, then add ${quotedSkill}.`;
  }
  return `Add ${quotedSkill} under ${placement.groupName}.`;
}

function buildDeferredSkillPlacementText(skill, placement, targetPlacement = null) {
  const quotedSkill = `"${skill}"`;
  const target = targetPlacement?.label ? ` Add the proof bullet under ${targetPlacement.label}.` : "";
  if (placement.shouldCreate) {
    return `After proof exists, create ${placement.groupName} and add ${quotedSkill}.${target}`;
  }
  return `After proof exists, add ${quotedSkill} under ${placement.groupName}.${target}`;
}

function buildSkillGuidance(skill, jobTitle, section, placement) {
  const role = cleanDisplayText(jobTitle || "this role");
  const groupAction = placement.shouldCreate ? `Because your current skills do not have a clean ${placement.groupName} bucket, create that group instead of forcing this into an unrelated section.` : `This keeps ${skill} beside related skills recruiters expect to scan together.`;
  const sectionLabel = section.toLowerCase();
  const proofType = sectionLabel === "projects" ? "project entry" : `${sectionLabel} bullet`;
  return `Use the suggested ${proofType} only after you can honestly explain or build it. This is stronger than a keyword-only add for ${role} because it gives ATS and recruiters proof, not just a term. ${groupAction}`;
}

function buildMissingEvidenceGuidance(skill, jobTitle, placement, targetPlacement = null) {
  const role = cleanDisplayText(jobTitle || "this role");
  const groupAction = placement.shouldCreate
    ? `Create a proper ${placement.groupName} bucket later if the proof is real.`
    : `Keep ${skill} near related skills only after the project or work bullet supports it.`;
  const target = targetPlacement?.label ? ` Best location: ${targetPlacement.label}.` : "";
  return `No credible resume evidence was found for ${skill}. For ${role}, do not rewrite an unrelated line just to include the keyword. Build or document proof first, then add one concise bullet with tools, validation, and outcome.${target} ${groupAction}`;
}

function buildPreviewSkillGroups(items) {
  const groups = new Map();
  items.forEach((item) => {
    const groupName = item.placement?.groupName || "Technical Skills";
    const existingItems = item.placement?.existingItems ?? [];
    const current = groups.get(groupName) ?? [];
    groups.set(groupName, uniqueDisplayItems([...current, ...existingItems, item.skill]));
  });
  return Array.from(groups.entries()).map(([groupName, skills]) => ({
    groupName,
    skillLine: skills.join(", "),
  }));
}

function buildModelResumeLine(skill, result, oldLine, section, resume, index = 0, targetPlacement = null) {
  const role = sanitizeRoleLabel(result?.job_title);
  const lowered = cleanDisplayText(skill).toLowerCase();
  const context = detectResumeBulletContext(skill, result, resume);
  const projectMode = section === "Projects";
  const evidenceAnchor = inferEvidenceAnchor(result, resume);
  const oldText = cleanDisplayText(oldLine?.text || oldLine);

  if (oldLine?.synthetic) {
    return buildNewEvidenceBullet(skill, result, resume, context, section, index, targetPlacement);
  }

  if (oldLine?.weakEvidence) {
    return buildExistingEvidenceUpgrade(skill, result, oldLine, section, resume, context, role);
  }

  const ragRewrite = buildRagCoachRewrite(skill, result, oldLine, section, resume, context, role, evidenceAnchor);

  if (ragRewrite) {
    return ragRewrite;
  }

  if (context === "product" && /(stakeholder|requirement|roadmap|agile|scrum|jira|prioritization|user stor)/i.test(skill)) {
    return projectMode
      ? `Created a ${role} project plan using ${skill}, stakeholder mapping, priority scoring, and acceptance criteria to show delivery-ready product thinking.`
      : `Coordinated ${skill} across business, technical, and delivery inputs, improving prioritization clarity and decision follow-through.`;
  }
  if (lowered === "tensorflow") {
    return "Developed TensorFlow training workflows with clean feature inputs and evaluation tracking, improving model iteration quality and experiment visibility.";
  }
  if (lowered === "pytorch") {
    return "Implemented PyTorch model workflows with custom data loading and validation checks, improving training repeatability and evaluation accuracy.";
  }
  if (["scikit-learn", "sklearn"].includes(lowered)) {
    return "Built Scikit-learn feature engineering and model evaluation pipelines with Pandas, improving baseline accuracy and speeding up ML experimentation.";
  }
  if (lowered === "machine learning") {
    return "Developed machine-learning pipelines with Python, Pandas, and Scikit-learn, improving feature processing and model evaluation for predictive analysis.";
  }
  if (["natural language processing", "nlp"].includes(lowered)) {
    return "Implemented NLP preprocessing and text-classification pipelines with Python and Scikit-learn, improving document categorization accuracy.";
  }
  if (lowered === "etl") {
    return "Built SQL and Pandas ETL pipelines to clean, transform, and validate reporting data, reducing manual preparation effort and improving data reliability.";
  }
  if (["dbt", "airflow"].includes(lowered)) {
    return `Designed ${skill} data pipelines for scheduled transformations and validation checks, improving ETL reliability and analytics refresh consistency.`;
  }
  if (["aws", "azure", "gcp"].includes(lowered)) {
    return `Deployed ${evidenceAnchor} workflows on ${skill}, configuring environment settings, release checks, and access notes to improve operational readiness.`;
  }
  if (["docker", "kubernetes", "ci/cd", "jenkins", "github actions"].includes(lowered)) {
    const tech = lowered === "ci/cd" ? "GitHub Actions" : skill;
    return `Containerized and automated ${evidenceAnchor} delivery with ${tech}, adding validation checks and rollback notes to make releases easier to verify.`;
  }
  if (lowered === "microservices") {
    return "Designed FastAPI microservices with PostgreSQL-backed service boundaries, reducing API coupling and improving scalability for reporting workflows.";
  }
  if (["rest apis", "api", "apis", "fastapi", "django", "node.js", "node"].includes(lowered)) {
    const tech = ["api", "apis", "rest apis"].includes(lowered) ? "FastAPI" : skill;
    return `Built ${tech} API endpoints with PostgreSQL data access, improving request handling and making backend services easier to extend.`;
  }
  if (["langchain", "langgraph", "llamaindex", "autogen", "agentic ai"].includes(lowered)) {
    const tech = lowered === "agentic ai" ? "LangChain" : skill;
    return `Built a ${tech} agent workflow with tool-calling, retrieval context, and response checks to automate multi-step ${role} support tasks.`;
  }
  if (["vector db", "vectordb", "pinecone", "chromadb", "faiss", "rag"].includes(lowered)) {
    const tech = lowered === "vector db" || lowered === "vectordb" || lowered === "rag" ? "FAISS" : skill;
    return `Implemented a ${tech}-backed retrieval pipeline with chunking, metadata filters, and answer citation checks to improve document-grounded recommendations.`;
  }
  if (["power bi", "tableau", "looker", "data visualization", "excel"].includes(lowered)) {
    const tech = lowered === "data visualization" ? "Power BI" : skill;
    return `Developed ${tech} dashboards on SQL datasets, improving KPI visibility and reducing manual reporting for business stakeholders.`;
  }
  if (["sql", "postgresql", "bigquery", "snowflake", "pandas", "numpy"].includes(lowered)) {
    return buildDataSkillBullet(skill, lowered);
  }
  if (context === "frontend") {
    return `Built ${role} interface improvements with ${skill}, improving usability, consistency, and handoff quality for users and stakeholders.`;
  }
  if (context === "ai") {
    return `Designed ${skill} workflows for ${evidenceAnchor}, including input preparation, evaluation cases, and explainable outputs for reviewer trust.`;
  }
  if (context === "data") {
    return `Built ${skill} analysis workflows for ${evidenceAnchor}, cleaning source data, defining KPIs, and summarizing insights for stakeholder review.`;
  }
  if (context === "cloud") {
    return `Implemented ${skill} deployment workflows for ${evidenceAnchor}, documenting configuration, validation, and monitoring steps for repeatable releases.`;
  }
  if (context === "product") {
    return `Translated ${skill} work into clear ${role} priorities, improving stakeholder alignment, delivery focus, and decision quality.`;
  }
  if (context === "marketing") {
    return `Managed ${skill} initiatives for ${role} goals, improving campaign visibility, audience targeting, and conversion-focused reporting.`;
  }
  if (context === "sales") {
    return `Used ${skill} to strengthen ${role} execution, improving pipeline tracking, client follow-up quality, and revenue opportunity visibility.`;
  }
  if (context === "finance") {
    return `Applied ${skill} across ${role} workflows, improving reporting accuracy, reconciliation quality, and audit-ready documentation.`;
  }
  if (context === "hr") {
    return `Used ${skill} in ${role} processes, improving candidate or employee tracking, coordination quality, and operational turnaround time.`;
  }
  if (context === "design") {
    return `Created ${skill} deliverables for ${role} work, improving user clarity, design consistency, and stakeholder review speed.`;
  }
  if (context === "security") {
    return `Applied ${skill} to security workflows, improving risk visibility, issue triage, and control documentation for production teams.`;
  }
  if (context === "mobile") {
    return `Built mobile ${role} improvements with ${skill}, improving app reliability, user flow quality, and release readiness.`;
  }
  if (oldText && oldText.length > 30) {
    const baseLine = oldText.replace(/[.!?]*$/, "");
    return `Strengthened ${baseLine.charAt(0).toLowerCase()}${baseLine.slice(1)} using ${skill}, making the impact clearer for ${role} screening.`;
  }
  return `Delivered ${role} work using ${skill}, improving execution quality, stakeholder clarity, and measurable outcomes.`;
}

function buildExistingEvidenceUpgrade(skill, result, oldLine, section, resume, context, role) {
  const oldText = cleanDisplayText(oldLine?.text || "");
  const base = oldText.replace(/[.!?]*$/, "");
  const sectionName = section === "Projects" ? "project" : "experience";
  const compactBullet = buildCompactResumeUpgradeBullet(base, skill, context, role);

  if (base.length > 45) {
    return `Suggested bullet: ${compactBullet}`;
  }

  return `Suggested bullet: Add ${skill} proof to a relevant ${sectionName} line with tools, validation, and measurable ${compactOutcomeForContext(context)}.`;
}

function buildCompactResumeUpgradeBullet(base, skill, context, role) {
  const actionLine = normalizeResumeBulletLead(base);
  const proof = compactProofPhraseForSkill(skill, context);
  const outcome = compactOutcomeForContext(context);
  const bullet = `${actionLine}, adding ${proof} to improve ${outcome}.`;
  return limitResumeBulletWords(bullet, 31);
}

function normalizeResumeBulletLead(base) {
  const cleaned = cleanDisplayText(base)
    .replace(/^improve this (experience|project) line to:\s*/i, "")
    .replace(/\s+only if true\b.*$/i, "")
    .replace(/\s+so it better matches\b.*$/i, "")
    .replace(/[.!?]*$/, "");
  const shortened = cleaned
    .replace(/\s+to handle\s+/i, " for ")
    .replace(/\s+to support\s+/i, " for ")
    .replace(/\s+for multiple client projects\b/i, " for client projects");
  const words = shortened.split(/\s+/).filter(Boolean);
  if (words.length <= 16) return shortened;
  return words.slice(0, 16).join(" ");
}

function compactProofPhraseForSkill(skill, context) {
  const cleaned = cleanDisplayText(skill);
  const lowered = cleaned.toLowerCase();
  if (["agentic ai", "langchain", "langgraph", "autogen"].includes(lowered)) return `${cleaned} tool-calling checks`;
  if (lowered === "prompt engineering") return "prompt tests and evaluation notes";
  if (["generative ai", "rag", "vector db"].includes(lowered)) return `${cleaned} grounding and evaluation`;
  if (/(machine learning|scikit|tensorflow|pytorch|nlp|model)/i.test(cleaned)) return `${cleaned} validation metrics`;
  if (/(aws|azure|gcp|docker|kubernetes|ci\/cd|jenkins|github actions)/i.test(cleaned)) return `${cleaned} deployment validation`;
  if (/(sql|power bi|tableau|etl|dashboard|analytics|pandas|numpy)/i.test(cleaned)) return `${cleaned} KPI and data-quality evidence`;
  if (/(react|javascript|typescript|api|fastapi|node|django)/i.test(cleaned)) return `${cleaned} tests and validation states`;
  if (context === "product") return `${cleaned} acceptance criteria`;
  if (context === "security") return `${cleaned} risk and remediation evidence`;
  return `${cleaned} validation evidence`;
}

function compactOutcomeForContext(context) {
  if (context === "ai") return "grounded automation";
  if (context === "data") return "reporting accuracy";
  if (context === "frontend") return "user experience";
  if (context === "backend") return "API reliability";
  if (context === "cloud") return "release reliability";
  if (context === "security") return "risk visibility";
  if (context === "product") return "delivery clarity";
  return "business impact";
}

function limitResumeBulletWords(text, maxWords = 31) {
  const cleaned = cleanDisplayText(text);
  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length <= maxWords) return cleaned;
  return `${words.slice(0, maxWords).join(" ").replace(/[,:;]+$/, "")}.`;
}

function proofClauseForSkill(skill, context) {
  const cleaned = cleanDisplayText(skill);
  const lowered = cleaned.toLowerCase();
  if (["agentic ai", "langchain", "langgraph", "autogen"].includes(lowered)) {
    return `${cleaned} proof such as tool-calling flow, guardrails, task completion checks, and failure-case handling`;
  }
  if (["generative ai", "prompt engineering", "rag", "vector db"].includes(lowered)) {
    return `${cleaned} proof such as prompt tests, retrieval grounding, citations, evaluation notes, and hallucination checks`;
  }
  if (/(machine learning|scikit|tensorflow|pytorch|nlp|model)/i.test(cleaned)) {
    return `${cleaned} proof such as dataset size, feature choices, baseline metric, validation result, and error analysis`;
  }
  if (/(aws|azure|gcp|docker|kubernetes|ci\/cd|jenkins|github actions)/i.test(cleaned)) {
    return `${cleaned} proof such as deployment steps, environment setup, monitoring, rollback notes, and release validation`;
  }
  if (/(sql|power bi|tableau|etl|dashboard|analytics|pandas|numpy)/i.test(cleaned)) {
    return `${cleaned} proof such as data source, KPI definition, cleaning rules, dashboard insight, and before/after result`;
  }
  if (/(react|javascript|typescript|api|fastapi|node|django)/i.test(cleaned)) {
    return `${cleaned} proof such as user flow, API contract, validation state, tests, and performance or reliability result`;
  }
  if (context === "product") return `${cleaned} proof such as stakeholder input, acceptance criteria, prioritization decision, and release impact`;
  if (context === "security") return `${cleaned} proof such as finding evidence, severity, remediation action, and control validation`;
  return `${cleaned} proof with tools used, decision made, validation evidence, and measurable result`;
}

function outcomePhraseForContext(context) {
  if (context === "ai") return "model quality, grounded output, evaluation discipline, or automation impact";
  if (context === "data") return "decision quality, reporting accuracy, data trust, or business visibility";
  if (context === "frontend") return "user experience, reliability, accessibility, or interface performance";
  if (context === "backend") return "API reliability, maintainability, data consistency, or service performance";
  if (context === "cloud") return "deployment reliability, operational readiness, cost awareness, or release safety";
  if (context === "security") return "risk reduction, incident clarity, audit readiness, or control strength";
  if (context === "product") return "delivery clarity, stakeholder alignment, prioritization, or launch readiness";
  return "clearer scope, stronger credibility, and measurable business impact";
}

function buildRagCoachRewrite(skill, result, oldLine, section, resume, context, role, evidenceAnchor) {
  if (oldLine?.synthetic) return "";
  const patterns = (result?.market_context ?? []).flatMap((item) => parseRewritePatterns(item?.text || ""));
  if (!patterns.length) return "";
  const queryTerms = tokenSet([
    skill,
    role,
    context,
    section,
    result?.job_title,
    result?.detected_role_family,
    resume?.basics?.headline,
    resume?.basics?.summary,
    oldLine?.text,
  ].join(" "));
  const oldText = cleanDisplayText(oldLine?.text || "");
  const synthetic = Boolean(oldLine?.synthetic);
  const scored = patterns
    .map((pattern, index) => ({ pattern, score: scoreRewritePattern(pattern, skill, section, context, queryTerms, synthetic), index }))
    .filter((item) => item.score >= 8)
    .sort((a, b) => b.score - a.score || a.index - b.index);
  const selected = scored[0]?.pattern;
  if (!selected?.template) return "";
  return fillRewriteTemplate(selected.template, {
    skill,
    role,
    anchor: evidenceAnchor,
    oldLine: oldText,
    section,
    project: cleanDisplayText(resume?.projects?.[0]?.name || "portfolio project"),
  });
}

function parseRewritePatterns(text) {
  const lines = String(text || "").split(/(?=RewritePattern:)/g);
  return lines
    .filter((line) => line.trim().startsWith("RewritePattern:"))
    .map((line) => {
      const parts = {};
      const cleaned = line.replace(/^RewritePattern:\s*/i, "");
      cleaned.split("|").forEach((part) => {
        const [rawKey, ...valueParts] = part.split("=");
        const key = cleanDisplayText(rawKey).toLowerCase();
        const value = valueParts.join("=").trim();
        if (key) parts[key] = value;
      });
      return {
        domain: cleanDisplayText(parts.domain),
        roles: parseCommaLikeList(parts.roles),
        skills: parseCommaLikeList(parts.skills),
        place: cleanDisplayText(parts.place),
        useWhen: cleanDisplayText(parts.usewhen),
        template: cleanDisplayText(parts.template),
      };
    })
    .filter((pattern) => pattern.template);
}

function scoreRewritePattern(pattern, skill, section, context, queryTerms, synthetic) {
  const patternText = cleanDisplayText([
    pattern.domain,
    pattern.roles.join(" "),
    pattern.skills.join(" "),
    pattern.place,
    pattern.useWhen,
  ].join(" ")).toLowerCase();
  const patternTerms = tokenSet(patternText);
  let score = 0;
  queryTerms.forEach((term) => {
    if (patternTerms.has(term)) score += 1;
  });
  const normalizedSkill = cleanDisplayText(skill).toLowerCase();
  if (normalizedSkill && patternText.includes(normalizedSkill)) score += 8;
  if (context && patternText.includes(context)) score += 3;
  if (pattern.place && pattern.place.toLowerCase() === section.toLowerCase()) score += 4;
  if (synthetic && pattern.place.toLowerCase() === "projects") score += 2;
  return score;
}

function fillRewriteTemplate(template, values) {
  const fallbackAnchor = values.anchor || values.project || values.role;
  return cleanDisplayText(template
    .replaceAll("{skill}", values.skill || "the target skill")
    .replaceAll("{role}", values.role || "the target role")
    .replaceAll("{anchor}", fallbackAnchor)
    .replaceAll("{old_line}", values.oldLine || fallbackAnchor)
    .replaceAll("{section}", values.section || "Projects")
    .replaceAll("{project}", values.project || fallbackAnchor));
}

function buildNewEvidenceBullet(skill, result, resume, context, section, index = 0, targetPlacement = null) {
  const role = sanitizeRoleLabel(result?.job_title);
  const lowered = cleanDisplayText(skill).toLowerCase();
  const proof = proofPlanForMissingSkill(skill, result, resume, context, index, targetPlacement);
  const projectPrefix = section === "Projects" ? "Build proof first: " : "Only add after real proof: ";

  if (targetPlacement?.name) {
    return limitResumeBulletWords(`Suggested bullet: ${proof.action}`, 28);
  }

  if (["aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "github actions"].includes(lowered)) {
    return limitResumeBulletWords(`${projectPrefix}${proof.action}; document setup, validation, rollback notes, and one release log.`, 26);
  }
  if (["python", "machine learning", "scikit-learn", "tensorflow", "pytorch", "nlp"].includes(lowered)) {
    return limitResumeBulletWords(`${projectPrefix}${proof.action}; show dataset, baseline metric, error analysis, and README result.`, 26);
  }
  if (["langchain", "langgraph", "llamaindex", "autogen", "agentic ai", "rag", "vector db"].includes(lowered)) {
    return limitResumeBulletWords(`${projectPrefix}${proof.action}; add tool-calling or retrieval proof, prompt tests, failure cases, and citations.`, 26);
  }
  if (context === "data") {
    return limitResumeBulletWords(`${projectPrefix}${proof.action}; define dataset, KPI logic, cleaning rules, and final insight.`, 26);
  }
  if (context === "frontend" || context === "backend") {
    return limitResumeBulletWords(`${projectPrefix}${proof.action}; cover flow, API/component design, validation, tests, and demo notes.`, 26);
  }
  return limitResumeBulletWords(`${projectPrefix}${proof.action}; document problem, implementation, validation, and measurable outcome for ${role}.`, 26);
}

function proofPlanForMissingSkill(skill, result, resume, context, index = 0, targetPlacement = null) {
  const role = sanitizeRoleLabel(result?.job_title);
  if (targetPlacement?.name) {
    return { action: buildTargetedAddBullet(skill, context, targetPlacement, role) };
  }
  const directTemplate = projectTemplateForContext(context, role, skill, role, [skill]);
  if (context === "cloud") {
    return { action: `Create "${directTemplate.projectName}" using ${directTemplate.stack}` };
  }
  const catalog = buildRagProjectIdeas(result, resume, [skill], context, role);
  const selected = catalog[index % Math.max(1, catalog.length)] || projectTemplateForContext(context, role, skill, role, [skill]);
  const projectName = cleanDisplayText(selected?.projectName || selected?.title || `${role} proof project`);
  const stack = cleanDisplayText(selected?.stack || skill);
  const lead = [
    `Create "${projectName}" using ${stack}`,
    `Build a small "${projectName}" case study with ${skill}`,
    `Document a hands-on "${projectName}" proof using ${skill}`,
    `Finish one realistic "${projectName}" workflow that proves ${skill}`,
  ][index % 4];
  return { action: lead };
}

function buildTargetedAddBullet(skill, context, targetPlacement, role) {
  const skillName = cleanDisplayText(skill);
  const targetName = cleanDisplayText(targetPlacement.name || targetPlacement.label || role);
  const tech = cleanDisplayText(targetPlacement.tech);
  const stackSuffix = tech && !tech.toLowerCase().includes(skillName.toLowerCase()) ? ` alongside ${tech.split(",").slice(0, 3).map(cleanDisplayText).filter(Boolean).join(", ")}` : "";
  const lowered = skillName.toLowerCase();

  if (/(aws|azure|gcp|docker|kubernetes|ci\/cd|jenkins|github actions)/i.test(skillName)) {
    return `Added ${skillName} deployment workflow for ${targetName}${stackSuffix}, documenting setup, validation, rollback notes, and release evidence.`;
  }
  if (/(agentic ai|langchain|langgraph|autogen)/i.test(skillName)) {
    return `Enhanced ${targetName} with ${skillName} tool-calling checks, failure handling, and evaluation notes to improve grounded automation.`;
  }
  if (/(generative ai|prompt engineering|rag|vector db|llm)/i.test(skillName)) {
    return `Enhanced ${targetName} with ${skillName} grounding, prompt tests, citations, and evaluation notes to improve answer reliability.`;
  }
  if (/(machine learning|scikit|tensorflow|pytorch|nlp|model)/i.test(skillName)) {
    return `Improved ${targetName} with ${skillName} validation metrics, error analysis, and README results to strengthen model credibility.`;
  }
  if (/(sql|power bi|tableau|etl|dashboard|analytics|pandas|numpy)/i.test(skillName)) {
    return `Enhanced ${targetName} with ${skillName} data checks, KPI logic, and outcome notes to improve reporting accuracy.`;
  }
  if (/(react|javascript|typescript|api|fastapi|node|django)/i.test(skillName)) {
    return `Improved ${targetName} with ${skillName} validation, tests, and error handling to strengthen user flow reliability.`;
  }
  if (context === "product" || /(stakeholder|requirement|roadmap|scrum|jira|priorit)/i.test(lowered)) {
    return `Added ${skillName} evidence to ${targetName}, documenting stakeholders, priorities, decisions, and outcome for clearer delivery ownership.`;
  }
  if (context === "security") {
    return `Added ${skillName} evidence to ${targetName}, documenting risk, remediation, validation, and control impact.`;
  }
  return `Added ${skillName} evidence to ${targetName}, documenting tools, validation, and measurable outcome for ${role}.`;
}

function ensureUniqueCoachSuggestion(text, skill, result, resume, context, section, usedFingerprints, index = 0, targetPlacement = null) {
  const cleaned = cleanDisplayText(text);
  const fingerprint = cleaned
    .toLowerCase()
    .replaceAll(cleanDisplayText(skill).toLowerCase(), "{skill}")
    .replace(/\b(agentic ai|generative ai|prompt engineering|machine learning|react|fastapi|docker|aws|sql)\b/g, "{skill}")
    .replace(/"[^"]+"/g, "{project}")
    .replace(/\s+/g, " ")
    .slice(0, 180);
  if (!usedFingerprints.has(fingerprint)) {
    usedFingerprints.add(fingerprint);
    return cleaned;
  }
  const fallback = buildNewEvidenceBullet(skill, result, resume, context, section, index + usedFingerprints.size + 1, targetPlacement);
  usedFingerprints.add(`${fingerprint}:${skill.toLowerCase()}`);
  return fallback;
}

function inferEvidenceAnchor(result, resume) {
  const projectName = cleanDisplayText(resume?.projects?.[0]?.name);
  if (projectName && !/uploaded pdf projects?/i.test(projectName)) return projectName;
  const role = cleanDisplayText(resume?.experience?.[0]?.role);
  const company = cleanDisplayText(resume?.experience?.[0]?.company);
  if (role && company && !/uploaded pdf/i.test(company)) return `${role} work at ${company}`;
  if (role) return role;
  return sanitizeRoleLabel(result?.job_title);
}

function buildDataSkillBullet(skill, lowered) {
  if (lowered === "sql") {
    return "Optimized SQL queries for reporting datasets, improving extraction speed and reducing manual reconciliation during analytics refreshes.";
  }
  if (lowered === "postgresql") {
    return "Designed PostgreSQL schemas and indexed queries for analytics APIs, improving data retrieval speed and reporting consistency.";
  }
  if (lowered === "pandas") {
    return "Developed Pandas transformation pipelines for CSV and SQL datasets, reducing manual cleanup and improving analysis accuracy.";
  }
  if (lowered === "numpy") {
    return "Implemented NumPy-based feature calculations for model datasets, improving preprocessing speed and numerical consistency.";
  }
  if (lowered === "bigquery") {
    return "Built BigQuery analysis workflows for large reporting tables, improving query scalability and dashboard refresh efficiency.";
  }
  if (lowered === "snowflake") {
    return "Developed Snowflake data marts for analytics reporting, improving governed access and reducing repeated manual data pulls.";
  }
  return `Optimized ${skill} data workflows for ETL and analysis, reducing manual cleanup and improving reliability of reporting outputs.`;
}

function sanitizeRoleLabel(jobTitle) {
  const role = cleanDisplayText(jobTitle || "target role");
  if (!isCleanProfessionalRoleTitle(role)) return "target role";
  return role;
}

function professionalRoleLabel(result, resume) {
  const candidates = [
    result?.job_title,
    result?.detected_role_family,
    result?.detected_resume_role_family,
    resume?.basics?.headline,
    resume?.experience?.[0]?.role,
  ].map(cleanDisplayText);
  return candidates.find(isCleanProfessionalRoleTitle) || "target role";
}

function isCleanProfessionalRoleTitle(value) {
  const text = cleanDisplayText(value);
  if (!text || text.length > 72) return false;
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length > 9) return false;
  if (/[.!?]$/.test(text)) return false;
  if (text.includes(",") && words.length > 4) return false;
  if (/\b(score|match|requirement|description|responsibilit|qualification|permanent|full time|part time|contract)\b/i.test(text)) return false;
  if (/^(designing|developing|researching|building|creating|working|partnering|managing|owning|responsible|must|should|will)\b/i.test(text)) return false;
  return /\b(engineer|developer|scientist|analyst|manager|designer|consultant|administrator|specialist|architect|tester|qa|sre|devops|product|scrum|support|sales|marketing|finance|hr|security|data|machine learning|ai|backend|frontend|full stack)\b/i.test(text);
}

function detectResumeBulletContext(skill, result, resume) {
  const skillOnly = cleanDisplayText(skill).toLowerCase();
  if (/(stakeholder|product management|roadmap|user stories|requirements|agile|scrum|jira|prioritization|release planning)/i.test(skillOnly)) return "product";
  if (/(seo|sem|campaign|content strategy|social media|email marketing|performance marketing|conversion|crm)/i.test(skillOnly)) return "marketing";
  if (/(salesforce|lead generation|account management|customer success|client relationship|negotiation|pipeline)/i.test(skillOnly)) return "sales";
  if (/(financial|accounting|reconciliation|budget|forecast|audit|tax|compliance|risk)/i.test(skillOnly)) return "finance";
  if (/(recruit|talent acquisition|hr|onboarding|employee|payroll|sourcing|interview)/i.test(skillOnly)) return "hr";
  if (/(figma|wireframe|prototype|user research|usability|design system|photoshop|illustrator)/i.test(skillOnly)) return "design";
  if (/(tensorflow|pytorch|keras|scikit|sklearn|langchain|langgraph|llamaindex|autogen|agentic|generative|vector|rag|model|nlp|machine learning|ai)/i.test(skillOnly)) return "ai";
  if (/(sql|pandas|numpy|dashboard|etl|analytics|tableau|power bi|data)/i.test(skillOnly)) return "data";
  if (/(react|javascript|typescript|html|css|frontend|ui engineer|web developer)/i.test(skillOnly)) return "frontend";
  if (/(aws|azure|gcp|docker|kubernetes|ci\/cd|deployment|cloud)/i.test(skillOnly)) return "cloud";

  const combined = cleanDisplayText([
    skill,
    result?.job_title,
    result?.detected_role_family,
    result?.detected_resume_role_family,
    resume?.basics?.headline,
    resume?.basics?.summary,
    ...(resume?.skills ?? []).map((group) => `${group.name} ${(group.items ?? []).join(" ")}`),
    ...(result?.missing_required_skills ?? []).map((item) => item.keyword),
    ...(result?.missing_keywords ?? []).map((item) => item.keyword),
  ].join(" ")).toLowerCase();

  if (/(tensorflow|pytorch|keras|scikit|sklearn|langchain|langgraph|llamaindex|autogen|agentic|generative|vector|rag|model|nlp|machine learning|ai)/i.test(combined)) return "ai";
  if (/(react|javascript|typescript|html|css|frontend|ui engineer|web developer)/i.test(combined)) return "frontend";
  if (/(aws|azure|gcp|docker|kubernetes|ci\/cd|deployment|cloud)/i.test(combined)) return "cloud";
  if (/(sql|pandas|numpy|dashboard|etl|analytics|tableau|power bi|data)/i.test(combined)) return "data";
  if (/(product manager|product owner|program manager|project manager|scrum|agile|roadmap|jira|stakeholder|requirements|delivery manager)/i.test(combined)) return "product";
  if (/(marketing|seo|sem|campaign|content|social media|growth|conversion|brand|email marketing)/i.test(combined)) return "marketing";
  if (/(sales|account executive|business development|lead generation|crm|salesforce|pipeline|customer success|client relationship)/i.test(combined)) return "sales";
  if (/(finance|accounting|accountant|audit|tax|reconciliation|budget|forecast|compliance|risk)/i.test(combined)) return "finance";
  if (/(human resources|hr|recruit|talent acquisition|onboarding|employee|payroll|sourcing|interview)/i.test(combined)) return "hr";
  if (/(ux|ui designer|product designer|graphic designer|figma|prototype|wireframe|user research|usability|adobe)/i.test(combined)) return "design";
  if (/(security|cyber|soc|vulnerability|incident|risk assessment|iam|compliance control)/i.test(combined)) return "security";
  if (/(android|ios|mobile|flutter|react native|kotlin|swift)/i.test(combined)) return "mobile";
  return "backend";
}

function estimateSkillImpact(skill, result, index) {
  const required = (result.missing_required_skills ?? []).some((item) => cleanDisplayText(item.keyword).toLowerCase() === cleanDisplayText(skill).toLowerCase());
  const weak = (result.weak_evidence_skills ?? []).some((item) => cleanDisplayText(item.keyword).toLowerCase() === cleanDisplayText(skill).toLowerCase());
  if (required) return Math.max(4, 8 - index);
  if (weak) return 3;
  return Math.max(2, 5 - Math.floor(index / 2));
}

function SimpleListItem({ icon, title, text }) {
  return (
    <div className="ats-simple-list-item">
      <span className={`ats-simple-icon ${icon}`} aria-hidden="true">
        {simpleIconText(icon)}
      </span>
      <div>
        <strong>{title}</strong>
        {text ? <p>{text}</p> : null}
      </div>
    </div>
  );
}

function SkillColumn({ title, icon, items, emptyText }) {
  return (
    <div className={`ats-simple-skill-column tone-${icon}`}>
      <div className="ats-simple-skill-head">
        <span className={`ats-simple-icon ${icon}`} aria-hidden="true">
          {simpleIconText(icon)}
        </span>
        <strong>{title}</strong>
      </div>
      <div className="ats-simple-chip-list">
        {items.length ? items.map((item) => <span key={`${title}-${item}`}>{item}</span>) : <p>{emptyText}</p>}
      </div>
    </div>
  );
}

function buildSimpleFixes(result, optimization) {
  const fixes = [];
  const addFix = (problem, fix, icon = "warning", rank = 3, dedupeKey = "") => {
    const cleanedProblem = shortText(problem, 76);
    const cleanedFix = cleanDisplayText(fix);
    if (!cleanedProblem || !cleanedFix) return;
    const normalizedKey = cleanDisplayText(dedupeKey || cleanedProblem).toLowerCase();
    if (fixes.some((item) => item.key === normalizedKey || item.problem.toLowerCase() === cleanedProblem.toLowerCase())) return;
    fixes.push({ problem: cleanedProblem, fix: cleanedFix, icon, rank, key: normalizedKey });
  };

  const classifySkillKeyword = (keyword) => {
    const normalized = cleanDisplayText(keyword).toLowerCase();
    if (["tensorflow", "pytorch", "keras", "scikit-learn", "sklearn"].includes(normalized)) return "ml-framework";
    if (["langchain", "langgraph", "rag", "vector db", "vectordb", "pinecone", "chromadb", "faiss"].includes(normalized)) return "llm-stack";
    if (["azure", "aws", "gcp"].includes(normalized)) return "cloud";
    if (["docker", "kubernetes", "ci/cd", "jenkins", "github actions", "devops"].includes(normalized)) return "platform";
    if (["a/b testing", "ab testing", "experimentation"].includes(normalized)) return "experimentation";
    if (["sql", "power bi", "tableau", "excel", "pandas", "numpy"].includes(normalized)) return "data";
    if (["react", "javascript", "typescript", "node.js", "node", "rest apis", "api", "microservices", "fastapi", "django"].includes(normalized)) return "engineering";
    if (["product management", "roadmap", "user stories", "requirements", "stakeholder management", "agile", "scrum", "jira", "prioritization"].includes(normalized)) return "product";
    if (["seo", "sem", "google analytics", "campaign management", "content strategy", "social media", "email marketing", "performance marketing", "conversion optimization", "crm"].includes(normalized)) return "marketing";
    if (["salesforce", "lead generation", "account management", "customer success", "client relationship", "negotiation", "pipeline management"].includes(normalized)) return "sales";
    if (["financial analysis", "accounting", "reconciliation", "budgeting", "forecasting", "audit", "taxation", "compliance", "risk analysis"].includes(normalized)) return "finance";
    if (["recruitment", "talent acquisition", "hr operations", "onboarding", "employee engagement", "payroll", "performance management", "sourcing", "interviewing"].includes(normalized)) return "hr";
    if (["figma", "wireframing", "prototyping", "user research", "usability testing", "design systems", "photoshop", "illustrator"].includes(normalized)) return "design";
    return "general";
  };

  const buildSkillFixCopy = (keyword, required, jobTitle) => {
    if (!keyword) return "";
    const roleLabel = cleanDisplayText(jobTitle || "the target role");
    const skillType = classifySkillKeyword(keyword);

    if (skillType === "cloud") {
      return required
        ? `Show where you used ${keyword} in delivery work for ${roleLabel}. A stronger fix is one bullet that names the cloud task, the system you supported, and the result.`
        : `If ${keyword} is real experience, weave it into one project or work bullet instead of listing it by itself. Mention what you deployed, migrated, or automated.`;
    }

    if (skillType === "platform") {
      return required
        ? `Recruiters will look for hands-on evidence here. Add ${keyword} only if you used it, then point to one delivery bullet showing pipeline, deployment, or release ownership.`
        : `Strengthen this by tying ${keyword} to shipping work. One concise bullet about automation, deployment, or environment setup will read better than a skills-only mention.`;
    }

    if (skillType === "ml-framework") {
      return required
        ? `For ${keyword}, the best improvement is proof of application. Add one bullet that says what model or workflow you built, why ${keyword} was used, and what outcome it improved.`
        : `If ${keyword} is part of your actual toolkit, mention it in a project with a concrete ML task such as training, tuning, evaluation, or inference.`;
    }

    if (skillType === "llm-stack") {
      return required
        ? `This is more convincing when it appears in context. Show ${keyword} in one bullet tied to an agent, retrieval, orchestration, or LLM workflow you actually built.`
        : `Only add ${keyword} if you used it in a real build. The strongest version is a bullet that explains the use case, architecture piece, and practical outcome.`;
    }

    if (skillType === "experimentation") {
      return `Rather than just naming ${keyword}, show decision-making evidence. Add one bullet about the hypothesis, metric, and change you validated through experimentation.`;
    }

    if (skillType === "data") {
      return `Make ${keyword} visible through output, not only through a keyword mention. Add a bullet that ties it to analysis, dashboarding, reporting, or measurable insight.`;
    }

    if (skillType === "engineering") {
      return `A clean fix is to connect ${keyword} to shipped work. Add one bullet that shows what you built with it, where it fit in the stack, and the result it delivered.`;
    }
    if (skillType === "product") {
      return `Make ${keyword} visible through product or delivery evidence. Add one bullet showing the decision, stakeholder group, prioritization reason, and outcome.`;
    }
    if (skillType === "marketing") {
      return `Show ${keyword} through campaign evidence. Add one bullet with channel, audience, metric, and what improved.`;
    }
    if (skillType === "sales") {
      return `Tie ${keyword} to pipeline or client outcomes. Add one bullet showing account context, action taken, and measurable progress.`;
    }
    if (skillType === "finance") {
      return `Support ${keyword} with accuracy or control evidence. Add one bullet showing the report, reconciliation, audit, or forecast impact.`;
    }
    if (skillType === "hr") {
      return `Make ${keyword} concrete through people-process evidence. Add one bullet showing hiring, onboarding, employee, or coordination impact.`;
    }
    if (skillType === "design") {
      return `Show ${keyword} as design proof. Add one bullet naming the research, prototype, user flow, or system component and the review outcome.`;
    }

    return required
      ? `If you genuinely have ${keyword}, add it only with proof. One focused bullet showing where you used it and what changed will make this gap less risky.`
      : `If ${keyword} is relevant experience, support it with one concrete example instead of a standalone keyword so the match feels credible.`;
  };

  const skillFixCopy = (keyword, required) => {
    return buildSkillFixCopy(keyword, required, result.job_title);
  };

  const criticalGapFixCopy = (item) => {
    const title = cleanDisplayText(item?.title).toLowerCase();
    if (title.includes("experience level below")) {
      return "Counter this by foregrounding depth over duration. Lead with your strongest production work, ownership, and measurable outcomes so the reader sees seniority in evidence, not just in years.";
    }
    if (title.includes("core role alignment")) {
      return "Tighten alignment in the headline, summary, and first few bullets. The target role should be obvious within a quick scan, and your top evidence should reinforce that direction.";
    }
    return item?.suggested_edit || item?.impact || item?.details || "";
  };

  (result.missing_required_skills ?? []).forEach((item) => {
    const keyword = cleanDisplayText(item.keyword);
    addFix(`Missing required skill: ${keyword}`, skillFixCopy(keyword, true), "cross", 0, `missing-skill:${keyword.toLowerCase()}`);
  });
  (result.missing_keywords ?? [])
    .filter((item) => ["high", "medium"].includes(String(item.importance || "").toLowerCase()))
    .forEach((item) => {
      const keyword = cleanDisplayText(item.keyword);
      const highPriority = item.importance === "high";
      addFix(`Missing skill: ${keyword}`, skillFixCopy(keyword, false), highPriority ? "cross" : "warning", highPriority ? 1 : 2, `missing-skill:${keyword.toLowerCase()}`);
    });
  (result.critical_gaps ?? []).forEach((item) => {
    addFix(item.title, criticalGapFixCopy(item), "cross", 1, `critical-gap:${cleanDisplayText(item.title).toLowerCase()}`);
  });

  const groupedSuggestions = result.suggestions ?? {};
  ["high_impact", "medium_impact", "low_impact"].forEach((key) => {
    (groupedSuggestions[key] ?? []).forEach((item) => {
      addFix(item.title, item.suggested_edit || item.details, key === "high_impact" ? "warning" : "check", key === "high_impact" ? 2 : 4, `suggestion:${cleanDisplayText(item.title).toLowerCase()}`);
    });
  });
  (result.improvement_suggestions ?? []).forEach((item) => {
    addFix(item.title, item.suggested_edit || item.details, "warning", 3, `improvement:${cleanDisplayText(item.title).toLowerCase()}`);
  });
  (optimization?.remaining_gaps ?? []).forEach((item) => {
    const keyword = cleanDisplayText(item);
    addFix(`Add proof for ${keyword}`, `Add one specific bullet that shows how you used ${keyword} and what outcome it produced.`, "warning", 2, `remaining-gap:${keyword.toLowerCase()}`);
  });

  return fixes
    .sort((left, right) => left.rank - right.rank)
    .slice(0, 5)
    .map(({ key, ...item }) => item);
}

function buildSimpleCriticalIssues(result) {
  const issues = [];
  const addIssue = (title, text, icon = "cross") => {
    const cleanedTitle = cleanDisplayText(title);
    if (!cleanedTitle || issues.some((item) => item.title.toLowerCase() === cleanedTitle.toLowerCase())) return;
    issues.push({ title: cleanedTitle, text: cleanDisplayText(text), icon });
  };

  (result.missing_required_skills ?? []).forEach((item) => {
    addIssue(`Missing required skill: ${item.keyword}`, item.details || "Add this only if you can support it with real experience.");
  });
  (result.missing_keywords ?? [])
    .filter((item) => item.importance === "high")
    .forEach((item) => addIssue(`Missing skill: ${item.keyword}`, item.details));
  (result.critical_gaps ?? []).forEach((item) => {
    addIssue(item.title, item.impact || item.details);
  });
  (result.formatting_issues ?? [])
    .filter((item) => ["critical", "high"].includes(String(item.severity || "").toLowerCase()))
    .forEach((item) => addIssue(item.issue, item.recommendation || item.details, "warning"));

  return issues.slice(0, 5);
}

function buildSimpleSuggestions(result, optimization) {
  const suggestions = [];
  const addSuggestion = (title, text) => {
    const cleanedTitle = cleanDisplayText(title);
    if (!cleanedTitle || suggestions.some((item) => item.title.toLowerCase() === cleanedTitle.toLowerCase())) return;
    suggestions.push({ title: cleanedTitle, text: cleanDisplayText(text) });
  };
  const groupedSuggestions = result.suggestions ?? {};

  ["high_impact", "medium_impact", "low_impact"].forEach((key) => {
    (groupedSuggestions[key] ?? []).forEach((item) => {
      addSuggestion(item.title, item.suggested_edit || item.details);
    });
  });
  (result.improvement_suggestions ?? []).forEach((item) => {
    addSuggestion(item.title, item.suggested_edit || item.details);
  });
  (optimization?.remaining_gaps ?? []).forEach((item) => {
    addSuggestion(`Add proof for ${item}`, "Use a real project or work bullet that shows where you used it.");
  });

  return suggestions.slice(0, 5);
}

function buildSimpleSkills(result) {
  const comparisonItems = (result.comparison_view ?? []).filter((item) => isSkillLikeTerm(item.requirement));
  const missing = uniqueDisplayItems([
    ...comparisonItems.filter((item) => item.status === "missing").map((item) => item.requirement),
    ...(result.missing_required_skills ?? []).map((item) => item.keyword),
    ...(result.missing_keywords ?? []).map((item) => item.keyword),
  ]).filter(isSkillLikeTerm);
  const strong = uniqueDisplayItems([
    ...comparisonItems.filter((item) => item.status === "matched").map((item) => item.requirement),
    ...(result.matched_keywords ?? []).map((item) => item.keyword),
  ])
    .filter(isSkillLikeTerm)
    .filter((item) => !includesDisplayItem(missing, item));
  const needsImprovement = uniqueDisplayItems([
    ...comparisonItems.filter((item) => item.status === "partial").map((item) => item.requirement),
    ...(result.weak_evidence_skills ?? []).map((item) => item.keyword),
  ])
    .filter(isSkillLikeTerm)
    .filter((item) => !includesDisplayItem(missing, item) && !includesDisplayItem(strong, item));

  return {
    strong: strong.slice(0, 10),
    needsImprovement: needsImprovement.slice(0, 10),
    missing: missing.slice(0, 10),
  };
}

function buildSimpleRoleMatches(result) {
  const comparisonMatches = (result.comparison_view ?? []).map((item) => ({
    requirement: item.requirement,
    evidence: item.evidence?.[0] || "",
    score: item.status === "matched" ? 2 : item.status === "partial" ? 1 : 0,
  }));
  const semanticMatches = (result.semantic_requirement_matches ?? []).map((item) => ({
    requirement: item.job_requirement,
    evidence: item.matched_resume_bullet || "",
    score: item.match_strength === "strong" ? 2 : item.match_strength === "partial" ? 1 : 0,
  }));

  return [...semanticMatches, ...comparisonMatches]
    .filter((item) => cleanDisplayText(item.requirement))
    .sort((left, right) => right.score - left.score)
    .filter((item, index, list) => list.findIndex((candidate) => cleanDisplayText(candidate.requirement).toLowerCase() === cleanDisplayText(item.requirement).toLowerCase()) === index)
    .slice(0, 5);
}

function buildSimpleRoleFit(result, skills) {
  const comparisonRows = (result.comparison_view ?? [])
    .filter((item) => isSkillLikeTerm(item.requirement))
    .map((item) => ({
      skill: cleanDisplayText(item.requirement),
      status: statusLabel(item.status),
      tone: statusTone(item.status),
      rank: item.status === "missing" ? 0 : item.status === "partial" ? 1 : 2,
    }));
  const fallbackRows = [
    ...skills.missing.map((skill) => ({ skill, status: "Missing", tone: "missing", rank: 0 })),
    ...skills.needsImprovement.map((skill) => ({ skill, status: "Partial", tone: "partial", rank: 1 })),
    ...skills.strong.map((skill) => ({ skill, status: "Strong", tone: "strong", rank: 2 })),
  ];

  return uniqueRoleRows(comparisonRows.length ? comparisonRows : fallbackRows)
    .sort((left, right) => left.rank - right.rank)
    .slice(0, 5);
}

function normalizeScore(value) {
  const score = Number(value);
  if (!Number.isFinite(score)) return 0;
  return Math.max(0, Math.min(100, Math.round(score)));
}

function simpleAtsStatus(score) {
  if (score >= 78) return { label: "Good", tone: "good" };
  if (score >= 60) return { label: "Moderate", tone: "moderate" };
  return { label: "Weak", tone: "weak" };
}

function buildSimpleAtsSummary(result, status, fixCount, optimization) {
  if (optimization) {
    return `Auto-fix updated score from ${optimization.previous_score} to ${optimization.updated_score}.`;
  }
  if (fixCount) {
    return `${status.label} fit for ${result.job_title || "this role"}; fix ${fixCount} priority item${fixCount === 1 ? "" : "s"} first.`;
  }
  return `${status.label} fit for ${result.job_title || "this role"}; no priority fixes found.`;
}

function cleanDisplayText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function shortText(value, maxLength) {
  const text = cleanDisplayText(value);
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).trim()}...`;
}

function uniqueDisplayItems(items) {
  const seen = new Set();
  return items
    .map(cleanDisplayText)
    .filter(Boolean)
    .filter((item) => {
      const key = item.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function includesDisplayItem(items, value) {
  const key = cleanDisplayText(value).toLowerCase();
  return items.some((item) => cleanDisplayText(item).toLowerCase() === key);
}

function sameDisplayText(left, right) {
  return cleanDisplayText(left).toLowerCase() === cleanDisplayText(right).toLowerCase();
}

const GENERIC_NON_SKILL_TERMS = new Set([
  "agent",
  "agents",
  "business",
  "client",
  "clients",
  "collaboration",
  "collaborative",
  "communication",
  "company",
  "computer",
  "customer",
  "customers",
  "data-driven",
  "deliver",
  "delivery",
  "design",
  "development",
  "enterprise",
  "execution",
  "impact",
  "innovation",
  "leadership",
  "management",
  "opportunity",
  "organization",
  "ownership",
  "performance",
  "process",
  "processes",
  "product",
  "products",
  "professional",
  "project",
  "projects",
  "quality",
  "requirement",
  "requirements",
  "responsibility",
  "responsibilities",
  "role",
  "science",
  "solution",
  "solutions",
  "strategy",
  "support",
  "system",
  "systems",
  "team",
  "teams",
  "work",
  "workflow",
  "workflows",
]);

const TECH_SKILL_TOKENS = new Set([
  "ai",
  "analytics",
  "api",
  "apis",
  "aws",
  "azure",
  "backend",
  "ci/cd",
  "cloud",
  "computer",
  "css",
  "data",
  "database",
  "databases",
  "db",
  "deep",
  "devops",
  "django",
  "docker",
  "engineering",
  "etl",
  "excel",
  "fastapi",
  "figma",
  "frontend",
  "gcp",
  "generative",
  "git",
  "github",
  "html",
  "hugging",
  "javascript",
  "js",
  "kubernetes",
  "langchain",
  "llm",
  "llms",
  "machine",
  "matplotlib",
  "microservice",
  "microservices",
  "ml",
  "mongodb",
  "mysql",
  "nlp",
  "node",
  "node.js",
  "numpy",
  "pandas",
  "pipeline",
  "pipelines",
  "postgresql",
  "power",
  "powerbi",
  "prompt",
  "prompts",
  "python",
  "pytorch",
  "rag",
  "react",
  "redis",
  "rest",
  "saas",
  "scikit-learn",
  "seaborn",
  "seo",
  "sklearn",
  "sql",
  "tableau",
  "tensorflow",
  "testing",
  "typescript",
  "ux",
  "ui",
  "vector",
  "visualization",
]);

const PROFESSIONAL_SKILL_TOKENS = new Set([
  "abm",
  "account",
  "accounting",
  "adobe",
  "agile",
  "analysis",
  "audit",
  "budgeting",
  "campaign",
  "campaigns",
  "compliance",
  "content",
  "crm",
  "customer",
  "design",
  "documentation",
  "email",
  "engagement",
  "figma",
  "finance",
  "forecasting",
  "growth",
  "gathering",
  "hiring",
  "hr",
  "interviewing",
  "jira",
  "kpi",
  "lead",
  "leads",
  "marketing",
  "negotiation",
  "onboarding",
  "operations",
  "payroll",
  "pipeline",
  "prioritization",
  "prototyping",
  "quickbooks",
  "reconciliation",
  "recruitment",
  "reporting",
  "research",
  "risk",
  "roadmap",
  "sales",
  "salesforce",
  "scrum",
  "seo",
  "sourcing",
  "stakeholder",
  "stories",
  "strategy",
  "taxation",
  "testing",
  "tally",
  "usability",
  "wireframing",
]);

function hasTechnicalSkillSignal(text) {
  const normalized = cleanDisplayText(text).toLowerCase();
  if (!normalized) return false;
  if (TECH_SKILL_TOKENS.has(normalized)) return true;
  if (PROFESSIONAL_SKILL_TOKENS.has(normalized)) return true;
  if (/[+/#.]/.test(normalized) || /\d/.test(normalized)) return true;

  const tokens = normalized
    .split(/[\s(),-]+/)
    .map((token) => token.trim())
    .filter(Boolean);

  return tokens.some((token) => TECH_SKILL_TOKENS.has(token) || PROFESSIONAL_SKILL_TOKENS.has(token));
}

function isProfessionalSkillTerm(value) {
  const normalized = cleanDisplayText(value).toLowerCase();
  if (!normalized) return false;
  if (PROFESSIONAL_SKILL_TOKENS.has(normalized)) return true;
  const tokens = normalized
    .split(/[\s(),/-]+/)
    .map((token) => token.trim())
    .filter(Boolean);
  return tokens.some((token) => PROFESSIONAL_SKILL_TOKENS.has(token));
}

function isSkillLikeTerm(value) {
  const text = cleanDisplayText(value);
  if (!text || text.length > 48 || /[.!?]$/.test(text)) return false;
  const normalized = text.toLowerCase();
  const words = text.split(/\s+/);
  if (words.length > 5) return false;
  if (GENERIC_NON_SKILL_TERMS.has(normalized)) return false;
  if (words.length > 2 && /\b(experience|responsibilities|qualifications|required|build|built|develop|design|create|partner|manage|own)\b/i.test(text)) return false;
  return hasTechnicalSkillSignal(text);
}

function simpleIconText(icon) {
  if (icon === "check") return "OK";
  if (icon === "cross") return "X";
  return "!";
}

function statusLabel(status) {
  if (status === "matched") return "Strong";
  if (status === "partial") return "Partial";
  return "Missing";
}

function statusTone(status) {
  if (status === "matched") return "strong";
  if (status === "partial") return "partial";
  return "missing";
}

function uniqueRoleRows(rows) {
  const seen = new Set();
  return rows.filter((row) => {
    const key = cleanDisplayText(row.skill).toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function ATSResultPanel({ result, optimization }) {
  const overallScore = result.overall_ats_score ?? result.overall_score;
  const jobMatchScore = result.job_match_score ?? result.overall_score;
  const readabilityScore = result.ats_readability_score ?? result.section_scores?.formatting_parseability ?? 0;
  const confidenceScore = result.confidence_score ?? result.parsing_confidence ?? 0;
  const missingKeywords = result.missing_keywords ?? [];
  const matchedKeywords = result.matched_keywords ?? [];
  const strongEvidenceSkills = result.strong_evidence_skills ?? [];
  const weakEvidenceSkills = result.weak_evidence_skills ?? [];
  const semanticMatches = result.semantic_requirement_matches ?? [];
  const matchedResponsibilities = result.matched_responsibilities ?? [];
  const missingResponsibilities = result.missing_responsibilities ?? [];
  const scoreCapsApplied = result.score_caps_applied ?? [];
  const confidenceFactors = result.confidence_factors ?? {};
  const detectedRoleLabel = result.detected_role_family ? result.detected_role_family.replaceAll("_", " ") : "";
  const suggestionsByPriority = result.suggestions ?? {
    high_impact: (result.improvement_suggestions ?? []).filter((item) => item.priority === "high"),
    medium_impact: (result.improvement_suggestions ?? []).filter((item) => item.priority === "medium"),
    low_impact: (result.improvement_suggestions ?? []).filter((item) => item.priority === "low"),
  };
  const groupedSuggestionEntries = [
    ["high_impact", "High Impact"],
    ["medium_impact", "Medium Impact"],
    ["low_impact", "Low Impact"],
  ];
  const groupedMissingKeywords = {
    high: missingKeywords.filter((item) => item.importance === "high"),
    medium: missingKeywords.filter((item) => item.importance === "medium"),
    low: missingKeywords.filter((item) => item.importance === "low"),
  };
  return (
    <div className="ats-result">
      <div className="ats-score-hero" style={{ "--score": `${overallScore}%` }}>
        <div className="ats-score-ring">
          <div className="ats-score-ring-inner">
            <strong>{overallScore}</strong>
            <span>/100</span>
          </div>
        </div>
        <div className="ats-score-copy">
          <div className="ats-score-topline">
            <h3>Overall ATS Score</h3>
            <span className={`ats-confidence-pill tone-${confidenceTone(result.confidence_label)}`}>{result.confidence_label}</span>
          </div>
          <p className="ats-job-title">{result.job_title}</p>
          <p>{result.summary}</p>
          <div className="ats-fix-metrics">
            <div className="ats-fix-metric-card">
              <span>Job Match</span>
              <strong>{jobMatchScore}/100</strong>
            </div>
            <div className="ats-fix-metric-card">
              <span>Readability</span>
              <strong>{readabilityScore}/100</strong>
            </div>
            <div className="ats-fix-metric-card">
              <span>Reliability</span>
              <strong>{Math.round(confidenceScore * 100)}%</strong>
            </div>
          </div>
          <div className="ats-meta-row">
            <span className="ats-meta-pill">Parsing confidence {Math.round(result.parsing_confidence * 100)}%</span>
            <span className="ats-meta-pill">Source {formatSourceLabel(result.job_source)}</span>
            {detectedRoleLabel ? <span className="ats-meta-pill">Role {detectedRoleLabel}</span> : null}
            {result.weight_profile_name ? <span className="ats-meta-pill">Weights {result.weight_profile_name.replaceAll("_", " ")}</span> : null}
            {result.match_quality_label ? <span className="ats-meta-pill">{result.match_quality_label}</span> : null}
            {result.score_cap_applied ? <span className="ats-meta-pill is-warning">Score cap applied</span> : null}
          </div>
          {result.source_note ? <p className="ats-source-note">{result.source_note}</p> : null}
          {result.score_cap_reason ? <p className="ats-source-note">{result.score_cap_reason}</p> : null}
        </div>
      </div>

      {optimization ? (
        <div className="ats-block ats-fix-summary">
          <div className="ats-block-head">
            <h4>Auto-Fix Result</h4>
            <span className={`ats-confidence-pill tone-${optimization.score_delta > 0 ? "strong" : "moderate"}`}>
              {optimization.score_delta > 0 ? "Score improved" : "Best safe version applied"}
            </span>
          </div>
          <div className="ats-fix-metrics">
            <div className="ats-fix-metric-card">
              <span>Before</span>
              <strong>{optimization.previous_score}/100</strong>
            </div>
            <div className="ats-fix-metric-card">
              <span>After</span>
              <strong>{optimization.updated_score}/100</strong>
            </div>
            <div className="ats-fix-metric-card">
              <span>Delta</span>
              <strong>{optimization.score_delta >= 0 ? `+${optimization.score_delta}` : optimization.score_delta}</strong>
            </div>
            <div className="ats-fix-metric-card">
              <span>Mode</span>
              <strong>Max from resume</strong>
            </div>
          </div>
          <p className="ats-source-note">{optimization.safety_note}</p>
          {optimization.applied_changes.length ? (
            <div className="ats-list compact">
              {optimization.applied_changes.map((item, index) => (
                <p className="ats-list-item" key={`optimization-change-${index}`}>
                  <span className="ats-list-bullet">{"\u2022"}</span>
                  <span>{item}</span>
                </p>
              ))}
            </div>
          ) : null}
          <div className="ats-fix-preview">
            <strong>Live resume updated automatically</strong>
            <p className="ats-fix-preview-title">{optimization.optimized_resume.basics.headline || "No headline available"}</p>
            <p>{optimization.optimized_resume.basics.summary}</p>
          </div>
          {optimization.remaining_gaps.length ? (
            <p className="ats-fix-gap-note">Remaining high/medium gaps: {optimization.remaining_gaps.join(", ")}</p>
          ) : null}
        </div>
      ) : null}

      <div className="ats-block ats-explanation-block">
        <div className="ats-block-head">
          <h4>Explanation Panel</h4>
        </div>
        <p className="ats-explanation-headline">{result.explanation_panel.headline}</p>
        <p className="ats-explanation-summary">{result.explanation_panel.summary}</p>
        <div className="ats-explanation-grid">
          <div className="ats-note-card">
            <strong>What is helping</strong>
            {result.explanation_panel.strengths.length ? (
              <div className="ats-list compact">
                {result.explanation_panel.strengths.map((item, index) => (
                  <p className="ats-list-item" key={`strength-${index}`}>
                    <span className="ats-list-bullet">{"\u2022"}</span>
                    <span>{item}</span>
                  </p>
                ))}
              </div>
            ) : (
              <p className="ats-empty-text">No major strengths surfaced yet.</p>
            )}
          </div>
          <div className="ats-note-card risk">
            <strong>What is holding the score back</strong>
            {result.explanation_panel.risks.length ? (
              <div className="ats-list compact">
                {result.explanation_panel.risks.map((item, index) => (
                  <p className="ats-list-item" key={`risk-${index}`}>
                    <span className="ats-list-bullet">{"\u2022"}</span>
                    <span>{item}</span>
                  </p>
                ))}
              </div>
            ) : (
              <p className="ats-empty-text">No major risks were flagged.</p>
            )}
          </div>
        </div>
      </div>

      <div className="ats-breakdown-grid section-score-grid">
        {Object.entries(result.section_scores).map(([key, score]) => {
          const meta = SECTION_SCORE_META[key];
          return (
            <div className="ats-breakdown-card section-score-card" key={key}>
              <div className="ats-breakdown-head">
                <span>{meta.title}</span>
                <strong>{score}/100</strong>
              </div>
              <div className="ats-mini-progress">
                <span style={{ width: `${score}%` }} />
              </div>
              <p>{meta.caption}</p>
            </div>
          );
        })}
      </div>

      <div className="ats-double-grid">
        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Confidence Factors</h4>
            <span className="ats-subtle-label">{Math.round(confidenceScore * 100)}% reliability</span>
          </div>
          {Object.entries(confidenceFactors).length ? (
            <div className="ats-comparison-grid">
              {Object.entries(confidenceFactors).map(([key, value]) => (
                <div className="ats-comparison-card" key={`confidence-${key}`}>
                  <div className="ats-comparison-topline">
                    <strong>{key.replaceAll("_", " ")}</strong>
                    <span className="ats-meta-pill">{Math.round(value * 100)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No confidence factors returned.</p>
          )}
        </div>

        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Score Caps</h4>
            <span className="ats-subtle-label">Calibration guardrails</span>
          </div>
          {scoreCapsApplied.length ? (
            <div className="ats-warning-list">
              {scoreCapsApplied.map((item, index) => (
                <div className="ats-warning-card" key={`score-cap-${index}`}>
                  <div className="ats-warning-topline">
                    <strong>{item.cap_name?.replaceAll("_", " ") ?? "Score cap"}</strong>
                    <span className="ats-priority-pill high">Cap {item.cap}</span>
                  </div>
                  <p>{item.reason}</p>
                  {item.triggered_by ? <p className="ats-warning-fix">{item.triggered_by}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No score caps were triggered.</p>
          )}
        </div>
      </div>

      <div className="ats-double-grid">
        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Requirement Evidence</h4>
            <span className="ats-subtle-label">JD bullet to resume bullet</span>
          </div>
          {semanticMatches.length ? (
            <div className="ats-match-grid">
              {semanticMatches.slice(0, 6).map((item, index) => (
                <div className="ats-match-card" key={`semantic-${index}`}>
                  <div className="ats-match-topline">
                    <strong>{item.job_requirement}</strong>
                    <span className={`ats-status-pill ${item.match_strength === "strong" ? "matched" : item.match_strength}`}>{item.semantic_score}/100</span>
                  </div>
                  {item.matched_resume_bullet ? <p>{item.matched_resume_bullet}</p> : <p className="ats-empty-text">No supporting bullet found.</p>}
                  {item.resume_section ? <p className="ats-match-sections">{item.resume_section}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No requirement evidence returned.</p>
          )}
        </div>

        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Responsibility Alignment</h4>
            <span className="ats-subtle-label">{result.responsibility_match_score ?? 0}/100</span>
          </div>
          {matchedResponsibilities.length || missingResponsibilities.length ? (
            <div className="ats-match-grid">
              {[...matchedResponsibilities.slice(0, 3), ...missingResponsibilities.slice(0, 3)].map((item, index) => (
                <div className="ats-match-card" key={`responsibility-${index}`}>
                  <div className="ats-match-topline">
                    <strong>{item.responsibility}</strong>
                    <span className={`ats-status-pill ${item.score >= 62 ? "matched" : "missing"}`}>{item.score ?? item.best_score}/100</span>
                  </div>
                  {item.matched_resume_bullet || item.best_resume_bullet ? (
                    <p>{item.matched_resume_bullet ?? item.best_resume_bullet}</p>
                  ) : (
                    <p className="ats-empty-text">No supporting bullet found.</p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No responsibility matches returned.</p>
          )}
        </div>
      </div>

      <div className="ats-keyword-priority-grid">
        {["high", "medium", "low"].map((priority) => (
          <div className="ats-block priority-block" key={priority}>
            <div className="ats-block-head">
              <h4>{priorityLabel(priority)} Priority Gaps</h4>
              <span className={`ats-priority-pill ${priority}`}>{priorityLabel(priority)}</span>
            </div>
            {groupedMissingKeywords[priority].length ? (
              <div className="ats-gap-list">
                {groupedMissingKeywords[priority].map((item) => (
                  <div className="ats-gap-card" key={`${priority}-${item.keyword}`}>
                    <strong>{item.keyword}</strong>
                    <p>{item.details}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="ats-empty-text">No {priority} priority gaps were detected.</p>
            )}
          </div>
        ))}
      </div>

      <div className="ats-double-grid">
        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Formatting Warnings</h4>
            <span className="ats-subtle-label">ATS-safe checks</span>
          </div>
          {result.formatting_issues.length ? (
            <div className="ats-warning-list">
              {result.formatting_issues.map((item, index) => (
                <div className="ats-warning-card" key={`warning-${index}`}>
                  <div className="ats-warning-topline">
                    <strong>{item.issue}</strong>
                    <span className={`ats-priority-pill ${item.severity}`}>{priorityLabel(item.severity)}</span>
                  </div>
                  <p>{item.details}</p>
                  <p className="ats-warning-fix">{item.recommendation}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No major ATS formatting risks were flagged in this resume structure.</p>
          )}
        </div>

        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Critical Requirements Not Found</h4>
            <span className="ats-subtle-label">Potential screen-outs</span>
          </div>
          {result.critical_gaps.length ? (
            <div className="ats-warning-list">
              {result.critical_gaps.map((item, index) => (
                <div className="ats-warning-card critical" key={`critical-${index}`}>
                  <strong>{item.title}</strong>
                  <p>{item.details}</p>
                  <p className="ats-warning-fix">{item.impact}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No obvious hard-screen gaps were detected.</p>
          )}
        </div>
      </div>

      <div className="ats-block">
        <div className="ats-block-head">
          <h4>How To Improve</h4>
          <span className="ats-subtle-label">Grouped next edits</span>
        </div>
        {groupedSuggestionEntries.some(([key]) => suggestionsByPriority[key]?.length) ? (
          groupedSuggestionEntries.map(([key, label]) =>
            suggestionsByPriority[key]?.length ? (
              <div className="ats-suggestion-grid" key={key}>
                {suggestionsByPriority[key].map((item, index) => (
                  <div className="ats-suggestion-card" key={`suggestion-${key}-${index}`}>
                    <div className="ats-suggestion-topline">
                      <span className={`ats-priority-pill ${item.priority}`}>{label}</span>
                      <span className={`ats-issue-tag ${item.issue_type}`}>{item.issue_type}</span>
                    </div>
                    <strong>{item.title}</strong>
                    <p>{item.details}</p>
                    {item.suggested_edit ? <p className="ats-suggested-edit">{item.suggested_edit}</p> : null}
                  </div>
                ))}
              </div>
            ) : null
          )
        ) : (
          <p className="ats-empty-text">No recommendations are available yet.</p>
        )}
      </div>

      <div className="ats-double-grid">
        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Strong Evidence Skills</h4>
            <span className="ats-subtle-label">Experience/project proof</span>
          </div>
          {strongEvidenceSkills.length ? (
            <div className="ats-match-grid">
              {strongEvidenceSkills.map((item) => (
                <div className="ats-match-card" key={`strong-evidence-${item.keyword}`}>
                  <div className="ats-match-topline">
                    <strong>{item.keyword}</strong>
                    <span className="ats-priority-pill high">Tier {item.evidence_tier}</span>
                  </div>
                  <p className="ats-match-sections">{item.source_sections.join(", ")}</p>
                  {item.evidence.length ? <p>{item.evidence[0]}</p> : <p className="ats-empty-text">Evidence snippet unavailable.</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No strongly evidenced skills were detected yet.</p>
          )}
        </div>

        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Weak Evidence Skills</h4>
            <span className="ats-subtle-label">Skills needing proof</span>
          </div>
          {weakEvidenceSkills.length ? (
            <div className="ats-match-grid">
              {weakEvidenceSkills.map((item) => (
                <div className="ats-match-card" key={`weak-evidence-${item.keyword}`}>
                  <div className="ats-match-topline">
                    <strong>{item.keyword}</strong>
                    <span className="ats-priority-pill medium">Tier {item.evidence_tier}</span>
                  </div>
                  <p className="ats-match-sections">{item.source_sections.join(", ")}</p>
                  {item.evidence.length ? <p>{item.evidence[0]}</p> : <p className="ats-empty-text">No supporting evidence found in the resume.</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No skills-only evidence risks were detected.</p>
          )}
        </div>
      </div>

      <div className="ats-double-grid">
        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Matched Keywords</h4>
            <span className="ats-subtle-label">Resume evidence</span>
          </div>
          {matchedKeywords.length ? (
            <div className="ats-match-grid">
              {matchedKeywords.map((item) => (
                <div className="ats-match-card" key={`match-${item.keyword}`}>
                  <div className="ats-match-topline">
                    <strong>{item.keyword}</strong>
                    <span className={`ats-priority-pill ${item.importance}`}>{item.match_type}</span>
                  </div>
                  <p className="ats-match-sections">{item.source_sections.join(", ")}</p>
                  {item.evidence.length ? <p>{item.evidence[0]}</p> : <p className="ats-empty-text">Evidence snippet unavailable.</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No matched keywords were detected yet.</p>
          )}
        </div>

        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Job Requirements vs Resume Evidence</h4>
            <span className="ats-subtle-label">Comparison view</span>
          </div>
          {result.comparison_view.length ? (
            <div className="ats-comparison-grid">
              {result.comparison_view.map((item, index) => (
                <div className="ats-comparison-card" key={`comparison-${index}`}>
                  <div className="ats-comparison-topline">
                    <strong>{item.requirement}</strong>
                    <span className={`ats-status-pill ${item.status}`}>{item.status}</span>
                  </div>
                  <p className="ats-comparison-meta">{priorityLabel(item.importance)} importance</p>
                  {item.evidence.length ? <p>{item.evidence[0]}</p> : <p className="ats-empty-text">No supporting evidence found in the resume.</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="ats-empty-text">No comparison items to show yet.</p>
          )}
        </div>
      </div>

      {result.stuffing_warnings?.length ? (
        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Repetition Warnings</h4>
            <span className="ats-subtle-label">Keyword stuffing checks</span>
          </div>
          <div className="ats-warning-list">
            {result.stuffing_warnings.map((item, index) => (
              <div className="ats-warning-card" key={`stuffing-${index}`}>
                <div className="ats-warning-topline">
                  <strong>{item.keyword}</strong>
                  <span className={`ats-priority-pill ${item.severity}`}>{priorityLabel(item.severity)}</span>
                </div>
                <p>{item.details}</p>
                <p className="ats-warning-fix">{item.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="ats-block parse-preview-block">
        <div className="ats-block-head">
          <h4>ATS Parse Preview</h4>
          <span className="ats-subtle-label">Plain-text reading order</span>
        </div>
        <pre className="ats-parse-preview">{result.parse_preview}</pre>
      </div>
    </div>
  );
}

function confidenceTone(label) {
  if (label === "Strong Match") return "strong";
  if (label === "Moderate Match") return "moderate";
  return "weak";
}

function formatSourceLabel(source) {
  if (source === "pasted_fallback") return "fallback text";
  if (source === "pasted_description") return "pasted text";
  return "job URL";
}

function priorityLabel(priority) {
  if (!priority) return "";
  return priority.charAt(0).toUpperCase() + priority.slice(1);
}

export default App;
