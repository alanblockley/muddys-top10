# Changelog

All notable changes to the Muddy's Top 10 system.

Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased] — 2026-08-06

### Added

- **Campaign Status Workflow**: Campaigns now progress through `draft → reviewed → approved → published` states with dedicated action buttons in the admin UI.
- **Resources Feature**: New admin tab for uploading and managing station resources (opus/mp3/pdf files). Supports categories: Jingle, Sting, Ad, Read, Promo, Imaging, Other. Each resource has a description and metadata.
- **Resources API**: `GET /api/resources` (public), `POST /api/resources` (admin, authenticated), `DELETE /api/resources/{id}` (admin, authenticated).
- **Resources on Landing Page**: Public landing page displays resources grouped by category in a two-column responsive grid.
- **PNG Download Link**: Public page now includes a direct download link for the chart infographic PNG.
- **SAM Template**: Added `resources/*` S3 permissions and API Gateway routes for the resources endpoints.

### Changed

- **Public Page**: Now only displays PUBLISHED campaigns (previously showed approved or published).
- **Public Page Redesign**: Landing page redesigned to match admin purple/gold/navy theme.
- **"Campaign" Wording Removed**: All public-facing pages no longer use the word "campaign" — it is now an internal-only term.
- **Feedback UI**: Feedback sections in admin are now collapsible using `<details>`/`<summary>` elements.
- **Infographic Stats Strip**: Merged from 3 panels to 2 panels (Chart Story + This Week's Stats).
