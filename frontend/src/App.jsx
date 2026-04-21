import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "./config";
import { stripRichText } from "./richText";
import ResumePreviewPanel from "./resumeTemplates/ResumePreview";
import { DEFAULT_TEMPLATE_ID, RESUME_TEMPLATES, getTemplateMeta } from "./resumeTemplates/templateMeta";
import { sampleResume } from "./sampleResume";
import { normalizeLayoutOptions, normalizeResumeData, normalizeSectionOrder, normalizeUrl, SECTION_LABELS } from "./resumeData";

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

const RESUME_EXPORT_RULES = [
  { path: ["basics", "full_name"], label: "Full Name", minLength: 2 },
  { path: ["basics", "email"], label: "Email", minLength: 3, validate: (value) => /\S+@\S+\.\S+/.test(value) || "Email must be valid." },
  { path: ["basics", "phone"], label: "Phone", minLength: 7 },
  { path: ["basics", "location"], label: "Location", minLength: 2 },
  { path: ["basics", "summary"], label: "Professional Summary", minLength: 30 },
];
const BOLD_MARKER = "**";
const HEX_COLOR_RE = /^#[0-9a-f]{6}$/i;
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
    input.focus();
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
  const [atsLoading, setAtsLoading] = useState(false);
  const [atsFixing, setAtsFixing] = useState(false);
  const [atsStatus, setAtsStatus] = useState("Paste a public job URL, a job description, or both to run a recruiter-style ATS check.");
  const [atsResult, setAtsResult] = useState(null);
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
      setAuthStatus(error.message);
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
    certifications: resume.certifications.filter((item) => hasAnyText(item.title, item.issuer, item.year)),
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

  const analyzeAts = async () => {
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
      setAtsStatus("ATS analysis complete. Review missing requirements, formatting risk, and exact next edits below.");
    } catch (error) {
      setAtsResult(null);
      setAtsStatus(`ATS analysis failed: ${error.message}`);
    } finally {
      setAtsLoading(false);
    }
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
      const normalizedOptimizedResume = normalizeResumeData(data.optimized_resume);
      const normalizedCurrentResume = normalizeResumeData(structuredClone(resume));
      const resumeChanged = JSON.stringify(normalizedOptimizedResume) !== JSON.stringify(normalizedCurrentResume);
      setResume(normalizedOptimizedResume);
      setAtsResult(data.analysis);
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
    <div className="page-shell">
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

      <div className="page-container">
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
                <strong>{activeWorkspace === "ats" ? "ATS workspace with live editor data" : "Editor, PDF export, and ATS scoring in one place"}</strong>
                <p>
                  {activeWorkspace === "ats"
                    ? "Run ATS analysis in a dedicated page-style workspace while still using the current resume data from the editor."
                    : "Compare your resume against a public posting or pasted job description with section scores, risk checks, and edit-ready recommendations."}
                </p>
                <Button
                  variant="secondary"
                  className="hero-ats-link"
                  onClick={activeWorkspace === "ats" ? openEditorWorkspace : openAtsWorkspace}
                >
                  {activeWorkspace === "ats" ? "Open Editor Workspace" : "Open ATS Workspace"}
                </Button>
              </div>
            </div>
          </div>
        </header>

        {activeWorkspace === "editor" ? (
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
        ) : (
          <ATSWorkspaceSection
            atsLoading={atsLoading}
            atsFixing={atsFixing}
            atsStatus={atsStatus}
            atsTargetTitle={atsTargetTitle}
            atsJobUrl={atsJobUrl}
            atsJobDescription={atsJobDescription}
            atsResult={atsResult}
            atsOptimization={atsOptimization}
            currentResume={currentResumePayload}
            onTargetTitleChange={setAtsTargetTitle}
            onJobUrlChange={setAtsJobUrl}
            onJobDescriptionChange={setAtsJobDescription}
            onAnalyze={analyzeAts}
            onAutoFix={autoFixResume}
            onLoadDemoJob={loadDemoJob}
          />
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
  const paymentLabel = paymentStatus?.exempt
    ? "PDF: Admin"
    : `PDF Credits: ${Number(paymentStatus?.remaining_downloads || 0)}`;

  return (
    <nav className="app-navbar">
      <div className="app-navbar-inner">
        <div className="app-navbar-brand">
          <span className="app-navbar-label">ATS Resume Builder</span>
          <strong>Save, export, and manage your resume from one toolbar</strong>
        </div>

        <div className="app-navbar-actions">
          <Button variant="nav" className={activeWorkspace === "editor" ? "nav-pill-active" : ""} onClick={onJumpToEditor}>
            Editor
          </Button>
          <Button variant="nav" className={activeWorkspace === "ats" ? "nav-pill-active" : ""} onClick={onJumpToAts}>
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
          />
          <span className="app-navbar-payment">{paymentLabel}</span>
          <Button variant="nav" onClick={onGenerateResume} disabled={loading}>
            {loading ? "Generating..." : "Download PDF"}
          </Button>
          <Button variant="nav" className="app-navbar-account" onClick={onLogout} title={`Signed in as ${authUser.email}`}>
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
  atsResult,
  atsOptimization,
  currentResume,
  onTargetTitleChange,
  onJobUrlChange,
  onJobDescriptionChange,
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
              <span className="ats-workbench-pill">Connected to live editor data</span>
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

            <div className="ats-toolbar">
              <Button variant="primary" className="ats-action-btn" onClick={onAnalyze} disabled={atsLoading}>
                {atsLoading ? "Analyzing..." : "Run ATS Test"}
              </Button>
              <Button variant="secondary" className="ats-action-btn" onClick={onAutoFix} disabled={atsLoading || atsFixing}>
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
                Auto Fix updates the live resume using evidence already present in your current resume.
              </p>
            </div>
          </div>

          <div className="ats-sidekick-card">
            <div className="ats-sidekick-block">
              <p className="ats-kicker">Connected Resume</p>
              <h3>Current editor data used for ATS</h3>
              <div className="ats-resume-sync-card">
                <strong>{currentResume.basics.full_name || "Untitled resume"}</strong>
                <p>{currentResume.basics.headline?.trim() || "No headline added yet."}</p>
                <div className="ats-sync-metrics">
                  <span>{currentResume.experience.length} experience</span>
                  <span>{currentResume.projects.length} projects</span>
                  <span>{currentResume.skills.length} skill groups</span>
                  <span>{filledSectionCount} filled sections</span>
                </div>
                <p className="ats-sync-note">
                  Every ATS run automatically uses the latest content from the editor section. No manual copy or save step is needed.
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
                  <h3>ATS insights and recommendation panels</h3>
                </div>
                <div className="ats-results-actions">
                  <span className="ats-workbench-pill is-result">Latest analysis loaded</span>
                  <Button variant="primary" onClick={onAutoFix} disabled={atsLoading || atsFixing}>
                    {atsFixing ? "Auto-Fixing..." : "Improve Score by Auto-Fixing"}
                  </Button>
                </div>
              </div>
              <ATSResultPanel result={atsResult} optimization={atsOptimization} />
            </>
          ) : (
            <div className="ats-empty-state">
              <p className="ats-kicker">Ready</p>
              <h3>Your ATS dashboard will appear here.</h3>
              <p>Run the ATS test from this section to load scorecards, matched keywords, formatting warnings, and suggested edits.</p>
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

function SaveActionsMenu({ hasSavedDraft, onSaveDraft, onClearSavedDraft, onLoadDemoData }) {
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

function ATSResultPanel({ result, optimization }) {
  const groupedMissingKeywords = {
    high: result.missing_keywords.filter((item) => item.importance === "high"),
    medium: result.missing_keywords.filter((item) => item.importance === "medium"),
    low: result.missing_keywords.filter((item) => item.importance === "low"),
  };
  return (
    <div className="ats-result">
      <div className="ats-score-hero" style={{ "--score": `${result.overall_score}%` }}>
        <div className="ats-score-ring">
          <div className="ats-score-ring-inner">
            <strong>{result.overall_score}</strong>
            <span>/100</span>
          </div>
        </div>
        <div className="ats-score-copy">
          <div className="ats-score-topline">
            <h3>ATS Match Score</h3>
            <span className={`ats-confidence-pill tone-${confidenceTone(result.confidence_label)}`}>{result.confidence_label}</span>
          </div>
          <p className="ats-job-title">{result.job_title}</p>
          <p>{result.summary}</p>
          <div className="ats-meta-row">
            <span className="ats-meta-pill">Parsing confidence {Math.round(result.parsing_confidence * 100)}%</span>
            <span className="ats-meta-pill">Source {formatSourceLabel(result.job_source)}</span>
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
          <span className="ats-subtle-label">Exact next edits</span>
        </div>
        {result.improvement_suggestions.length ? (
          <div className="ats-suggestion-grid">
            {result.improvement_suggestions.map((item, index) => (
              <div className="ats-suggestion-card" key={`suggestion-${index}`}>
                <div className="ats-suggestion-topline">
                  <span className={`ats-priority-pill ${item.priority}`}>{priorityLabel(item.priority)}</span>
                  <span className={`ats-issue-tag ${item.issue_type}`}>{item.issue_type}</span>
                </div>
                <strong>{item.title}</strong>
                <p>{item.details}</p>
                {item.suggested_edit ? <p className="ats-suggested-edit">{item.suggested_edit}</p> : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="ats-empty-text">No recommendations are available yet.</p>
        )}
      </div>

      <div className="ats-double-grid">
        <div className="ats-block">
          <div className="ats-block-head">
            <h4>Matched Keywords</h4>
            <span className="ats-subtle-label">Resume evidence</span>
          </div>
          {result.matched_keywords.length ? (
            <div className="ats-match-grid">
              {result.matched_keywords.map((item) => (
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
            <p className="ats-empty-text">No strong matched keywords were detected yet.</p>
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
