# Demo App Requirements

## Project Name

TaskFlow Lite Demo

## Goal

Provide a small FastAPI app with a home page, login page, dashboard, settings page, and API endpoints that can be exercised by the supervisor loop.

## Tech Stack

- Frontend: HTML
- Backend: FastAPI
- Database: None
- Authentication: Demo form submission
- Deployment: Local development only

## Required Pages

- Home page
- Login page
- Dashboard page
- Settings page

## Required Features

- Home navigation buttons
- Login form
- Dashboard action buttons
- Settings form
- Health endpoint
- API endpoints for login, signup, me, and settings

## User Flows to Test

### Flow 1: Login

1. Open the login page
2. Enter credentials
3. Submit the form
4. Verify the dashboard opens

### Flow 2: Dashboard Action

1. Open the dashboard page
2. Click the main action button
3. Verify the success message appears

### Flow 3: Settings

1. Open the settings page
2. Change the display name
3. Save the form
4. Verify the page responds successfully

## API Endpoints to Test

- GET /health
- GET /api/health
- POST /api/login
- POST /api/signup
- GET /api/me
- PUT /api/settings

## Acceptance Criteria

- Demo app starts locally on port 3000
- Pages load successfully
- Buttons work
- Forms submit
- API endpoints return JSON responses
- No critical console errors
