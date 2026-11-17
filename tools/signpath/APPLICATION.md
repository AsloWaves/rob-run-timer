# SignPath Foundation application (https://signpath.org/apply)

Every field on the form as of 2026-11-17, in order. `*` = required. Nothing here has been submitted.

| Field | Answer |
|---|---|
| Project Name* | Rob Run Harvest Timer |
| Repository URL* | https://github.com/AsloWaves/rob-run-timer |
| Homepage URL* | https://github.com/AsloWaves/rob-run-timer |
| Download URL | https://github.com/AsloWaves/rob-run-timer (the README has the download link and the SignPath credit. The form says this page must mention the SignPath Foundation, and the Releases page does not, so don't use that one.) |
| Privacy Policy URL | https://github.com/AsloWaves/rob-run-timer#code-signing-policy-and-privacy |
| Wikipedia URL (optional) | leave blank (no article) |
| Tagline* | A Windows timer that counts down plant harvests on each grow table in the game ROB RUN. |
| Category* | Gaming (the list is: Accessibility, AI Tools, Audio, Developer Tools, Educational, Gaming, Graphics, Productivity, Science, Other) |
| Description* | Rob Run Harvest Timer is a small open-source Windows desktop app for players of the Steam game ROB RUN. It runs a countdown for each grow table, applies the upgrade time reductions, and shows a Windows notification when a harvest is ready. It also includes a Grow Room window that estimates profit per hour. It is an unofficial fan tool, written in Python and tkinter, and MIT licensed. |
| Reputation* | See the draft below. |
| Maintainer Type | Individual maintainer(s) (the list is: Independent community project, Non-profit foundation or research/educational institution, For-profit company or corporate-backed project, Individual maintainer(s), Other) |
| Build System* | GitHub Actions (the only other option is GitLab CI/CD) |
| First Name* / Last Name* | yours (the name for the SignPath account) |
| Email* | yours (used for the SignPath account and notifications) |
| Company Name | leave blank |
| Primary Discovery Channel* | your real answer (I could not read the dropdown's options) |
| Exact source (optional) | e.g. "Google search" or whichever is true |
| reCAPTCHA | you complete it |
| Code of Conduct checkbox* | you read and tick it. It says certificates are issued in SignPath Foundation's name and may be revoked if terms are violated. |
| "Other communications" checkbox | optional, your choice |
| "Store and process my personal data" checkbox* | your choice. The form can't be submitted without it. |

## Reputation draft (edit before sending)

The project is new and small, so say so plainly:

> New project, first released 16 Nov 2026 and still being built out (v1.2.0 now). It is a small single-maintainer tool, so there is no press coverage yet. Public activity: 4 tagged releases, a documented README with a privacy section, and an MIT-licensed repository with an automated GitHub Actions build. At the time of writing the releases have about 9 downloads and the repository has no stars, and some of those downloads are my own testing. I am applying early because unsigned downloads trigger Windows SmartScreen warnings that put players off.

Heads-up: SignPath says it checks that a project has a "verifiable reputation". With zero stars and a one-day-old repo, this field is the most likely reason for a rejection. Waiting a few weeks for real usage (a post in the ROB RUN community, stars, downloads) would improve the odds. Re-check the numbers with `gh api repos/AsloWaves/rob-run-timer/releases` before sending.

## After approval
1. Install the SignPath GitHub app, create the project and a `release-signing` policy, and add repo secret `SIGNPATH_API_TOKEN` and variable `SIGNPATH_ORGANIZATION_ID`.
2. In `.github/workflows/build.yml`, replace the "Code signing" comment with the `signpath/github-action-submit-signing-request@v1` step, then attach the signed exe instead of `dist/RobRunTimer.exe`.
