import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "./config";
import ResumePreviewPanel from "./resumeTemplates/ResumePreview";
import { DEFAULT_TEMPLATE_ID, RESUME_TEMPLATES, getTemplateMeta } from "./resumeTemplates/templateMeta";
import { sampleResume } from "./sampleResume";
import { normalizeResumeData, normalizeSectionOrder, normalizeUrl, SECTION_LABELS } from "./resumeData";

const RESUME_DRAFT_KEY = "ats-resume-builder-draft";
const RESUME_TEMPLATE_KEY = "ats-resume-builder-template";
const WORKSPACE_VIEW_KEY = "ats-resume-builder-workspace-view";
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
    const value = String(getValueAtPath(resumePayload, rule.path) || "").trim();

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

function buildFallbackResumeFilename(fullName) {
  const normalizedName = String(fullName || "")
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1F]+/g, "")
    .replace(/\s+/g, "_");
  return `${normalizedName || "resume"}.pdf`;
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
  const [activeWorkspace, setActiveWorkspace] = useState(() => (window.localStorage.getItem(WORKSPACE_VIEW_KEY) === "ats" ? "ats" : "editor"));
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("Ready to build a polished resume and score it against a target job.");
  const [atsTargetTitle, setAtsTargetTitle] = useState("");
  const [atsJobUrl, setAtsJobUrl] = useState("");
  const [atsJobDescription, setAtsJobDescription] = useState("");
  const [atsLoading, setAtsLoading] = useState(false);
  const [atsStatus, setAtsStatus] = useState("Paste a public job URL, a job description, or both to run a recruiter-style ATS check.");
  const [atsResult, setAtsResult] = useState(null);
  const [hasSavedDraft, setHasSavedDraft] = useState(false);

  const hasAnyText = (...values) => values.some((value) => String(value || "").trim());

  useEffect(() => {
    async function hydrateFromBackend() {
      try {
        const savedDraft = window.localStorage.getItem(RESUME_DRAFT_KEY);
        if (savedDraft) {
          const parsedDraft = JSON.parse(savedDraft);
          setResume(normalizeResumeData(parsedDraft));
          setHasSavedDraft(true);
          setStatus("Saved draft restored. You can continue where you left off.");
          return;
        }
      } catch {
        // Ignore local draft parse errors and fall back to sample data.
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/sample`);
        if (!response.ok) return;
        const data = await response.json();
        if (data?.resume) setResume(normalizeResumeData(data.resume));
      } catch {
        // Keep local sample data when backend is offline.
      }
    }

    hydrateFromBackend();
  }, []);

  useEffect(() => {
    window.localStorage.setItem(RESUME_TEMPLATE_KEY, selectedTemplate);
  }, [selectedTemplate]);

  useEffect(() => {
    window.localStorage.setItem(WORKSPACE_VIEW_KEY, activeWorkspace);
  }, [activeWorkspace]);

  const saveDraft = () => {
    try {
      window.localStorage.setItem(RESUME_DRAFT_KEY, JSON.stringify(resume));
      setHasSavedDraft(true);
      setStatus("Draft saved successfully. It will restore automatically next time.");
    } catch {
      setStatus("Unable to save the draft in this browser.");
    }
  };

  const clearSavedDraft = () => {
    try {
      window.localStorage.removeItem(RESUME_DRAFT_KEY);
      setHasSavedDraft(false);
      setStatus("Saved draft cleared.");
    } catch {
      setStatus("Unable to clear the saved draft.");
    }
  };

  const updateBasics = (key, value) => {
    setResume((current) => ({ ...current, basics: { ...current.basics, [key]: value } }));
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

  const handleSkillItemsChange = (index, value) => {
    const items = value.split(",").map((item) => item.trim());
    updateArrayItem("skills", index, "items", items);
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
    section_order: normalizeSectionOrder(resume.section_order),
  });
  const currentResumePayload = cleanPayload();

  const generateResume = async () => {
    setLoading(true);
    setStatus("Generating PDF...");
    try {
      const validationMessage = validateResumeForExport(currentResumePayload);
      if (validationMessage) {
        throw new Error(validationMessage);
      }

      const response = await fetch(`${API_BASE_URL}/api/resume/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: selectedTemplate,
          resume: currentResumePayload,
        }),
      });
      if (!response.ok) {
        const message = await readErrorMessage(response, "Unable to generate resume");
        throw new Error(message);
      }

      const blob = await response.blob();
      if (!blob.size) {
        throw new Error("The server returned an empty PDF file.");
      }

      const filename = getDownloadFilename(response.headers, buildFallbackResumeFilename(resume.basics.full_name));
      downloadBlob(blob, filename);
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
    const normalizedJobUrl = normalizeUrl(atsJobUrl);
    const trimmedJobDescription = atsJobDescription.trim();
    const trimmedTargetTitle = atsTargetTitle.trim();
    if (!normalizedJobUrl && !trimmedJobDescription) {
      setAtsStatus("Add a public job link or paste the job description so the ATS checker has target requirements.");
      return;
    }

    setAtsLoading(true);
    setAtsStatus("Extracting job requirements, scoring resume evidence, and checking ATS formatting risk...");
    try {
      const response = await fetch(`${API_BASE_URL}/api/ats/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_url: normalizedJobUrl || null,
          job_description: trimmedJobDescription || null,
          target_title: trimmedTargetTitle || null,
          resume: currentResumePayload,
        }),
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

  const loadDemoData = () => {
    setResume(normalizeResumeData(structuredClone(sampleResume)));
    setStatus("Demo resume loaded. You can edit it, save it, or export a PDF.");
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

  return (
    <div className="page-shell">
      <AppNavbar
        activeWorkspace={activeWorkspace}
        selectedTemplate={selectedTemplate}
        templates={RESUME_TEMPLATES}
        loading={loading}
        hasSavedDraft={hasSavedDraft}
        onTemplateChange={handleTemplateChange}
        onSaveDraft={saveDraft}
        onGenerateResume={generateResume}
        onLoadDemoData={loadDemoData}
        onClearSavedDraft={clearSavedDraft}
        onJumpToAts={openAtsWorkspace}
        onJumpToEditor={openEditorWorkspace}
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
            <TextArea label="Professional Summary" value={resume.basics.summary} onChange={(value) => updateBasics("summary", value)} rows={5} />
            <p className="field-help">Spelling suggestions appear automatically from your browser while typing.</p>

            <SectionTitle title="Section Order" />
            <SectionOrderEditor order={normalizeSectionOrder(resume.section_order)} onMove={moveSection} />

            <SectionTitle title="Skills" actionLabel="Add Skill Group" onAction={() => addItem("skills", emptySkill)} />
            {resume.skills.map((item, index) => (
              <Card key={`skill-${index}`}>
                <div className="card-head">
                  <strong>Skill Group {index + 1}</strong>
                  <Button variant="ghost" onClick={() => removeItem("skills", index)}>Remove</Button>
                </div>
                <Field label="Category Name" value={item.name} onChange={(value) => updateArrayItem("skills", index, "name", value)} />
                <Field label="Comma-separated Skills" value={item.items.join(", ")} onChange={(value) => handleSkillItemsChange(index, value)} />
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
              <ResumePreviewPanel resume={resume} selectedTemplate={selectedTemplate} />
            </section>
          </main>
        ) : (
          <ATSWorkspaceSection
            atsLoading={atsLoading}
            atsStatus={atsStatus}
            atsTargetTitle={atsTargetTitle}
            atsJobUrl={atsJobUrl}
            atsJobDescription={atsJobDescription}
            atsResult={atsResult}
            currentResume={currentResumePayload}
            onTargetTitleChange={setAtsTargetTitle}
            onJobUrlChange={setAtsJobUrl}
            onJobDescriptionChange={setAtsJobDescription}
            onAnalyze={analyzeAts}
            onLoadDemoJob={loadDemoJob}
          />
        )}
      </div>
    </div>
  );
}

function AppNavbar({ activeWorkspace, loading, hasSavedDraft, selectedTemplate, templates, onTemplateChange, onSaveDraft, onGenerateResume, onLoadDemoData, onClearSavedDraft, onJumpToAts, onJumpToEditor }) {
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
          <TemplatePicker selectedTemplate={selectedTemplate} templates={templates} onTemplateChange={onTemplateChange} />
          <Button variant="nav" onClick={onSaveDraft}>
            Save Data
          </Button>
          <Button variant="nav" onClick={onGenerateResume} disabled={loading}>
            {loading ? "Generating..." : "Download PDF"}
          </Button>
          <Button variant="nav" onClick={onLoadDemoData}>
            Load Demo Data
          </Button>
          {hasSavedDraft ? (
            <Button variant="nav" onClick={onClearSavedDraft}>
              Clear Saved
            </Button>
          ) : null}
        </div>
      </div>
    </nav>
  );
}

function ATSWorkspaceSection({
  atsLoading,
  atsStatus,
  atsTargetTitle,
  atsJobUrl,
  atsJobDescription,
  atsResult,
  currentResume,
  onTargetTitleChange,
  onJobUrlChange,
  onJobDescriptionChange,
  onAnalyze,
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
              <Button variant="secondary" onClick={onLoadDemoJob}>
                Load Demo Job
              </Button>
            </div>

            <p className="field-help ats-help">
              If URL scraping fails, the pasted job description becomes the fallback automatically. The score uses weighted rule-based
              matching, context checks, and ATS formatting heuristics.
            </p>
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
                <span className="ats-workbench-pill is-result">Latest analysis loaded</span>
              </div>
              <ATSResultPanel result={atsResult} />
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

function TextArea({ label, value, onChange, rows, spellCheck = true }) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        rows={rows}
        value={value}
        spellCheck={spellCheck}
        autoCorrect={spellCheck ? "on" : "off"}
        autoCapitalize={spellCheck ? "sentences" : "off"}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
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
          <div className="bullet-input-row" key={`${label}-${index}`}>
            <span className="bullet-input-dot">{"\u2022"}</span>
            <input
              value={item}
              spellCheck={true}
              autoCorrect="on"
              autoCapitalize="sentences"
              onChange={(event) => onChange(index, event.target.value)}
              placeholder="Write one bullet point"
            />
            <Button variant="ghost" className="bullet-remove-btn" onClick={() => onRemove(index)}>
              Remove
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function ATSResultPanel({ result }) {
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
