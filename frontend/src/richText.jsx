const BOLD_PATTERN = /\*\*(.+?)\*\*/gs;

export function renderRichText(value) {
  const text = String(value || "");
  const parts = [];
  let lastIndex = 0;
  let matchIndex = 0;

  for (const match of text.matchAll(BOLD_PATTERN)) {
    const start = match.index ?? 0;
    const end = start + match[0].length;

    if (start > lastIndex) {
      parts.push(text.slice(lastIndex, start));
    }

    parts.push(<strong key={`rich-text-bold-${matchIndex}`}>{match[1]}</strong>);

    lastIndex = end;
    matchIndex += 1;
  }

  if (!parts.length) {
    return text;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

export function stripRichText(value) {
  return String(value || "").replace(BOLD_PATTERN, "$1");
}
