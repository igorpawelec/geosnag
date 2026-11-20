<!-- Copy of <personal OneDrive>\ClaudeCode-sync\rules\new-repo.md, kept in the repository so that cloud sessions
     and fresh clones know the rules too. Edit the OneDrive copy and refresh this one with
     ClaudeCode-sync\Publish-MachinesRule.ps1. -->

# Starting a new repository

Checklist for a new project, so that every repository behaves the same for Claude Code on all three
computers and in the cloud.

1. **Create it private** on GitHub under the right owner (personal or DFRM-FF-UAK); make it public
   only as a deliberate step, after checking that `.claude/rules/` and the history hold nothing
   private (the machines rule names accounts and paths: strip it, from the history too, or keep
   the repo private).
2. **Clone to the standard place** on each computer: `<apps root>\<repo>` for applications and
   packages, `<projects root>\<repo>` for research projects and papers (roots per computer are in
   `machines.md`). Same folder name everywhere.
3. **Register it**: add the name to `layout` in `ClaudeCode-sync\machines.json`, then run
   `Publish-MachinesRule.ps1` to drop `.claude/rules/` in (it takes every git repository under the
   roots, so there is no list to edit).
4. **`CLAUDE.md`** from `ClaudeCode-sync\templates\CLAUDE.md.template`: environment and how to run,
   how to test, layout, language rules, what stays out of git. Keep it short; details go in
   `.claude/rules/*.md` or docs.
5. **`.gitignore`** before the first commit: virtual environments, caches, build output, source
   material of courses and publications, large data, `CLAUDE.local.md`, `.claude/settings.local.json`.
6. **Name, description, topics, layout, README, mark, tags and releases** as in
   `repo-standard.md`. **LICENSE** chosen explicitly and placed at the root.
7. **First commit by Igor Pawelec**, English message, no attribution lines (`authorship.md`).
8. **Tests and a fast check** that a contributor can run locally (`pytest`, `R CMD check`, lint);
   name the command in `CLAUDE.md`. CI only when the repo needs releases.
9. **Agents**: copy the standard roles the project needs from `claude-home\agents\` or define them in
   `.claude/agents/`, scoped per `agents.md`.
10. **Data and documents** produced by the project carry Igor Pawelec as author in metadata.

Conventions that do not change between repositories: English code, comments and commits; Polish
user interface where the project is for Polish students, with `tr()`-style translation files;
computed values documented with their formula and source; course source material never committed.
