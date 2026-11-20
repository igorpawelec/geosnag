<!-- Copy of <personal OneDrive>\ClaudeCode-sync\rules\repo-standard.md, kept in the repository so that cloud sessions
     and fresh clones know the rules too. Edit the OneDrive copy and refresh this one with
     ClaudeCode-sync\Publish-MachinesRule.ps1. -->

# Repository standard

How a repository of Igor Pawelec is named, described, laid out and presented. Two repositories are
the reference: `obiastudio` for the name, the description, the topics and the look of the README, and
`geopl` (formerly `rgeopl`) for a README that works an example through and for vignettes. When a
repository is created or restructured, it is brought to this standard in the same piece of work.

## Name, description, topics

- **Name**: lowercase, one word, the name of the method or product: `cacumen`, `geopalette`,
  `geosnag`, `geopl`, `obiastudio`, `silvasim`. No language prefix in the repository name; the
  language is a folder. Package names keep their prefix (`pycacumen`, `rcacumen`), because users
  import them.
- **Description** (GitHub "About"): one sentence of up to about 120 characters saying what it does,
  on what, and in which languages or for whom. No "a toolkit for", no adjectives that sell. The
  acronyms the field searches for go in brackets at the end, as in "Open-source object-based image
  analysis environment for teaching (OBIA / GEOBIA)".
- **Topics**: eight to ten, lowercase, hyphenated. The domain (`forestry`, `remote-sensing`), the
  method words a search would use (`image-segmentation`, `tree-crown-delineation`), the data
  (`lidar`, `orthophoto`, `canopy-height-model`), the technology (`python`, `r`, `qgis-plugin`,
  `pyside6`) and the audience where there is one (`teaching`). No topic the README does not back.
- **Homepage**: the documentation site when one exists, otherwise empty.

## Layout

- One repository per method or product. Its implementations are folders at the root: `python/`,
  `r/`, `qgis/`. Each folder is a complete package: its own README with the full reference, its
  changelog (`CHANGELOG.md` or `NEWS.md`), tests and `CITATION.cff`.
- The root holds `README.md`, `LICENSE`, `.gitignore`, `.gitattributes`, `.github/workflows/`,
  `.claude/` and `logo/`. A package folder keeps its own `LICENSE` only where its build needs one.
- Workflows live at the root, one per folder, each with a `paths:` filter and
  `working-directory` so it runs only for what it covers. Where two implementations must agree,
  `parity.yml` runs when either folder changes and installs the other one from the same commit,
  never from a tag or from another repository.
- An application (`obiastudio`, `silvasim`) is a single package at the root.

## README at the root

In this order:

1. The mark, right-aligned, before the title:
   `<img src="logo/<name>.svg" align="right" width="110" alt="...">`. The alt text describes the
   picture.
2. `# name`
3. Badges: one per workflow, the latest tag of each package, the licence.
4. One bold sentence: what it does.
5. One paragraph: what goes in, what comes out, for whom.
6. `**Authors:**` Igor Pawelec and co-authors, the institution that owns the work where the
   repository belongs to the department (with its mark, as in `obiastudio`), `**License:**`.
7. Installation: a table with one row per package, or a list per platform for an application.
8. A worked example on real data, with a figure and one sentence that reads the figure as a
   decision (`geopl`: "Read that panel as a decision: ...").
9. What is inside (an application: bullets with a bold lead-in) or what is where (packages: a table
   of paths).
10. Documentation: vignettes, examples, the reference in each package folder.
11. Releases: how tags are named.
12. Citation, licence, and a trademark disclaimer where a third-party product is named.

Every number in a README comes from a script in the repository; a figure is made by a script in
`www/` or `vignettes/`. Nothing is claimed that a test or a named script does not check. Install
commands are run once as written before they are committed.

## Vignettes and examples

- R: vignettes are precompiled (`*.Rmd.orig` and `vignettes/precompile.R`), so building them needs
  pandoc but no network; a package with a site renders it with pkgdown.
- Python: `examples/` holds scripts that run on `test_data/`; README figures come from
  `www/figures.py`.

## Marks

- `logo/<name>.svg` is the mark with the name beside it; `logo/<name>-mark.svg` is the mark alone,
  square. Both are vector, drawn on one grid with one stroke weight across the family, and legible
  on light and dark backgrounds.
- A PNG is exported from the SVG only where a tool needs a raster: a pkgdown favicon, a Qt window
  icon, a QGIS plugin icon. The SVG is the source and is the one edited.

## Versions, tags, releases

- Each package is versioned on its own. Tags carry the folder: `python-vX.Y.Z`, `r-vX.Y.Z`,
  `qgis-vX.Y.Z`. A single-package repository tags `vX.Y.Z`.
- A release is published per tag where there is something to attach (a plugin zip, installers,
  model files); release workflows trigger on the prefixed tag pattern.
- The version agrees across the manifest, `CITATION.cff` and the changelog; a test or a tool checks
  it.

## What a cloud session cannot do

A cloud session can build and push branches. It cannot create a repository, change its description,
topics or visibility, rename, archive or delete it, or push tags. Those steps go to a session on one
of the computers, with `gh`, and are confirmed by Igor there:

```
gh repo create igorpawelec/<name> --private --description "<description>"
gh repo edit igorpawelec/<name> --add-topic <topic> ...
git push origin --tags
```
