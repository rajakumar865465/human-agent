# Safe Permission Policy

The Supervisor Agent can approve safe permission prompts automatically.

## Safe Examples

- Read project files
- Edit files inside project workspace
- Install normal project dependencies
- Run build command
- Run test command
- Start local development server
- Open browser for testing

## Safe Command Prefixes

These commands may be auto-approved when they match the configured allowlist:

- `npm install`
- `npm run build`
- `npm run dev`
- `npm test`
- `python`
- `pytest`
- `playwright`

## Risky Examples That Need Human Approval

- Delete files outside project workspace
- Access private SSH keys
- Access cloud credentials
- Upload secrets
- Run destructive system commands
- Format disk
- Remove user folders
- Disable security tools

## Blocked Command Patterns

The supervisor must refuse commands that match these patterns:

- `rm -rf`
- `del /s`
- `Remove-Item -Recurse`
- `shutdown`
- `format`
- `delete system`
- `private key`
- `secret`

## Rule

The agent must never blindly approve risky permissions.
If a prompt or command is uncertain, the safe default is human review.
