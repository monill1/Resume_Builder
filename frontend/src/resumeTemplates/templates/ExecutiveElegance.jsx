import { ContactList, OrderedSections, TemplateSection } from "../shared";
import { getSectionTitle } from "../helpers";
import { renderRichText } from "../../richText";

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

function ExecutiveSidebarCertifications({ certifications }) {
  if (!certifications.length) return null;

  return (
    <TemplateSection title={getSectionTitle("certifications", certifications.length)} variant="stacked" className="executive-stacked">
      <div className="executive-sidebar-list">
        {certifications.map((item, index) => (
          <div className="executive-sidebar-item executive-cert-item" key={`${item.title}-${index}`}>
            <p className="executive-cert-head">
              <strong>{item.title}</strong>
              {item.year ? <span>{item.year}</span> : null}
            </p>
            {item.issuer ? <p className="executive-sidebar-meta">{item.issuer}</p> : null}
          </div>
        ))}
      </div>
    </TemplateSection>
  );
}

export default function ExecutiveElegance({ data }) {
  const certificationInSidebar = Boolean(data.layout_options?.executive_certifications_in_sidebar);
  const sidebarKeys = certificationInSidebar ? ["skills", "certifications"] : ["skills"];
  const sidebarSections = data.orderedSections.filter((key) => sidebarKeys.includes(key));
  const mainKeys = data.orderedSections.filter((key) => !sidebarKeys.includes(key));

  return (
    <div className="resume-template executive-elegance">
      <div className="template-grid template-grid-sidebar executive-shell">
        <aside className="template-sidebar executive-sidebar">
          <div className="executive-sidebar-copy">
            <p className="template-kicker executive-kicker">Executive Profile</p>
            <h1>{data.basics.full_name}</h1>
            {data.basics.headline ? <p className="resume-template-headline">{data.basics.headline}</p> : null}
          </div>

          <div className="template-sidebar-block executive-contact-block">
            <h2>Contact</h2>
            <ContactList contacts={data.contacts} icons layout="stack" className="is-executive" separator={false} />
          </div>

          <div className="executive-sidebar-sections">
            {sidebarSections.map((sectionKey) => {
              if (sectionKey === "skills") return <ExecutiveSidebarSkills key={sectionKey} skills={data.skills} />;
              if (sectionKey === "certifications") {
                return <ExecutiveSidebarCertifications key={sectionKey} certifications={data.certifications} />;
              }
              return null;
            })}
          </div>
        </aside>

        <main className="template-main executive-main">
          {data.basics.summary ? (
            <TemplateSection title="Professional Summary" variant="minimal" className="executive-summary-section">
              <p className="tpl-summary-text">{renderRichText(data.basics.summary)}</p>
            </TemplateSection>
          ) : null}

          <OrderedSections
            data={data}
            sectionKeys={mainKeys.filter((key) => key !== "summary")}
            variant="minimal"
            className="executive-main-section"
            projectLinkMode="icon"
          />
        </main>
      </div>
    </div>
  );
}
