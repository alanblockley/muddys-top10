# Muddy's Top 10 — Admin User Guide

This guide covers everything you need to manage the Muddy's Top 10 system: viewing campaigns, adjusting settings, and providing feedback that shapes future content.

---

## Public Welcome Page

Opening the site's root CloudFront URL, such as `https://d1234abcdef.cloudfront.net/`, shows the latest published chart PNG for Muddy's Top 10. This page is public and does not require sign-in.

The public page also includes:
- A direct **PNG download link** for the current chart image
- A **Resources** section showing station resources (audio files, PDFs) grouped by category in a two-column responsive grid

> **Note:** Only campaigns with **Published** status appear on the public page. Draft, reviewed, and approved campaigns are only visible in the admin panel.

## Accessing the Admin Panel

1. Open your site's CloudFront URL and add `/admin.html` to the end (e.g. `https://d1234abcdef.cloudfront.net/admin.html`).
2. Sign in with your username and password (provided by whoever set up your account).
3. Once logged in, you'll see the navigation bar across the top:

| History | Campaigns | Resources | Settings | Raw Data | Spotify |
|---------|-----------|-----------|----------|----------|---------|

- **History** — recent tracks detected from the stream
- **Campaigns** — weekly promotional content (radio reads, social posts, infographics)
- **Resources** — upload and manage station resources (jingles, stings, ads, etc.)
- **Settings** — chart schedule, filters, branding, and validation options
- **Raw Data** — low-level track data for troubleshooting
- **Spotify** — Spotify integration management

---

## Campaigns

The Campaigns tab shows all generated weekly campaign drafts.

**Viewing a campaign:**

1. Click any campaign in the list.
2. A split view opens:
   - **Left side** — the infographic image
   - **Right side** — content tabs

**Content tabs:**

| Tab | What's inside |
|-----|---------------|
| Radio Reads | Broadcast-ready scripts for on-air use |
| Social Posts | Ready-to-post social media content |
| Details | Technical info (generation date, model used, chart data) |

**Regenerate button:**
Click **Regenerate** to create a new revision of the campaign. The system remembers any feedback you've given (see Feedback System below) and uses it to improve the new version.

**Quick feedback:**
While viewing a campaign, use the thumbs up/down buttons on the infographic. Your response is saved and used to guide future generations.

### Campaign Status Workflow

Each campaign progresses through a defined workflow:

```
Draft → Reviewed → Approved → Published
```

| Status | Meaning |
|--------|---------|
| **Draft** | Freshly generated, not yet reviewed |
| **Reviewed** | Reviewer has seen it and provided feedback |
| **Approved** | Content signed off, ready for publication |
| **Published** | Live on the public page |

Action buttons appear at the top of the campaign view to advance the status. Only **Published** campaigns appear on the public-facing page.

---

## Generating a Campaign

1. Go to the **Campaigns** tab.
2. Select the chart week you want to generate content for.
3. Choose which sections to include:
   - **Radio** — on-air read scripts
   - **Infographic** — the visual chart image
   - **Social** — social media posts
4. Click **Generate Draft**.

**What happens behind the scenes:**

1. The system calculates this week's chart data (Top 10 rankings, movement, play counts).
2. Claude writes the editorial content (radio reads, social posts, chart commentary).
3. The infographic is rendered as a PNG image.
4. Everything is saved and appears in the campaign list.

You'll see animated dots while generation is in progress. This typically takes 30–60 seconds.

---

## Resources

The Resources tab lets you upload and manage station assets — jingles, stings, ads, radio reads, promos, imaging elements, and other files.

### Uploading a Resource

1. Go to the **Resources** tab.
2. Click **Upload Resource**.
3. Choose a file (supported formats: `.opus`, `.mp3`, `.pdf`).
4. Select a **category**:
   - Jingle
   - Sting
   - Ad
   - Read
   - Promo
   - Imaging
   - Other
5. Add a **description** (optional but recommended).
6. Click **Upload**.

### Managing Resources

- Resources are listed with their category, filename, and description.
- Click the **delete** button to remove a resource.
- Resources are stored in S3 under the `resources/` prefix and metadata is kept in the Config table.

### Public Display

Uploaded resources appear on the public landing page, grouped by category in a two-column responsive grid. Visitors can browse and access station resources without signing in.

---

## Settings

The Settings tab has four sub-tabs.

### Schedule

Controls when chart weeks start and when campaigns are automatically created.

- **Chart Reset** — pick the day and hour when a new chart week begins. Times are in SLT (stream local time).
- **Campaign Generation** — pick the day and hour when campaigns are automatically generated each week.
- **Auto-generate toggle** — turn automatic campaign generation on or off.
- **Freeze toggle** — when enabled, prevents the chart from resetting (useful during holidays or special events).

### Filters

Keeps unwanted items out of the Top 10 (like station IDs, DJ announcements, or promotional messages).

- Each line is a pattern that matches track names to exclude.
- Patterns use regular expressions, but common ones are pre-filled for you.
- Example: a pattern like `^Muddy's Music Cafe` excludes any track starting with "Muddy's Music Cafe".

### Branding

Customise how your infographic looks.

- **Logo** — upload a PNG, JPEG, or WebP image. It will be resized to 512×512 pixels.
- **Chart Title** — the heading shown on the infographic (e.g. "Muddy's Top 10").
- **Tagline** — a subtitle or slogan shown below the title.
- **Colour scheme** — five colour pickers:
  - Primary
  - Secondary
  - Accent
  - Background
  - Text

These colours are applied the next time you generate an infographic. They don't change previously generated images.

### Validation

Controls how the system cleans up track names detected from the stream.

- **MusicBrainz** — toggle on/off. Checks track names against the MusicBrainz music database to fix typos and standardise formatting.
- **Spotify** — toggle on/off. Does the same using Spotify's catalogue (requires Spotify credentials to be configured).

When both are enabled, the system checks MusicBrainz first, then Spotify as a fallback.

---

## Feedback System

The system learns from your feedback over time.

Feedback sections are **collapsible** — click the disclosure triangle to expand or collapse feedback history on a campaign.

**How to give feedback:**

1. Open any campaign from the list.
2. If something isn't right — tone, wording, style, layout choices — click the **thumbs down** button.
3. Add a comment explaining what you'd like changed (e.g. "Too formal — make it fun and casual" or "Don't mention track positions, just the song names").
4. Submit.

**What happens with your feedback:**

- It's stored in the system's memory.
- The next time you generate or regenerate a campaign, Claude reads your past feedback and adjusts accordingly.
- Over time, the output aligns more closely with your preferences without you needing to repeat yourself.

Use **thumbs up** when you're happy with a result — this reinforces what's working well.

---

## Infographic

Each campaign includes a generated infographic image.

**Specifications:**
- Size: 1280 × 720 pixels (landscape, suitable for social media)
- Format: PNG

**What's on it:**
- Chart table showing all 10 tracks with rankings and movement arrows
- Chart Talk — 6 editorial commentary boxes highlighting notable movers and trends
- Stats strip — 2 panels: Chart Story (narrative) and This Week's Stats (new entries, climbers, fallers, non-movers)
- Footer with branding

**Downloading:**
From the campaign view, click the download button beneath the infographic preview to save the PNG to your computer.

**Customisation:**
The overall layout and design are fixed, but the colours used come from your **Settings → Branding** colour scheme. Update those colours and regenerate to see the change.
