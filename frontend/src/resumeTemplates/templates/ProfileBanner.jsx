import { ContactList, TemplateSection } from "../shared";
import { getSectionTitle } from "../helpers";
import { renderRichText } from "../../richText";

function getInitials(fullName) {
  const parts = String(fullName || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  const initials = parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("");
  return initials || "CV";
}

function SidebarEducation({ education }) {
  if (!education.length) return null;

  return (
    <TemplateSection title="Education" variant="banner-sidebar" className="profile-banner-sidebar-section">
      <div className="profile-banner-sidebar-list">
        {education.map((item, index) => (
          <article className="profile-banner-sidebar-entry" key={`${item.institution}-${index}`}>
            {item.degree ? <strong>{item.degree}</strong> : null}
            {item.institution ? <span>{item.institution}</span> : null}
            {[item.location, item.duration, item.score].filter(Boolean).map((line) => (
              <span key={line}>{line}</span>
            ))}
          </article>
        ))}
      </div>
    </TemplateSection>
  );
}

function SidebarSkills({ skills }) {
  if (!skills.length) return null;

  return (
    <TemplateSection title="Key Skills" variant="banner-sidebar" className="profile-banner-sidebar-section">
      <div className="profile-banner-skill-list">
        {skills.flatMap((group) => group.items.length ? group.items : [group.name]).filter(Boolean).map((skill, index) => (
          <p className="profile-banner-skill" key={`${skill}-${index}`}>
            <span className="profile-banner-dot">{"\u2022"}</span>
            <span>{skill}</span>
          </p>
        ))}
      </div>
    </TemplateSection>
  );
}

function BulletList({ items }) {
  return (
    <div className="profile-banner-bullets">
      {items.map((item, index) => (
        <p className="profile-banner-bullet" key={`${index}-${item}`}>
          <span>{"\u2022"}</span>
          <span>{renderRichText(item)}</span>
        </p>
      ))}
    </div>
  );
}

function ExperienceSection({ items }) {
  if (!items.length) return null;

  return (
    <TemplateSection title="Professional Experience" variant="banner-main" className="profile-banner-main-section">
      <div className="profile-banner-entry-list">
        {items.map((item, index) => (
          <article className="profile-banner-entry" key={`${item.company}-${item.role}-${index}`}>
            <p className="profile-banner-entry-head">
              <strong>{item.role}</strong>
              <span>
                {item.company_link ? (
                  <a href={item.company_link} target="_blank" rel="noreferrer">
                    {item.company}
                  </a>
                ) : (
                  item.company
                )}
                {[item.location, item.date_label].filter(Boolean).length ? ` | ${[item.location, item.date_label].filter(Boolean).join(" | ")}` : ""}
              </span>
            </p>
            <BulletList items={item.achievements} />
          </article>
        ))}
      </div>
    </TemplateSection>
  );
}

function ProjectsSection({ items }) {
  if (!items.length) return null;

  return (
    <TemplateSection title={getSectionTitle("projects")} variant="banner-main" className="profile-banner-main-section">
      <div className="profile-banner-entry-list">
        {items.map((item, index) => (
          <article className="profile-banner-entry" key={`${item.name}-${index}`}>
            <p className="profile-banner-entry-head">
              <strong>{item.name}</strong>
              <span>{[item.tech_stack, item.year].filter(Boolean).join(" | ")}</span>
            </p>
            {item.link ? (
              <a className="profile-banner-link" href={item.link} target="_blank" rel="noreferrer">
                Project Link
              </a>
            ) : null}
            <BulletList items={item.highlights} />
          </article>
        ))}
      </div>
    </TemplateSection>
  );
}

function CertificationsSection({ items }) {
  if (!items.length) return null;

  return (
    <TemplateSection title={getSectionTitle("certifications", items.length)} variant="banner-main" className="profile-banner-main-section">
      <div className="profile-banner-cert-list">
        {items.map((item, index) => (
          <p className="profile-banner-cert" key={`${item.title}-${index}`}>
            <span>{"\u2022"}</span>
            <span>
              <strong>{item.title}</strong>
              {[item.issuer, item.year].filter(Boolean).length ? `, ${[item.issuer, item.year].filter(Boolean).join(" | ")}` : ""}
            </span>
          </p>
        ))}
      </div>
    </TemplateSection>
  );
}

export default function ProfileBanner({ data }) {
  const mainSections = data.orderedSections.filter((key) => !["summary", "skills", "education"].includes(key));

  return (
    <div className="resume-template profile-banner">
      <header className="profile-banner-hero">
        <div className="profile-banner-avatar" aria-hidden="true">
          <span>{getInitials(data.basics.full_name)}</span>
        </div>
        <div className="profile-banner-hero-copy">
          <h1>{data.basics.full_name}</h1>
          {data.basics.headline ? <p className="profile-banner-headline">{data.basics.headline}</p> : null}
          {data.basics.summary ? <p className="profile-banner-summary">{renderRichText(data.basics.summary)}</p> : null}
        </div>
      </header>

      <div className="profile-banner-body">
        <aside className="profile-banner-sidebar">
          {data.contacts.length ? (
            <TemplateSection title="Personal Information" variant="banner-sidebar" className="profile-banner-sidebar-section">
              <ContactList contacts={data.contacts} icons layout="stack" className="is-profile-banner" separator={false} />
            </TemplateSection>
          ) : null}
          <SidebarEducation education={data.education} />
          <SidebarSkills skills={data.skills} />
        </aside>

        <main className="profile-banner-main">
          {mainSections.map((sectionKey) => {
            if (sectionKey === "experience") return <ExperienceSection key={sectionKey} items={data.experience} />;
            if (sectionKey === "projects") return <ProjectsSection key={sectionKey} items={data.projects} />;
            if (sectionKey === "certifications") return <CertificationsSection key={sectionKey} items={data.certifications} />;
            return null;
          })}
        </main>
      </div>
    </div>
  );
}
