# ResearchPilot AI Design System

> **Status:** Specification Frozen
> **Version:** 1.0.0
> **Last Updated:** 2026-09-16
> **Owner:** ResearchPilot AI Project

---

## 1. Design Philosophy

The visual direction for ResearchPilot AI is **"Sage Intelligence"**.

The product should feel:
- Clean, minimal, professional, premium, sophisticated, calm, trustworthy, intelligent, research-oriented, modern, and technically credible.
- It must feel like a **premium research workstation** combined with an **editorial research platform** and a **modern professional SaaS product**.

The design should NOT feel:
- Flashy, gaming-oriented, cyberpunk, overly futuristic, neon, childish, overly colorful, generic "AI SaaS", crypto/web3-like, or overly glassmorphic.

**Core Principle: Evidence over decoration.**
The interface should make it easy for the user to understand:
- What did ResearchPilot find?
- Where did it find it?
- Why is the source relevant?
- Which claims are verified?
- What is uncertain?
- What is the final conclusion?

The design must reinforce trust and transparency.

---

## 2. Brand Direction

Follow approximately this visual balance:
- **70–80%** Background + White Surfaces
- **15–20%** Text + Neutral Elements
- **5–10%** Sage / Gold / Semantic Accents

The product should feel **neutral first and branded second**.

---

## 3. Color System

These colors are the APPROVED source of truth. Do not use older themes or palettes.

### Primary Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-bg-primary` | `#F7F8F4` | Primary application/page background |
| `--color-bg-surface` | `#FFFFFF` | Cards, panels, inputs, modals, report containers, elevated UI sections |

### Text Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-text-primary` | `#172019` | Headings, primary body text, important information, navigation |
| `--color-text-secondary` | `#687169` | Descriptions, metadata, secondary labels, supporting text |

### Border Color

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-border` | `#DEE3DE` | Card borders, dividers, input borders, table separators |

### Brand Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-brand-sage` | `#356B52` | Primary brand/accent color. Use intentionally for primary CTA, active navigation, links, selected states, progress indicators, important interactive elements, focus states where appropriate. Do NOT use as a large background. |
| `--color-accent-light` | `#E5F0E9` | Light accent for selected backgrounds, subtle information panels, active navigation backgrounds, success-like neutral highlights, source/category indicators, hover states. |
| `--color-accent-gold` | `#9A7B45` | Muted gold secondary accent. Use very sparingly for premium/highlight indicators, important research metadata, special status, subtle visual emphasis. Do NOT use for normal buttons. |

### Semantic Colors

Keep semantic colors muted and professional. Avoid highly saturated neon status colors.

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-success` | `#287A55` | Success states, verified claims |
| `--color-warning` | `#A66A00` | Warnings, flagged items, unverified claims |
| `--color-error` | `#B54747` | Error states, failures, contradicted claims |
| `--color-info` | `#4F7190` | Information, neutral progress |

---

## 4. Typography

Typography should communicate Hierarchy, Clarity, Readability, and Authority. Avoid excessive font weights, decorative typography, or excessive uppercase text.

### Font Families

| Role | Font Family | Source | Usage |
|------|-------------|--------|-------|
| **Primary UI Font** | `Inter` | Google Fonts | Navigation, buttons, forms, body text, dashboard, settings, system UI |
| **Research/Editorial** | `Source Serif 4` | Google Fonts | Long-form research/report presentation (use selectively to improve readability) |
| **Technical Font** | `JetBrains Mono` | Google Fonts | Source IDs, citation metadata, technical identifiers, timestamps, code, API information |

### Type Scale (Responsive starting direction)

Define a consistent responsive type scale. Do not treat these values as rigid if responsive design requires adjustment.

| Role | Size |
|------|------|
| `Display` | 48–64px |
| `H1` | 36–44px |
| `H2` | 28–32px |
| `H3` | 20–24px |
| `Body Large` | 17–18px |
| `Body` | 15–16px |
| `Small` | 13–14px |
| `Caption` | 12px |

---

## 5. Spacing

Use a consistent 4px base spacing system. Avoid arbitrary spacing values unless there is a strong design reason.

| Value | Usage Examples |
|-------|----------------|
| `4px`, `8px` | Tight gaps, input padding |
| `12px`, `16px` | Standard padding, grid gaps |
| `20px`, `24px` | Card padding, section spacing |
| `32px`, `40px` | Page margins |
| `48px`, `64px`, `80px`, `96px` | Report spacing, landing page sections |

---

## 6. Layout

- Use grid and flexbox to manage layout.
- Maintain a generous reading width for reports and long-form content.
- Ensure the layout supports complex data (sources, evidence, progress) without feeling cluttered.

---

## 7. Radius

Use restrained rounded corners. The design should feel professional rather than playful. Avoid making every component excessively rounded.

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `6px` | Small elements |
| `--radius-md` | `8px` | Inputs, Buttons |
| `--radius-lg` | `10-12px`| Cards |
| `--radius-xl` | `14-16px`| Large containers |
| `--radius-pill` | `999px` | Pills, tags |

---

## 8. Elevation

Shadows are used very sparingly.
Prefer `border + surface contrast + subtle elevation` over large dramatic shadows.
Cards should be distinguishable through background differences and thin borders rather than floating everything.

---

## 9. Iconography

`TBD — select one consistent icon library during frontend implementation.`

- Must be simple, thin/medium-weight, professional, recognizable, and minimal.
- Avoid decorative 3D icons, overly colorful icons, or inconsistent icon styles.

---

## 10. Components

- **Buttons/Inputs/Cards:** Must follow clear hierarchy, minimal decoration, strong readability, predictable interaction, accessible contrast, consistent spacing, and consistent states.
- **Glassmorphism:** Do NOT use glassmorphism as the default component style. Extreme limited use (e.g., sticky nav) only when it improves UX.
- **Gradients:** Not a core part of visual identity. Subtle use only for marketing/hero accents (no neon, no purple/blue AI gradients, no large gradient backgrounds). The UI should primarily use flat, sophisticated colors.

---

## 11. Research UI

The visual design must prioritize the product's core workflow:
`Question → Plan → Research → Evidence → Verification → Report`

- **Progress:** Avoid generic "Loading..." as the primary progress experience. Use structured progress (e.g., Planning ✓, Web Research ✓, Verification ⟳, Report ○). Do not expose private model chain-of-thought.
- **Activity Feed:** Compact, informative, visually quiet. This should not become a developer console.
- **Source Cards:** Prioritize Source title, Source type, Publisher/author, Publication date, Relevance, Evidence used, Citation reference. Avoid unexplained AI confidence scores.

---

## 12. Report UI

The final report should feel closer to a professional research document than a chatbot response.
- Prioritize excellent typography (Source Serif 4).
- Generous reading width, clear hierarchy, citations, source references, section navigation, readable paragraphs, and tables where appropriate.
- Evidence traceability must be highly visible.

---

## 13. Responsive Design

Designed mobile-first conceptually while prioritizing desktop for the research workspace.

- **Desktop:** Supports Research + Progress + Sources + Activity without becoming visually crowded.
- **Mobile:** Simplifies the workspace into sequential sections: `Query → Progress → Findings → Report → Sources`.

---

## 14. Accessibility

- **Contrast:** Color contrast for all text must be accessible. Do not rely on color alone to communicate status.
- **Keyboard & Screen Readers:** Keyboard navigation, clear focus states, semantic HTML, screen readers support.
- **Other considerations:** Readable font sizes, reduced motion support, accessible forms, error messaging, touch targets.

---

## 15. Motion

Motion should be subtle and purposeful. ResearchPilot is a productivity/research tool; motion should never compete with information.

- **Allowed:** Hover transitions, page transitions, progress transitions, expanding/collapsing sections, loading indicators, subtle status changes.
- **Avoid:** Excessive parallax, floating particles, constant animations, animated gradients, distracting 3D effects.

---

## 16. Design Do's
- Use typography to create hierarchy rather than relying on colors.
- Use whitespace to organize content.
- Keep the UI neutral-first and branded-second.
- Make evidence and traceability a core visual element of the product.

---

## 17. Design Don'ts
- Do not use Sage Green as a large background across the application.
- Do not use Muted Gold for normal buttons or large UI areas.
- Do not use neon colors, large shadows, or complex gradients.
- Do not expose internal AI reasoning/chain-of-thought to the user.
- Do not clutter the dashboard with unnecessary KPI cards simply because dashboards commonly have them.
