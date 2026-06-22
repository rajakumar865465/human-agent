# Project Requirements

This is a concrete sample target app for the supervisor loop.

Replace these details with your real app when you are ready to test another project.

## Project Name

TaskFlow Lite

## Target App Summary

- What is being built: A lightweight task management web app
- Who it is for: Solo users and small teams
- Primary user value: Track tasks, log in securely, and update account settings from a simple dashboard

## Goal

Build a web app that supports user signup, login, dashboard access, and settings updates with a reliable API and a clean browser experience.

## Tech Stack

- Frontend: React
- Backend: FastAPI
- Database: SQLite
- Authentication: Email and password with session-based auth
- Deployment: Local development first, then containerized deployment
- Test runner: Pytest
- Browser automation: Playwright

## Scope

### In Scope
- Home page
- Signup page
- Login page
- Dashboard page
- Settings page
- Authenticated API endpoints
- Browser smoke tests and form flow tests

### Out of Scope
- Payments
- Team invites
- Notifications
- Mobile app support

## Required Pages

- Home page
- Signup page
- Login page
- Dashboard
- Settings page

## Required Features

- User registration
- User login and logout
- Protected dashboard access
- Dashboard primary action button
- Settings update form

## Data and API Expectations

- Main entities: User, Task
- Required API base path: `/api`
- Auth session or token approach: Session cookies
- Persistent data that must survive reloads: User profile and task records

## User Flows to Test

### Flow 1: Signup

1. Open the signup page
2. Enter valid user details
3. Submit the signup form
4. Verify the dashboard opens

### Flow 2: Login

1. Open the login page
2. Enter valid credentials
3. Submit the login form
4. Verify the user dashboard appears

### Flow 3: Dashboard Primary Action

1. Open the dashboard
2. Click the primary action button
3. Verify a task is created or the expected success state appears

### Flow 4: Settings Update

1. Open the settings page
2. Change one editable setting
3. Save the change
4. Verify the update persists after refresh

## API Endpoints to Test

- `GET /health`
- `POST /api/signup`
- `POST /api/login`
- `GET /api/me`
- `PUT /api/settings`

## Build and Run Commands

- Install dependencies: `npm install`
- Build command: `npm run build`
- Dev server command: `npm run dev`
- Test command: `npm test`

## Acceptance Criteria

- App builds successfully
- App runs locally
- Main pages load
- Signup and login work
- Dashboard primary action works
- Settings updates persist
- No critical console errors
- No critical network errors
- APIs return expected results

## Notes for the Supervisor

- Use the sample endpoints as defaults when wiring tests
- Replace these values if the target app changes
- Keep screenshots for any failed flow

