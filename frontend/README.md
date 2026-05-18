Frontend Quickstart

This is a minimal Vite + React frontend for the QC Allocation Planner.

Install and run:

```bash
cd frontend
npm install
npm run dev
```

The UI expects the backend API under `/api/*`. When running in development you can set a proxy in `vite.config.js` or run both services behind a reverse proxy.

Notes
- The `GanttPlanner` component is intentionally minimal: it positions tasks by start/end times and uses HTML5 drag events. Replace with a production Gantt library to gain robust drag/resize behavior.
- The `JobsPanel` Auto-Plan button calls `POST /api/schedule/plan` and refreshes the day.
- To enable audit capture, pass the authenticated user's UUID as `actor_id` in plan/replan requests (backend currently reads it from `options`).
