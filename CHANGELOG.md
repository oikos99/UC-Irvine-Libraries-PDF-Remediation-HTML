# Changelog

## v11

- Remove the top padding from the main converter `<h1>` heading while retaining the safer page-level top spacing that prevents logo clipping.

## v10

- Rename the interface to **UC Irvine Libraries PDF-to-HTML Accessibility Converter (Ver. 2)**.
- Add safer top spacing below the Streamlit toolbar so the header logo is not clipped.
- Render the header logo with `object-fit: contain` so the complete logo remains visible.

## v9

- Render both panel captions in a shared Streamlit caption row below the side-by-side components so their baselines align horizontally.

## v7

- Display **Preview HTML** to the left of **Edit HTML source**.
- Open each page in rendered HTML preview mode by default.
- Remove the embedded-image-token count notice above the compact editor.

## v6

- Render the page-preview caption directly in Streamlit below the compact editor component.
- Remove the duplicate caption from inside the custom component iframe so it cannot be clipped by component-height calculations.

## v5

- Fixed repeated HTML previews becoming blank after returning to edit mode.
- Preview iframe now receives a fresh Blob URL for every render instead of repeatedly reusing `srcdoc`.
- Protected the editor against transient empty rerender arguments from Streamlit so the hidden source is not accidentally cleared.
- Dynamically reports the component height so the caption below the preview remains visible.
- Restored the caption: `Rendered preview of the current edited HTML for this page.`

## v4

- Added local editor/preview toggle synchronization fixes.

## v3

- Added compact embedded-image tokens represented as protected inline pills.

## v8

- Replaced the static original-page screenshot with an accessible zoomable image panel.
- Added Zoom out, Fit width, and Zoom in controls plus keyboard zoom shortcuts within the focused image panel.
- Matched the original-page and HTML-review panel heights so their lower edges align.
- Centered both panel captions.
