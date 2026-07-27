# Security policy

## Supported version

Until the first tagged release, only the current `main` branch receives security fixes. The project
is provisional and is not an operating-system sandbox.

## Report a vulnerability

Use GitHub's private vulnerability reporting form from this repository's **Security** tab. Do not
put exploit details, credentials, private paths, protected data, or project-specific evidence in a
public issue or discussion.

If private vulnerability reporting is unavailable, contact the maintainer through the GitHub
profile for `josephbartlett` without sending sensitive details until a private channel is agreed.

Include the affected revision, platform, a minimal synthetic reproduction, the claimed impact, and
whether any secret or private data may already have been exposed. You should receive an
acknowledgement within seven days.

## Scope

Security reports are especially useful for:

- path-containment or runner-boundary escapes;
- confirmation or model-authority bypass;
- receipt, handoff, or JSON-mode privacy leaks;
- unsafe initialization overwrite or reparse behavior;
- arbitrary command or shell execution;
- integrity, latest-pointer, or binding confusion.

Authority labels describe expected behavior; they are not OS enforcement. Adopting projects remain
responsible for trusted entrypoints, host permissions, secrets, network controls, custody, and
release gates.
