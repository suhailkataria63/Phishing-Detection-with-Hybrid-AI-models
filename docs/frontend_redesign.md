# Frontend Redesign

## 1) Redesign Goals
- Transform the UI into a modern security-analyst console while preserving all existing detection functionality.
- Keep URL, email, and joint detection flows intact.
- Add a structured batch-analysis workspace and case-detail investigative view.

## 2) Design System Decisions
- Dark, professional dashboard palette with restrained cyan accent.
- Consistent card surfaces, thin borders, and soft depth/shadow.
- Strong typography hierarchy and compact analyst-friendly spacing.
- Color semantics:
- red/orange for risky signals
- amber for review states
- green for benign confidence
- cyan for neutral controls/navigation

## 3) Major UI Sections
- Detection Workspace:
- left panel for mode/config/input
- right panel for summary, score breakdown, explanation, recommendation
- Batch Analysis Workspace:
- CSV upload and controls (mode, operating profile, strategy, threshold override)
- sortable/filterable results table
- case detail drawer with input evidence and reasoning metadata

## 4) Key Reusable Components
- `components/dashboard/ModeSelector.tsx`
- `components/dashboard/DetectionForm.tsx`
- `components/dashboard/SummaryCard.tsx`
- `components/dashboard/SignalBreakdownCard.tsx`
- `components/dashboard/ExplanationCard.tsx`
- `components/dashboard/RecommendationCard.tsx`
- `components/batch/BatchUploadPanel.tsx`
- `components/batch/BatchResultsTable.tsx`
- `components/batch/CaseDetailDrawer.tsx`
- `components/shared/RiskBadge.tsx`
- `components/shared/ScoreBar.tsx`
- `components/shared/SectionCard.tsx`

## 5) New Dependencies
- None required. Redesign uses existing Next.js + React + Tailwind setup.

## 6) Workflow Mapping
- URL Detection:
- frontend normalizes URL and calls `/detect/url`
- Email Detection:
- frontend sends subject/body/sender + operating mode to `/detect/email`
- Joint Detection:
- frontend sends subject/body/sender/manual URLs + operating mode + strategy to `/detect/joint`
- Batch Analysis:
- frontend parses CSV client-side and runs row-level requests against existing APIs
- supports URL/email/joint modes with consistent recommendation formatting

## 7) Notes
- Long explanation payloads now wrap safely in cards (`whitespace-pre-wrap` + `break-all`) to avoid column overflow.
- URL mode still supports Enter-to-analyze behavior.
