# JORS submission checklist (Hephaestus metapaper)

Updated 2026-09-02 (final pass). Manuscript updated to release v0.2.0, cover letter rebuilt
on the Odinzen letterhead, gates re-run. Ready for the two submission clicks below.

## Done (2026-09-02, third pass)

- main pushed (public repo now matches the deployed site) and release v0.2.0 tagged and pushed.
- Manuscript updated to v0.2.0: browser-application section lists all five tools including
  session uploads and the live solver for any loaded three-cation file; the reuse section
  records the in-browser hull covering loaded ternaries (was future work, now shipped);
  software-location and data-availability blocks bumped; docx and PDF rebuilt from the md.
- Cover letter rebuilt on the Odinzen letterhead template (header block, footer logo),
  dated 2 September 2026, v0.2.0 archive line; PDF rendered and visually checked.
- Gate record: argus order on the rebuilt docx is green (26 in-text / 26 list in
  first-appearance order; tables 1-2 and figures 1-3 resolve). The reference list is
  hash-identical to the 2026-08-25 build (sha256 prefix 9bac98bda6192e47), so the 08-25
  metadata gate (24 registry-resolved, 2 hand-verified monographs, suspects adjudicated)
  carries to this build unchanged.

## Remaining - Michael's two clicks

1. **Zenodo DOI (do first; JORS wants a persistent archive):** zenodo.org -> log in with
   GitHub -> enable the hephaestus-mqmqa-public repository toggle -> on GitHub, the existing
   v0.2.0 release triggers the deposit (or click "create release" again if needed). Copy the
   minted DOI into the JORS form when asked.
2. **JORS portal:** openresearchsoftware.metajnl.com -> submit -> upload the manuscript docx,
   the three figures, and the cover letter from this package.
3. Optional, after submission: SSRN (MatSciRN) preprint from the same PDF, feeding the
   LinkedIn series.

## Prior passes

Updated 2026-08-25 (second pass). The bibliography is now Zotero-generated, the
repository is public, and v0.1.0 is tagged. The list below is what remains.

## Done (2026-08-25)

- Repository public: github.com/odinzen/hephaestus-mqmqa-public (flipped by Michael).
- Release tag v0.1.0 pushed on main.
- Bibliography regenerated from the Zotero export (24 registry-bound entries plus
  the two no-DOI monographs), 26 references, Greig Parts I and II now separate
  entries, in-text markers renumbered, all argus gates green on the rebuilt docx.
- Documented corrections to registry typos (the papers' true forms, deviating from
  Crossref): Greig JW (registry says "Creig", Part II), Fe-O-SiO2 (registry has
  lowercase "o", Björkman 1985), SiO2 subscript-artifact spacing (Bowen-Schairer).
- Software location block updated per the no-Zenodo decision: archive = GitHub
  release v0.1.0.

## Remaining before submission

1. **Zotero library hygiene** (the document is correct; make the library match):
   in Zotero, open the Greig Part II item and correct the author "Creig" to
   "Greig"; add the two no-DOI monographs by hand (Robie and Hemingway, USGS
   Bulletin 2131, 1995; Chase, NIST-JANAF Tables 4th ed., Monograph 9, 1998).
2. **SSRN preprint** (MatSciRN network): upload the manuscript PDF from this
   package. Feeds the LinkedIn preprint series.
3. **Journal-submission flag (decide before submitting to JORS, not before SSRN):**
   JORS requires deposit in a persistent archive (their guidance names Zenodo or
   figshare); a GitHub release alone may be bounced by the editor. The Zenodo
   GitHub integration is two clicks and mints the DOI from the existing v0.1.0
   release whenever you are ready.
4. **Update the cover letter date** if submission is not on 2026-08-25.

## Gate record (all run on the final built docx, 2026-08-25 second pass)

- Argus check: 26 entries; 24 resolve against Crossref/OpenAlex/arXiv. The three
  suspect flags were adjudicated: Greig Part II is the documented registry typo,
  and both arXiv MLIP entries match the canonical arXiv author lists exactly
  (OpenAlex author-parsing noise). The two monographs are no-DOI, verified by hand.
- Argus order: 26 in-text citations and 26 list entries agree, first-appearance order.
- Argus leak: no codenames, no engine-method description.
- Argus statements: conflict-of-interest and data-availability both pass.
- Argus typography, units, consistency: clean.
- Argus kristina: clean apart from six long-sentence advisories, kept deliberately.
- PDF rebuilt (LibreOffice) and visually checked: Times New Roman, justified,
  black, Odinzen-only byline, references render correctly.

## Notes

- JORS conventions applied: metapaper section template, Vancouver numbered
  references by first appearance, American spelling.
- Authorship: single author, byline Odinzen LLC only (recorded decision 2026-08-25).
- Optional polish: an architecture figure is allowed by the template and could be
  added in revision if reviewers ask.
