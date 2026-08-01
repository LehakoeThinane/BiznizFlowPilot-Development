import { Extension } from "@tiptap/core";

/** Paragraph/heading indent level, rendered as margin-left - TipTap has no
 * bundled extension for this (only list-item nesting, via sinkListItem/
 * liftListItem, which StarterKit already provides). Mirrors the common
 * community pattern: an attribute on block nodes rendered as inline style,
 * bounded so it can never produce runaway/negative margins. */

const MIN_LEVEL = 0;
const MAX_LEVEL = 8;
const STEP_EM = 1.5;

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    indent: {
      indent: () => ReturnType;
      outdent: () => ReturnType;
    };
  }
}

export const Indent = Extension.create({
  name: "indent",

  addOptions() {
    return { types: ["paragraph", "heading"] };
  },

  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          indent: {
            default: 0,
            renderHTML: (attributes: { indent?: number }) => {
              if (!attributes.indent) return {};
              return { style: `margin-left: ${attributes.indent * STEP_EM}em` };
            },
            parseHTML: (element: HTMLElement) => {
              const margin = parseFloat(element.style.marginLeft || "0");
              return margin > 0 ? Math.round(margin / STEP_EM) : 0;
            },
          },
        },
      },
    ];
  },

  addCommands() {
    return {
      indent:
        () =>
        ({ tr, state, dispatch }) => {
          let changed = false;
          state.doc.nodesBetween(state.selection.from, state.selection.to, (node, pos) => {
            if (this.options.types.includes(node.type.name)) {
              const current = (node.attrs.indent as number) ?? 0;
              if (current < MAX_LEVEL) {
                if (dispatch) tr.setNodeMarkup(pos, undefined, { ...node.attrs, indent: current + 1 });
                changed = true;
              }
            }
          });
          return changed;
        },
      outdent:
        () =>
        ({ tr, state, dispatch }) => {
          let changed = false;
          state.doc.nodesBetween(state.selection.from, state.selection.to, (node, pos) => {
            if (this.options.types.includes(node.type.name)) {
              const current = (node.attrs.indent as number) ?? 0;
              if (current > MIN_LEVEL) {
                if (dispatch) tr.setNodeMarkup(pos, undefined, { ...node.attrs, indent: current - 1 });
                changed = true;
              }
            }
          });
          return changed;
        },
    };
  },
});
