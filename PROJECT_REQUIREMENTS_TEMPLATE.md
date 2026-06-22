# Project Requirements Template

Use this file to describe the app that the Supervisor Agent must build and test.

Replace the sample values below with the real project details before running the supervisor loop.

## Project Name

`Your Project Name`

## Target App Summary

- What is being built:
- Who it is for:
- Primary user value:

## Goal

Describe the app in one to three sentences.

Example:

Build a web app that lets users sign up, log in, manage a dashboard, and update settings with a reliable API and a clean UI.

## Tech Stack

- Frontend:
- Backend:
- Database:
- Authentication:
- Deployment:
- Test runner:
- Browser automation:

## Scope

### In Scope
- Core user authentication
- Dashboard experience
- Settings management
- API health and auth checks
- Browser-based UI smoke tests

### Out of Scope
- List anything intentionally not included in this build

## Required Pages

- Home page
- Login page
- Signup page
- Dashboard
- Settings page

## Required Features

- User registration
- User login and logout
- Protected dashboard access
- Editable account settings
- Primary action button on the dashboard

## Data and API Expectations

- Main entities:
- Required API base path:
- Auth session or token approach:
- Persistent data that must survive reloads:

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
3. Verify the expected result appears

### Flow 4: Settings Update

1. Open the settings page
2. Change one editable setting
3. Save the change
4. Verify the update persists

## API Endpoints to Test

- `GET /health`
- `POST /api/login`
- `POST /api/signup`
- `GET /api/me`
- `PUT /api/settings`

## Build and Run Commands

- Install dependencies:
- Build command:
- Dev server command:
- Test command:

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

- List any known edge cases
- List any required environment variables
- List any manual checks that should still be performed
