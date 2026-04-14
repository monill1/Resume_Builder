import { useEffect, useRef, useState } from "react";
import { buildResumeViewModel } from "./helpers";
import { DEFAULT_TEMPLATE_ID } from "./templateMeta";
import ClassicProfessional from "./templates/ClassicProfessional";
import ContemporaryAccent from "./templates/ContemporaryAccent";
import ExecutiveElegance from "./templates/ExecutiveElegance";

const PREVIEW_PAGE_WIDTH = 816;
const PREVIEW_PAGE_HEIGHT = 1056;

const TEMPLATE_COMPONENTS = {
  "classic-professional": ClassicProfessional,
  "contemporary-accent": ContemporaryAccent,
  "executive-elegance": ExecutiveElegance,
};

export default function ResumePreview({ resume, selectedTemplate }) {
  const previewStageRef = useRef(null);
  const sheetRef = useRef(null);
  const [previewScale, setPreviewScale] = useState(1);
  const [sheetHeight, setSheetHeight] = useState(PREVIEW_PAGE_HEIGHT);

  const templateId = TEMPLATE_COMPONENTS[selectedTemplate] ? selectedTemplate : DEFAULT_TEMPLATE_ID;
  const TemplateComponent = TEMPLATE_COMPONENTS[templateId];
  const data = buildResumeViewModel(resume);

  useEffect(() => {
    if (!previewStageRef.current || !sheetRef.current) return undefined;

    const measure = () => {
      const stageWidth = previewStageRef.current?.clientWidth || PREVIEW_PAGE_WIDTH;
      const nextScale = Math.min(stageWidth / PREVIEW_PAGE_WIDTH, 1);
      const nextHeight = Math.max(sheetRef.current?.scrollHeight || PREVIEW_PAGE_HEIGHT, PREVIEW_PAGE_HEIGHT);
      setPreviewScale(nextScale);
      setSheetHeight(nextHeight);
    };

    const rafMeasure = () => window.requestAnimationFrame(measure);

    measure();

    const stageObserver = new ResizeObserver(() => rafMeasure());
    const sheetObserver = new ResizeObserver(() => rafMeasure());
    stageObserver.observe(previewStageRef.current);
    sheetObserver.observe(sheetRef.current);

    return () => {
      stageObserver.disconnect();
      sheetObserver.disconnect();
    };
  }, [resume, templateId]);

  return (
    <div className="resume-preview-stage" ref={previewStageRef}>
      <div className="resume-preview-canvas" style={{ height: `${sheetHeight * previewScale}px` }}>
        <div
          ref={sheetRef}
          className={`resume-sheet preview-template-${templateId}`}
          data-template-id={templateId}
          style={{
            width: `${PREVIEW_PAGE_WIDTH}px`,
            minHeight: `${PREVIEW_PAGE_HEIGHT}px`,
            transform: `scale(${previewScale})`,
          }}
        >
          <TemplateComponent data={data} />
        </div>
      </div>
    </div>
  );
}
