import { ContactList, OrderedSections } from "../shared";

export default function ContemporaryAccent({ data }) {
  return (
    <div className="resume-template contemporary-accent">
      <header className="resume-template-header is-accent">
        <div className="accent-band" />
        <div className="accent-copy">
          <p className="template-kicker">Contemporary Professional</p>
          <h1>{data.basics.full_name}</h1>
          {data.basics.headline ? <p className="resume-template-headline">{data.basics.headline}</p> : null}
          <ContactList contacts={data.contacts} icons layout="row" className="is-accent" />
        </div>
      </header>

      <div className="resume-template-body accent-body">
        <OrderedSections data={data} sectionKeys={data.orderedSections} variant="accent" />
      </div>
    </div>
  );
}
