# NovelVerse 📚

A full-featured web fiction platform built with Flask, SQLite, and Jinja2.
Inspired by RoyalRoad & ScribbleHub.

## Quick Start

```bash
pip install flask
python app.py
```
Open http://localhost:5000

## Demo Accounts
- **Author:** `stormwriter` / `password123`
- **Reader:** `avid_reader` / `password123`

## Features

### Reader Features
- Browse & search novels with genre/status/sort filters
- Follow novels → personal reading list with progress tracking
- Star ratings + written reviews per novel
- Comments on novels and individual chapters
- AI-powered recommendations based on reading history
- Reading progress saves automatically
- Adjustable font size while reading
- Drop-cap styled chapter reader with reading progress bar

### Author Features
- Create & manage multiple novels
- Rich chapter editor with formatting helpers
- Publish/draft toggle per chapter
- Analytics dashboard:
  - Views over time (30-day chart)
  - Per-chapter view breakdown
  - Rating distribution chart
  - Word count per chapter
- Author notes per chapter

### AI Features (requires Anthropic API key in environment)
- **Continue Story** — AI continues the narrative from your last paragraph
- **Improve Prose** — Rewrites selection for better flow and style
- **Enhance Dialogue** — Makes conversations feel more natural
- **Brainstorm Ideas** — Suggests 5 plot directions
- **Summarize Chapter** — Generates a synopsis

## Stack
- **Backend:** Python / Flask
- **Database:** SQLite (structured schema with indexes)
- **Security:** PBKDF2-SHA256 password hashing, Flask sessions
- **Frontend:** HTML + CSS + Vanilla JS + Jinja2
- **AI:** Anthropic Claude API (writing assistant + recommendations)
- **Charts:** Chart.js (analytics dashboard)

## Project Structure
```
novelverse/
├── app.py              # Routes + API endpoints
├── database.py         # Schema + DB connection
├── utils/
│   ├── auth.py         # Password hashing, decorators
│   └── helpers.py      # Filters (time_ago, word_count, paginate)
├── static/
│   ├── css/main.css    # Full design system
│   └── js/main.js      # Interactive features + Chart.js analytics
└── templates/
    ├── base.html
    ├── home.html
    ├── browse.html
    ├── search.html
    ├── auth/           # login, register
    ├── novel/          # detail, create, edit
    ├── chapter/        # read, editor
    ├── user/           # profile, settings, reading_list
    ├── dashboard/      # author, manage_novel
    ├── author/         # become_author
    └── errors/         # 404, 403, 500
```
