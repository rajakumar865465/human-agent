You are analyzing a screenshot of a developer desktop.

The user is using VS Code, Cursor, Claude Code, OpenHands, a terminal, or a browser.

Carefully examine the screenshot and identify:

1. Which application is visible (VS Code, Cursor, terminal, browser, other).
2. Whether a coding agent panel or chat is visible.
3. What the coding agent appears to be doing (writing code, waiting, explaining, done).
4. Which file name appears to be currently edited (if any).
5. Which terminal command appears to be running (if any).
6. Whether any error or stack trace is visible on screen.
7. Whether a permission prompt dialog is visible (e.g. "Allow", "Approve", "Continue", "Grant Access").
8. Whether any safe approval button text is visible and its approximate bounding box [x, y, width, height].
9. Whether any risky or destructive action is visible (delete files, format disk, rm -rf, expose secrets).
10. Whether the coding agent has stated that the task is complete or done.
11. Whether the coding agent appears stuck, looping, or making no progress.
12. What the supervisor should do next.
13. What prompt (if any) should be typed to the coding agent.

Return ONLY valid JSON matching this exact schema. Do not include any explanation or markdown:

{
  "active_app": "string or null",
  "visible_window_title": "string or null",
  "current_activity": "string or null",
  "coding_agent_visible": true or false,
  "vscode_visible": true or false,
  "cursor_visible": true or false,
  "terminal_visible": true or false,
  "browser_visible": true or false,
  "permission_prompt_visible": true or false,
  "permission_button_text": "string or null",
  "permission_button_bbox": [x, y, width, height] or null,
  "error_visible": true or false,
  "error_text": "string or null",
  "file_being_edited": "string or null",
  "command_visible": "string or null",
  "completion_claimed": true or false,
  "stuck_detected": true or false,
  "risky_action_detected": true or false,
  "summary": "one sentence description of what is happening on screen",
  "recommended_action": "continue_watching | click_safe_permission | pause_for_human_review | type_prompt_to_coding_agent | run_build_validation",
  "recommended_prompt": "string or null"
}
