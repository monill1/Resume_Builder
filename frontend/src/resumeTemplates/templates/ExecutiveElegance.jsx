import { ContactList, OrderedSections, TemplateSection } from "../shared";

const SIDEBAR_KEYS = ["skills"];

function ExecutiveSidebarSkills({ skills }) {
  if (!skills.length) return null;

  return (
    <TemplateSection title="Skills" variant="stacked" className="executive-stacked">
      <div className="executive-sidebar-list">
        {skills.map((item, index) => (
          <div className="executive-sidebar-item" key={`${item.name}-${index}`}>
            <p className="executive-sidebar-line">
              <strong>{item.name}:</strong> {item.items.join(", ")}
            </p>
          </div>
        ))}
      </div>
    </TemplateSection>
  );
}

export default function ExecutiveElegance({ data }) {
  const mainKeys = data.orderedSections.filter((key) => !SIDEBAR_KEYS.includes(key));

  return (
    <div className="resume-template executive-elegance">
      <div className="template-grid template-grid-sidebar executive-shell">
        <aside className="template-sidebar executive-sidebar">
          <div className="executive-sidebar-copy">
            <p className="template-kicker executive-kicker">Executive Profile</p>
            <h1>{data.basics.full_name}</h1>
            {data.basics.headline ? <p className="resume-template-headline">{data.basics.headline}</p> : null}
          </div>

          <div className="executive-divider" />

          <div className="template-sidebar-block executive-contact-block">
            <h2>Contact</h2>
            <ContactList contacts={data.contacts} icons layout="stack" className="is-executive" separator={false} />
          </div>

          <div className="executive-sidebar-sections">
            <ExecutiveSidebarSkills skills={data.skills} />
          </div>
        </aside>

        <main className="template-main executive-main">
          {data.basics.summary ? (
            <TemplateSection title="Professional Summary" variant="minimal" className="executive-summary-section">
              <p className="tpl-summary-text">{data.basics.summary}</p>
            </TemplateSection>
          ) : null}

          <OrderedSections data={data} sectionKeys={mainKeys.filter((key) => key !== "summary")} variant="minimal" className="executive-main-section" />
        </main>
      </div>
    </div>
  );
}
