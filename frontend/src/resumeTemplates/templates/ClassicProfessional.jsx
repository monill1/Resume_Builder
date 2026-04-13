import { ContactList, OrderedSections } from "../shared";

export default function ClassicProfessional({ data }) {
  return (
    <div className="resume-template classic-professional">
      <header className="resume-template-header is-classic">
        <h1>{data.basics.full_name.toUpperCase()}</h1>
        {data.basics.headline ? <p className="resume-template-headline">{data.basics.headline}</p> : null}
        <ContactList contacts={data.contacts} icons layout="row" className="is-classic" />
      </header>

      <div className="resume-template-body">
        <OrderedSections data={data} sectionKeys={data.orderedSections} variant="line" />
      </div>
    </div>
  );
}
