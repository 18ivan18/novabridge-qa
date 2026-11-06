export type AnswerPart = { kind: "text"; text: string } | { kind: "citation"; id: number };

/**
 * Split an answer into paragraphs of text and citations.
 *
 * The server has already checked the citations, so `sourceIds` is a safety net: a number with no
 * source stays plain text rather than becoming a link that leads nowhere.
 */
export function parseAnswer(text: string, sourceIds: ReadonlySet<number>): AnswerPart[][] {
  return text
    .split(/\n{2,}/)
    .filter((paragraph) => paragraph.trim())
    .map((paragraph) => {
      const parts: AnswerPart[] = [];
      // split() with a capture group puts each matched number at the odd positions.
      paragraph.split(/\[(\d+)\]/).forEach((piece, index) => {
        const id = Number(piece);
        if (index % 2 === 0) {
          if (piece) parts.push({ kind: "text", text: piece });
        } else if (sourceIds.has(id)) {
          parts.push({ kind: "citation", id });
        } else {
          parts.push({ kind: "text", text: `[${piece}]` });
        }
      });
      return parts;
    });
}
