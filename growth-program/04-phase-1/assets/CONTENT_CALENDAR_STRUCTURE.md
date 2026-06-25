# Content Calendar — Tab Structure

**Add this as a new tab in the Empire CRM Google Sheet**  
**Tab Name:** `Content_Calendar`

## Columns

| Column | Type | Purpose | Example |
|--------|------|---------|---------|
| `post_id` | Text | Unique ID | W1-SAT-C1 |
| `week` | Number | Week number (1, 2, 3...) | 1 |
| `day` | Text | Day of the week | Saturday |
| `publish_date` | Date | YYYY-MM-DD | 2026-06-28 |
| `category` | Text | C1-C10 | C1 |
| `topic` | Text | Short topic description | Flap T pronunciation |
| `text_ar` | Text | Arabic post content | (full post text) |
| `text_en` | Text | English translation (if bilingual) | (optional) |
| `cta_type` | Text | soft / medium / hard | soft |
| `cta_target` | Text | quiz / resource / call / how / community | resource |
| `published` | Boolean | TRUE when posted | FALSE |
| `engagement_notes` | Text | Manual: reactions, replies, bot taps | (fill after posting) |
| `bot_taps` | Number | Count of bot starts that day | (fill from report) |

## Category Reference

| Code | Name | Frequency |
|------|------|-----------|
| C1 | Value / micro-lesson | 2x/week |
| C2 | Transformation / success story | 1x/week |
| C3 | Behind-the-scenes / founder | 1x/2 weeks |
| C4 | Social proof / momentum | 1x/2 weeks |
| C5 | Engagement (poll/question) | 1x/week |
| C6 | Offer / promotion | 1x/2 weeks (max) |
| C7 | Problem education | 1x/week |
| C8 | Objection handler | 1x/2 weeks |
| C9 | Word of the day (daily ritual) | Daily |
| C10 | Event / live | 1x/month |

## Weekly Template

| Day | Category | CTA Type |
|-----|----------|----------|
| Saturday | C1 — Value | Soft (resource) |
| Sunday | C5 — Engagement | Soft (poll/reply) |
| Monday | C7 — Problem education | Medium (quiz) |
| Tuesday | C1 — Value | Soft (resource) |
| Wednesday | C2/C4 — Story/proof | Soft (reaction) |
| Thursday | C8/C3 — Objection/founder | Medium (call/quiz) |
| Daily | C9 — Word of the day | Reply CTA |
