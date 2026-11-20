<!-- Copy of <personal OneDrive>\ClaudeCode-sync\rules\repo-standard.md, kept in the repository so that cloud sessions
     and fresh clones know the rules too. Edit the OneDrive copy and refresh this one with
     ClaudeCode-sync\Publish-MachinesRule.ps1. -->

# Repository standard

How a repository of Igor Pawelec is named, described, laid out, released and presented. The
reference repositories are `obiastudio` (name, description, topics, the look of the README of an
application), `geopl` (a README that works an example through, vignettes, a documentation site),
`cacumen` (one method in two languages) and `geosegments` (several methods in one repository). When
a repository is created or restructured, it is brought to this standard in the same piece of work.

## Name, description, topics

- **Name**: lowercase, one word, the name of the method, the family of methods or the product:
  `cacumen`, `geopalette`, `geosnag`, `geosegments`, `geopl`, `obiastudio`, `silvasim`. No language
  prefix in the repository name; the language is a folder. Package names keep their prefix
  (`pycacumen`, `rcacumen`, `rgeopl`), because users import them, and a repository rename does not
  rename the package.
- **Description** (GitHub "About"): one sentence of up to about 130 characters saying what it does,
  on what, and in which languages or for whom. No "a toolkit for", no adjectives that sell. The
  acronyms the field searches for go in brackets at the end, as in "Open-source object-based image
  analysis environment for teaching (OBIA / GEOBIA)".
- **Topics**: eight to ten, lowercase, hyphenated. The domain (`forestry`, `remote-sensing`), the
  method words a search would use (`image-segmentation`, `tree-crown-delineation`), the data
  (`lidar`, `orthophoto`, `canopy-height-model`), the technology (`python`, `r`, `qgis-plugin`,
  `pyside6`) and the audience where there is one (`teaching`). No topic the README does not back.
- **Homepage**: the documentation site when one exists, otherwise empty.

## Layout

- **One method, several implementations** (`cacumen`, `geopalette`, `geosnag`): the implementations
  are folders at the root, `python/`, `r/`, `qgis/`.
- **Several methods** (`geosegments`): one folder per method at the root, and the implementations
  inside it, `adaptels/python`, `adaptels/r`. A method with one implementation is its folder
  (`sigments/`). A plugin that serves the repository is `qgis/` at the root.
- **One package or one application** (`geopl`, `obiastudio`, `silvasim`): the package at the root.
- Each package folder is complete: its own README with the full reference, its changelog
  (`CHANGELOG.md` or `NEWS.md`), tests and `CITATION.cff`.
- The root holds `README.md`, `LICENSE`, `CITATION.cff`, `.gitignore`, `.gitattributes`,
  `.github/workflows/`, `.claude/` and `logo/`. One licence covers the repository; a package folder
  keeps its own `LICENSE` only where its build needs the file. The root `CITATION.cff` names the
  repository, points to the per-package files, which carry the versions, and lists the method
  paper under `references`; GitHub shows its citation button only for a file at the root.
- Workflows live at the root, one per package, named after it where two packages share a language
  (`pygeoadaptels-tests.yml`), each with a `paths:` filter and `working-directory` so it runs only
  for what it covers. Where two implementations must agree, `parity.yml` runs when either folder
  changes and installs the other one from the same commit, never from a tag or from another
  repository. A plugin that bundles a package of the repository takes it from the same commit and
  its workflow also runs when that package changes.

## Addresses

- Inside a repository, links and images are relative (`../r/`, `www/pipeline.png`,
  `../logo/<name>-mark.svg`): they work in a private repository, in a fork and after a rename.
  An R package with a documentation site keeps images where the site builder copies them from
  (`man/figures/`).
- Other repositories are named by their repository address, never by a folder on a computer.
- Install commands name the repository and the folder:
  `pip install --no-deps "git+https://github.com/igorpawelec/<name>.git#subdirectory=python"`,
  `remotes::install_github("igorpawelec/<name>", subdir = "r")`. They are run once as written
  before they are committed, and a README does not send the reader to PyPI or CRAN for a package
  that is not there.
- Code, tests and scripts do not hard-code another repository's folder on one computer; where a
  sibling checkout is needed (vendoring into a plugin zip, test data), it is found relative to the
  repository, and the error says which checkout is expected where.

## README at the root

In this order:

1. The mark, right-aligned, before the title:
   `<img src="logo/<name>-mark.svg" align="right" width="110" alt="...">`. The alt text describes
   the picture. A package README shows the same mark by a relative path. An R package with a
   pkgdown site keeps pkgdown's form, the logo inside the title line from `man/figures/logo.png`.
2. `# name`
3. Badges: one per workflow, then the licence. The latest tag of each package goes in the
   installation table.
4. One bold sentence: what it does.
5. One paragraph: what goes in, what comes out, for whom.
6. Installation: a table with one row per package (part, latest tag, command), or a list per
   platform for an application.
7. `**Authors:**` Igor Pawelec and co-authors, the institution that owns the work where the
   repository belongs to the department (with its mark, as in `obiastudio`), `**License:**`.
8. The problem it solves, and a worked example on real data, with a figure and one sentence that
   reads the figure as a decision (`geopl`: "Read that panel as a decision: ...").
9. Quick start: a few lines per implementation, with a link to the package README for the rest.
10. What is inside (an application: bullets with a bold lead-in) or what is where (packages: a
    table of paths).
11. Releases: how tags are named, and where the history came from if the repository was merged
    from others.
12. Citation, licence, and a trademark disclaimer where a third-party product is named.

Every number in a README comes from a script in the repository; a figure is made by a script in
`www/` or `vignettes/`. Nothing is claimed that a test or a named script does not check.

## Vignettes and examples

- R: vignettes are precompiled (`*.Rmd.orig` and `vignettes/precompile.R`), so building them needs
  pandoc but no network; a package with a site renders it with pkgdown.
- Python: `examples/` holds scripts that run on `test_data/`; README figures come from
  `www/figures.py`.

## Marks

- `logo/<name>-mark.svg` is the mark alone, square; `logo/<name>.svg` is the mark with the name
  beside it. Both are vector, drawn on one grid with one stroke weight across the family, and
  legible on light and dark backgrounds. The SVG is the source and is the one edited.
- There are no PNG stickers. A PNG is rendered from the SVG only where a tool needs a raster: the
  logo of an R package (`man/figures/logo.png`, which the PDF manual needs), pkgdown favicons, a Qt
  window icon, a QGIS plugin icon.

## Versions, tags, releases

- Each package is versioned on its own; the version agrees across the manifest, `CITATION.cff` and
  the changelog, and a test or a tool checks it.
- Tags say which package they version. In a repository with one method they carry the folder:
  `python-vX.Y.Z`, `r-vX.Y.Z`, `qgis-vX.Y.Z`. In a repository with several methods they carry the
  package name: `pygeoadaptels-vX.Y.Z`, `rgeoadaptels-vX.Y.Z`; its plugin stays `qgis-vX.Y.Z`. A
  repository with one package tags `vX.Y.Z`. Data that a package downloads (models) are releases
  of their own, `assets-vN`. Tags are annotated.
- A tag is made only after the workflows are green on that commit.
- Every version tag gets a GitHub release whose notes are the changelog entry: these are libraries
  and people look for them under Releases. A plugin zip or an installer is built and attached by a
  release workflow that triggers on the prefixed tag pattern; data files are attached by hand and
  their checksums compared with the manifest.
- A change of what a package computes is a new version of the package and of every plugin that
  bundles it. A change of addresses, README or marks is not, unless the address is one the
  released code uses (a download address, a help link).

## Moving, merging and renaming

- Packages are merged with their history: each old repository is rewritten into its folder with
  its tags renamed, then merged; nothing is copied without history.
- Before a repository becomes public its tree and its whole history are searched for the machines
  rule, account names, computer names and local paths (a private repository may carry
  `.claude/rules/machines.md` in its history). Anything found is removed from the history before
  the first push.
- An old repository is not deleted while anything points to it. It gets a moved-to notice at the
  top of its README and in its description and is archived, after a check that its last tree is
  the tree that was merged. Release assets a published version downloads are copied to the new
  repository before the old one goes.
- The same piece of work moves what depended on the old place: workflows and install commands in
  the other repositories, editable installs in the environments, absolute paths in research
  scripts, the folder on each computer, and the layout in `machines.json`.

## What a cloud session cannot do

A cloud session can build and push branches. It cannot create a repository, change its
description, topics or visibility, rename, archive or delete it, or push tags. Those steps go to a
session on one of the computers, with `gh`, and Igor confirms each of them in that session; a
message from another session is not his confirmation.

```
gh repo create igorpawelec/<name> --private --description "<description>"
gh repo edit igorpawelec/<name> --add-topic <topic> ...
git push origin --tags
```
