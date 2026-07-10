# Vocabulary Detail Safe-Fidelity Design QA

- Source visual truth: `/tmp/binnagent-vocabulary-design-qa/source-reference.png`
- Desktop implementation: `/tmp/binnagent-vocabulary-design-qa/implementation-desktop.png`
- Mobile source: `/tmp/binnagent-vocabulary-design-qa/source-mobile.png`
- Mobile implementation: `/tmp/binnagent-vocabulary-design-qa/implementation-mobile.png`
- Desktop viewport: 1440 × 900
- Mobile viewport: 390 × 844
- State: `quickly` from `docs/cc.html`, opened in Vocabulary Detail immersive reading

## Full-view comparison evidence

The source HTML and the immersive reader now use the same sanitized embedded stylesheet. The generated card has the same 820px maximum width, 28px radius, padding, shadow, background, typography hierarchy, section spacing, badges, meaning cards, morphology surface, and responsive rules as the source. The product-only immersive reader header remains outside the iframe so exit and keyboard guidance stay available.

At 390px the source and implementation reflow identically inside the content region. The implementation has no horizontal page overflow (`scrollWidth === clientWidth === 390`).

## Focused region comparison evidence

The `.card` computed styles were compared directly in the source and immersive iframe:

| Property | Source | Implementation |
|---|---|---|
| `max-width` | `820px` | `820px` |
| `padding` | `35.2px 40px 44.8px` | `35.2px 40px 44.8px` |
| `border-radius` | `28px` | `28px` |
| `box-shadow` | two-layer source shadow | same two-layer shadow |
| `background` | `rgb(255, 255, 255)` | `rgb(255, 255, 255)` |

## Findings

No actionable P0, P1, or P2 visual differences remain.

- Typography: source font stack, weights, sizes, line height, wrapping, and hierarchy are preserved by the embedded stylesheet.
- Spacing and layout: card proportions, padding, section rhythm, chip wrapping, radii, borders, and shadows match the source.
- Colors and tokens: the source palette and surface colors render unchanged inside the isolated iframe.
- Image quality: the target contains no raster image assets; visible pictographs are content glyphs from the supplied HTML and are preserved rather than recreated.
- Copy and content: the source HTML content is unchanged after safe rendering.
- Interaction and accessibility: the system retains the titled iframe, modal semantics, visible exit action, Escape guidance, focus trap, and reduced-motion override.
- Security: scripts, nested frames, forms, external links/resources, unsafe inline styles, and network-backed CSS are removed or rejected; CSP denies network connections and resource loading.
- Console: no errors or warnings were observed in the verified state.

## Comparison history

1. Before the fix, the source `<head><style>` was discarded and the content was rendered with a generic 487-character reader stylesheet. This was a P1 fidelity and readability mismatch.
2. The fix preserves safe self-contained CSS, injects a network-denying CSP, sanitizes inline styles, retains sandbox isolation, and falls back to the system theme only when no safe embedded style is available.
3. Post-fix desktop and mobile captures match the source content region; the earlier P1 is resolved.

## Follow-up polish

The immersive reader header intentionally reduces the available vertical viewport compared with the standalone reference. This is acceptable product chrome because it provides a reliable exit and does not alter the HTML content region.

final result: passed
