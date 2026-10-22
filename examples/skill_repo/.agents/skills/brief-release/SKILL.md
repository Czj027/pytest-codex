---
name: brief-release
description: Create a short release note from release.json for a release-summary request.
---

Read release.json. Write RELEASE.md with exactly this structure, replacing the
version and change names with the input values:

```text
# Release VERSION

- CHANGE
- CHANGE

Review: offline replay verified
```

Do not install dependencies or change release.json. Reply briefly after writing.
