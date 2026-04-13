import { getSectionTitle } from "./helpers";

function ContactIcon({ type }) {
  if (type === "phone") return <img src="/contact-logo-clean.png" className="tpl-contact-icon" alt="" aria-hidden="true" />;
  if (type === "email") return <img src="/email-logo-clean.png" className="tpl-contact-icon" alt="" aria-hidden="true" />;
  if (type === "location") return <img src="/location-logo-clean.png" className="tpl-contact-icon" alt="" aria-hidden="true" />;
  if (type === "linkedin") return <img src="/linkedin-logo-clean.png" className="tpl-contact-icon" alt="" aria-hidden="true" />;
  if (type === "github") return <img src="/github-logo-clean.png" className="tpl-contact-icon" alt="" aria-hidden="true" />;
  return <span className="tpl-contact-fallback">{"\u2197"}</span>;
}

export function ContactList({ contacts, layout = "row", icons = false, className = "", separator = true }) {
  const wrapClassName = ["tpl-contact-list", `is-${layout}`, icons ? "has-icons" : "", className].filter(Boolean).join(" ");

  return (
    <div className={wrapClassName}>
      {contacts.map((item, index) => {
        const content = (
          <>
            {icons ? (
              <span className="tpl-contact-icon-wrap">
                <ContactIcon type={item.type} />
              </span>
            ) : null}
            <span>{item.label}</span>
          </>
        );

        const node = item.href ? (
          <a key={`${item.type}-${index}`} className="tpl-contact-link" href={item.href} target="_blank" rel="noreferrer">
            {content}
          </a>
        ) : (
          <span key={`${item.type}-${index}`} className="tpl-contact-link">
            {content}
          </span>
        );

        return (
          <span className="tpl-contact-entry" key={`${item.type}-${index}`}>
            {index > 0 && layout === "row" && separator ? <span className="tpl-contact-separator">|</span> : null}
            {node}
          </span>
        );
      })}
    </div>
  );
}

export function TemplateSection({ title, variant = "line", className = "", children }) {
  return (
    <section className={["tpl-section", `variant-${variant}`, className].filter(Boolean).join(" ")}>
      <div className="tpl-section-head">
        <h3>{title}</h3>
        <span className="tpl-section-rule" />
      </div>
      <div className="tpl-section-body">{children}</div>
    </section>
  );
}

function BulletList({ items, className = "" }) {
  return (
    <div className={["tpl-bullet-list", className].filter(Boolean).join(" ")}>
      {items.map((item, index) => (
        <p className="tpl-bullet-row" key={`${index}-${item}`}>
          <span className="tpl-bullet-dot">{"\u2022"}</span>
          <span>{item}</span>
        </p>
      ))}
    </div>
  );
}

function SummarySection({ summary }) {
  return <p className="tpl-summary-text">{summary}</p>;
}

function SkillsSection({ skills }) {
  return (
    <div className="tpl-bullet-list">
      {skills.map((item, index) => (
        <p className="tpl-bullet-row" key={`${item.name}-${index}`}>
          <span className="tpl-bullet-dot">{"\u2022"}</span>
          <span>
            <strong>{item.name}:</strong> {item.items.join(", ")}
          </span>
        </p>
      ))}
    </div>
  );
}

function ExperienceSection({ items }) {
  return (
    <div className="tpl-entry-list">
      {items.map((item, index) => (
        <article className="tpl-entry" key={`${item.company}-${item.role}-${index}`}>
          <div className="tpl-entry-head tpl-entry-head-grid">
            <div className="tpl-entry-primary">
              <strong className="tpl-entry-role">{item.role}</strong>
              {item.company_link ? (
                <a className="tpl-entry-company is-link" href={item.company_link} target="_blank" rel="noreferrer">
                  {item.company}
                </a>
              ) : (
                <span className="tpl-entry-company">{item.company}</span>
              )}
            </div>
            <div className="tpl-entry-meta">
              {item.location ? <span className="tpl-entry-location">{item.location}</span> : null}
              {item.date_label ? <span className="tpl-entry-date">{item.date_label}</span> : null}
            </div>
          </div>
          <BulletList items={item.achievements} />
        </article>
      ))}
    </div>
  );
}

function ProjectsSection({ items, linkMode = "text" }) {
  return (
    <div className="tpl-entry-list">
      {items.map((item, index) => (
        <article className="tpl-entry" key={`${item.name}-${index}`}>
          <div className="tpl-entry-head">
            <div className="tpl-entry-primary">
              <div className="tpl-project-title-row">
                <strong className="tpl-entry-role">{item.name}</strong>
                {item.link && linkMode === "icon" ? (
                  <a className="tpl-project-icon-link" href={item.link} target="_blank" rel="noreferrer" aria-label={`${item.name} link`}>
                    <img src="/github-logo-clean.png" className="tpl-project-icon" alt="" aria-hidden="true" />
                  </a>
                ) : null}
              </div>
              {item.link && linkMode !== "icon" ? (
                <a className="tpl-entry-company is-link" href={item.link} target="_blank" rel="noreferrer">
                  Project Link
                </a>
              ) : null}
            </div>
            {item.tech_stack ? <span className="tpl-entry-tech">{item.tech_stack}</span> : null}
          </div>
          <BulletList items={item.highlights} />
        </article>
      ))}
    </div>
  );
}

function EducationSection({ items }) {
  return (
    <div className="tpl-entry-list">
      {items.map((item, index) => (
        <article className="tpl-entry" key={`${item.institution}-${index}`}>
          <div className="tpl-entry-head">
            <div className="tpl-entry-primary">
              <strong className="tpl-entry-role">{item.institution}</strong>
              {item.degree ? <span className="tpl-entry-company">{item.degree}</span> : null}
            </div>
            {item.duration ? <span className="tpl-entry-date">{item.duration}</span> : null}
          </div>
          {item.location || item.score ? (
            <p className="tpl-inline-meta">{[item.location, item.score].filter(Boolean).join(" | ")}</p>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function CertificationsSection({ items }) {
  return (
    <div className="tpl-entry-list">
      {items.map((item, index) => (
        <article className="tpl-entry" key={`${item.title}-${index}`}>
          <div className="tpl-entry-head">
            <div className="tpl-entry-primary">
              <strong className="tpl-entry-role">{item.title}</strong>
              {item.issuer ? <span className="tpl-entry-company">{item.issuer}</span> : null}
            </div>
            {item.year ? <span className="tpl-entry-date">{item.year}</span> : null}
          </div>
        </article>
      ))}
    </div>
  );
}

export function OrderedSections({ data, sectionKeys, variant = "line", className = "" }) {
  return sectionKeys.map((sectionKey) => {
    if (sectionKey === "summary" && data.basics.summary) {
      return (
        <TemplateSection key={sectionKey} title={getSectionTitle(sectionKey)} variant={variant} className={className}>
          <SummarySection summary={data.basics.summary} />
        </TemplateSection>
      );
    }

    if (sectionKey === "skills" && data.skills.length) {
      return (
        <TemplateSection key={sectionKey} title={getSectionTitle(sectionKey)} variant={variant} className={className}>
          <SkillsSection skills={data.skills} />
        </TemplateSection>
      );
    }

    if (sectionKey === "experience" && data.experience.length) {
      return (
        <TemplateSection key={sectionKey} title={getSectionTitle(sectionKey)} variant={variant} className={className}>
          <ExperienceSection items={data.experience} />
        </TemplateSection>
      );
    }

    if (sectionKey === "projects" && data.projects.length) {
      return (
        <TemplateSection key={sectionKey} title={getSectionTitle(sectionKey)} variant={variant} className={className}>
          <ProjectsSection items={data.projects} linkMode={variant === "accent" ? "icon" : "text"} />
        </TemplateSection>
      );
    }

    if (sectionKey === "education" && data.education.length) {
      return (
        <TemplateSection key={sectionKey} title={getSectionTitle(sectionKey)} variant={variant} className={className}>
          <EducationSection items={data.education} />
        </TemplateSection>
      );
    }

    if (sectionKey === "certifications" && data.certifications.length) {
      return (
        <TemplateSection
          key={sectionKey}
          title={getSectionTitle(sectionKey, data.certifications.length)}
          variant={variant}
          className={className}
        >
          <CertificationsSection items={data.certifications} />
        </TemplateSection>
      );
    }

    return null;
  });
}
