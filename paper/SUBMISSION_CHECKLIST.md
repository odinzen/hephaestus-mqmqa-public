# JORS submission checklist (Hephaestus metapaper)

Updated 2026-09-03 (fifth pass, v0.4.0). Title and abstract carry the full scope, gates
re-run green. Ready for the two submission clicks below.

## Done (2026-09-03, fifth pass - v0.4.0)

- uTDB unified dialect shipped: :Q phases and MQ* parameters in the TDB reader, open spec
  (docs/UNIFIED_TDB_SPEC.md), two themed demonstration files (aluminum recycling: Al-Zn +
  NaCl-KCl-MgCl2 flux; steelmaking: Fe-C + FeO-MgO-SiO2 slag), machine-precision round-trip
  suites for both. Fixed a ternary-excess exponent slot bug the round-trip gate caught.
- Inden-Hillert-Jarl magnetic model implemented for TDB CEF phases; validated by pycalphad
  parity (crfe_bcc_magnetic) and the pure-iron transitions (1185/1668/1811 K vs measured
  1184.8/1667.5/1811). Own FeC.tdb (Gustafson 1985 on Dinsdale unaries). Suite: 104 passed.
- Web app: Melt/Alloy view toggle for unified files (computes the real Fe-C diagram,
  eutectic 1430 K at 17 mol% C), interstitial-phase support in the alloy sampler, figure
  zoom on every calculator, interactive Scheil (hover + pinned points, windowed axes,
  annotated), builder auto-populates from any loaded file, capacity-limited concierge copy.
- Supplementary Material S1 added: plain-language primer for the non-programmer, ending
  with how to do an assessment as a non-expert; referenced from the manuscript.
- Title and abstract updated to the full scope (slags, molten salts, alloys; three
  dialects; magnetic model; chloride family). Schools-of-formats table (Table 1) with
  XTDB as the spine; TDB -> uTDB -> XTDB path stated.
- Manuscript docx rebuilt clean of accumulated duplicate media (13.8 MB -> <1 MB); the
  argus heading-regex hang this exposed is fixed upstream in the argus repo with a
  regression test.
- Cover letter re-dated 3 September 2026, archive line v0.4.0.

## Done (2026-09-02, fourth pass - v0.3.0)

- TDB front-end shipped: the engine reads the Thermo-Calc dialect; validated on pycalphad's
  own test databases to ~1e-10 J/mol-atom (Al-Zn, Pb-Sn, Al-Mg), out-of-subset models fail
  loudly, suite now 81 passed. Browser gained alloy mode, the open AlZn.tdb example (own
  transcription of an Mey 1993 on Dinsdale unaries, verified bit-identical via pycalphad),
  and Scheil solidification on both chemistries.
- Manuscript rewritten around it: universal-reader abstract, workflow-stack introduction
  (FactSage, Thermo-Calc, OpenCalphad, pycalphad, CemGEMS), ChemSage lineage cited, TDB
  reader and Python API in Implementation, six-tool browser paragraph with Scheil, QC rows
  for the TDB oracle and scope guard, release-practice line, and a Worked examples
  subsection with the salt and alloy listings and Figures 4-5 (run verbatim; outputs match
  the figures). Five new registry-verified references (argus check 5/5 ok); full renumber
  to 34 entries, argus order green (34/34, figures 1-5, tables 1-2).
- Version bumped to v0.3.0 throughout (software location, data availability, cover letter).

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

- 2026-09-02 addendum: salt-family mention added to the database section with three new
  registry-verified references (Barin 1995, Hersh & Kleppa 1965, Sangster & Pelton 1987;
  argus check 3/3 ok, argus order green at 29/29). A wrong first-guess DOI for Hersh &
  Kleppa (resolved to a different 1965 JCP article) was caught by the gate and corrected
  to 10.1063/1.1696115 before it entered the list.

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
