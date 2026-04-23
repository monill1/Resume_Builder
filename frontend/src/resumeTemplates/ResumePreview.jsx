import { useLayoutEffect, useRef, useState } from "react";
import { buildResumeViewModel } from "./helpers";
import { DEFAULT_TEMPLATE_ID } from "./templateMeta";
import { buildThemePalette } from "./themePalette";
import ClassicProfessional from "./templates/ClassicProfessional";
import ContemporaryAccent from "./templates/ContemporaryAccent";
import ExecutiveElegance from "./templates/ExecutiveElegance";
import ProfileBanner from "./templates/ProfileBanner";

const PREVIEW_PAGE_WIDTH = 816;
const PREVIEW_PAGE_HEIGHT = 1056;

const TEMPLATE_COMPONENTS = {
  "classic-professional": ClassicProfessional,
  "contemporary-accent": ContemporaryAccent,
  "executive-elegance": ExecutiveElegance,
  "profile-banner": ProfileBanner,
};

export default function ResumePreview({ resume, selectedTemplate, sectionColor }) {
  const previewStageRef = useRef(null);
  const sheetRef = useRef(null);
  const [previewScale, setPreviewScale] = useState(1);
  const [sheetHeight, setSheetHeight] = useState(PREVIEW_PAGE_HEIGHT);

  const templateId = TEMPLATE_COMPONENTS[selectedTemplate] ? selectedTemplate : DEFAULT_TEMPLATE_ID;
  const TemplateComponent = TEMPLATE_COMPONENTS[templateId];
  const data = buildResumeViewModel(resume);
  const palette = buildThemePalette(sectionColor);

  useLayoutEffect(() => {
    if (!previewStageRef.current || !sheetRef.current) return undefined;

    let frameId = 0;

    const measure = () => {
      const stageWidth = previewStageRef.current?.clientWidth || PREVIEW_PAGE_WIDTH;
      const nextScale = Math.min(stageWidth / PREVIEW_PAGE_WIDTH, 1);
      const nextHeight = Math.max(sheetRef.current?.scrollHeight || PREVIEW_PAGE_HEIGHT, PREVIEW_PAGE_HEIGHT);
      setPreviewScale((currentScale) => (currentScale === nextScale ? currentScale : nextScale));
      setSheetHeight((currentHeight) => (currentHeight === nextHeight ? currentHeight : nextHeight));
    };

    const rafMeasure = () => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(measure);
    };

    measure();

    const stageObserver = new ResizeObserver(() => rafMeasure());
    const sheetObserver = new ResizeObserver(() => rafMeasure());
    stageObserver.observe(previewStageRef.current);
    sheetObserver.observe(sheetRef.current);

    return () => {
      window.cancelAnimationFrame(frameId);
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
            "--template-section-color": sectionColor,
            "--template-accent": palette.accent,
            "--template-accent-deep": palette.accentDeep,
            "--template-accent-ink": palette.accentInk,
            "--template-accent-soft": palette.accentSoft,
            "--template-accent-surface": palette.accentSurface,
            "--template-accent-surface-strong": palette.accentSurfaceStrong,
            "--template-accent-line": palette.accentLine,
            "--template-accent-border": palette.accentBorder,
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
