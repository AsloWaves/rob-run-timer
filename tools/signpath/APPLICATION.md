# SignPath Foundation application (draft, paste into the form at https://signpath.org/apply)

- **Project name:** Rob Run Harvest Timer
- **Repository:** https://github.com/AsloWaves/rob-run-timer
- **Download page:** https://github.com/AsloWaves/rob-run-timer/releases
- **License:** MIT (OSI-approved, no dual licensing, no proprietary components)
- **Maintainer / publisher name:** AsloWaves (sole maintainer; author, reviewer and approver)
- **Description:** A small Windows desktop timer for the Steam game ROB RUN. It counts down plant harvest time per grow table, applies the upgrade time cuts, and shows a Windows notification when a table is ready. It also has a Grow Room window that estimates profit per hour. Unofficial fan tool.
- **Built how:** GitHub Actions (`.github/workflows/build.yml`) runs PyInstaller on `windows-latest` and uploads `RobRunTimer.exe` as an artifact. Version and product metadata are set from `rob_run_timer.py` by `tools/make_version_info.py`.
- **Privacy:** no telemetry or user data collected. The only network call is an optional update check against GitHub's public API (can be disabled in Settings). Documented in the README under "Code signing policy and privacy".
- **Releases so far:** v1.1.0 to v1.2.0.
- **MFA:** enable two-factor sign-in on the GitHub account first.
- **Honest note on reputation:** the project is new and has a single maintainer; say so, and link the releases and any stars/downloads.

## After approval
1. Install the SignPath GitHub app, create the project + `release-signing` policy, and add repo secret `SIGNPATH_API_TOKEN` and variable `SIGNPATH_ORGANIZATION_ID`.
2. In `build.yml`, replace the "Code signing" comment with the `signpath/github-action-submit-signing-request@v1` step, then attach the signed exe instead of `dist/RobRunTimer.exe`.
