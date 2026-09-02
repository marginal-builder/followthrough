# FollowThrough – MVP Scope

**A lightweight team tool for weekly feedback + retrospectives.**

**Date:** 2026-09-02  
**Status:** Scoped MVP

---

## Goal

A lightweight team tool for weekly feedback + retrospectives.  
All team members can contribute. Feedback is discussed, actions and decisions are captured, and follow-through is tracked.

---

## Core Framework

**Start / Stop / Continue**

- **Start** – Things we should begin doing  
- **Stop** – Things that are not working / should stop  
- **Continue** – Things that are working well  

---

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Who can contribute | All team members | Not limited to project owners |
| Feedback scope | Team-wide | Simpler than per-project boards |
| Attribution | Attributed by default + optional “Submit anonymously” checkbox | Balance of accountability and psychological safety |
| Board style | Notion / Airtable-style | Familiar, flexible, easy to scan |
| Retrospective support | Shared view of feedback + action/decision capture | Supports live discussion |
| Recording | Upload audio, video, or paste transcript (no built-in recording) | Keeps MVP simple |
| Processing | Auto-transcribe (if needed) + extract Actions & Decisions | Reduces manual note-taking |
| Actions | Trackable items (Owner + Status + optional Due date) | Creates real follow-through |
| Decisions | Stored as a clean list linked to the week | Easy reference |
| Voting / prioritization | Not in MVP | Keeps the board clean; discussion happens live |
| Weekly board creation | Manual “Create this week’s board” button | Simple and reliable |
| Permissions | Everyone can add & view; light control on editing actions | Matches open contribution model |
| AI extraction | Auto-extract + always editable by humans | Good enough accuracy + human control |
| History | Past weeks archived and still viewable | Useful for looking back |

---

## MVP Feature List

### 1. Weekly Board
- Create a new weekly board manually
- Team-wide Start / Stop / Continue columns (or sections)
- Anyone can add an item
- Default attribution + anonymous checkbox
- Clean shared view for discussion

### 2. Retrospective Support
- View all submitted feedback in one place
- Discuss live
- Capture actions and decisions during/after the meeting

### 3. Meeting Processing
- Upload audio or video **or** paste a transcript
- System transcribes if needed
- Extracts:
  - **Actions** → become trackable items (Owner, Status, optional Due date)
  - **Decisions** → stored as a simple list for that week
- All extractions are editable

### 4. Action Tracking
- Actions appear on the board (or linked section)
- Fields: Owner, Status (e.g. To Do / In Progress / Done), optional Due date
- Basic ability to update status and owner

### 5. History
- Previous weeks remain accessible
- Can review past feedback, actions, and decisions

---

## Explicitly Out of Scope for MVP

- Built-in meeting recording
- Automatic weekly board creation / scheduling
- Voting or prioritization of feedback items
- Complex role / permission system
- Per-project boards
- Integrations with Zoom / Google Meet / Teams (beyond file upload)
- Advanced analytics or reporting
- Mobile-native app

---

## Suggested User Flow (High Level)

1. Someone creates “Week of [Date]” board  
2. Team members add Start / Stop / Continue items throughout the week (or just before the meeting)  
3. Team holds retrospective using the board  
4. After the meeting, someone uploads recording or pastes transcript  
5. System extracts Actions & Decisions  
6. Team reviews / edits the extracted items  
7. Actions are assigned and tracked  
8. Board is archived when the next week starts  

---

## Next Possible Steps (after MVP)

- Voting on feedback items  
- Built-in or integrated recording  
- Auto-create weekly boards  
- Slack / Teams notifications  
- Deeper action follow-up reminders  
- Per-project filtering or views  

---

*This document captures the full scoping discussion and final MVP decisions.*
