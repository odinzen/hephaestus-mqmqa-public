# JORS submission checklist (Hephaestus metapaper)

Updated 2026-09-09 (seventh pass, v0.6.0). The XTDB third-generation reader is now built and
described, two authors, the gas couplings and the full system set are described, references
verified and citations renumbered, gates re-run green. Ready for the two submission clicks below.

## Done (2026-09-09, seventh pass - v0.6.0)

- XTDB reader built and shipped (src/xtdb.c, src/xtdb.h): parses the open XML CALPHAD format
  and assembles third-generation Gibbs energies, an Einstein heat capacity valid to 0 K
  (weighted by atom count per formula unit) and a two-state liquid. Compiled into the
  WebAssembly core; a dedicated browser card reads an .xtdb file and computes its binary
  phase diagram live by lower-convex-hull common-tangent construction.
- Two databases ship: data/xtdb/AlC.xtdb (third-generation Al-C, He et al. 2021, our own
  transcription; reproduces Al melting 933.47 K and the Al4C3 peritectic 2429 K) and
  web/PbSn.xtdb (classic assessment in XTDB, Ngai & Chang 1981; eutectic 456 K, x(Sn) 0.74).
- Validated: C engine matches an independent Python evaluator to < 1e-6 J/mol-atom across the
  Einstein, two-state, and excess terms; heat capacities physical (graphite ~8.5, Al ~3R,
  Al4C3 -> 7*3R); reproduced in-browser (WASM). The Al4C3 Cp/atom-count convention was flagged
  to Michael as a science tie and confirmed against the XTDB spec and the He 2021 diagram.
- Manuscript: abstract, Table 1, and reuse section updated (engine reads XTDB directly with
  third-generation models); Figure 10 added (Al-C and Pb-Sn); three registry-verified
  references added (Chen & Sundman 2001, He et al. 2021, Ngai & Chang 1981; argus check 3/3
  ok, canonical numbering 50 total); version bumped v0.5.1 -> v0.6.0; argus order green
  (50 citations, tables 1-3, figures 1-10 all resolve).
- v0.6.0 tag and GitHub release cut (2026-09-09), published on main; the paper's persistent
  identifier https://github.com/odinzen/hephaestus-mqmqa-public/releases/tag/v0.6.0 resolves.
- Figure 1 (architecture) corrected to show .xtdb alongside .dat/.tdb/.utdb, caption updated.
- Submission-wide staleness pass across every artifact:
  - Cover letter: four containers incl. XTDB third-generation; archive line v0.4.0 + Zenodo
    replaced with release v0.6.0; letterhead/footer preserved (edited in place).
  - Supplementary S1 primer: XTDB row + third-generation glossary entries added; the
    third-generation card described in the file-loading section.
  - Manuscript: residual counts fixed (132/137 -> 142 tests; "either of two dialects" -> any).
  - Highlights file added (five points, <=85 chars each), current at v0.6.0.
  - Desktop submission zip rebuilt at v0.6.0 (now includes Highlights + fig10, 10 figures).
- OPEN: the two submission clicks.

## Done (2026-09-09, sixth pass - v0.5.1)

- Second author added: Gabriel Bustamante (Odinzen LLC, ORCID 0009-0005-3269-024X),
  credited software, software validation, and writing (review and editing). Byline, ORCIDs,
  list of contributors, competing-interests statement, and the AI-use disclosure updated to
  two authors. Michael E. Bustamante's affiliation confirmed as Odinzen LLC only (ASU left
  off for this Odinzen-product paper).
- Gas-flux (chloride fume) coupling shipped and described: engine salt activities times
  measured pure-component vapour pressures; new module python/mqmqa/gas_flux.py with a
  five-check test, and Figure 8. Joins the gas-condensed and gas-slag couplings (Table 3).
- Full shipped system set now documented (Table 2 + text): the CaO-Al2O3 and Al2O3-SiO2
  binaries, the CaO-Al2O3-SiO2 ternary (fitted ternary term, RMS ln a 0.48 over 45 KEMS
  points), the CaO-FeO-MgO-SiO2 quaternary, and the clinopyroxene and spinel solid solutions.
  Two references added and Crossref-verified (Rankin & Wright 1915; Zaitsev et al. 1997);
  citations canonically renumbered (47 total); argus order and check both green.
- OCASI/TQ embedding interface named in the reuse section; Figure 1 gains the gas engine;
  test count updated to 137; described release bumped to v0.5.1 (past the frozen v0.5.0 tag).
- Browser app: five live bugs fixed and verified in-app (the slag/gas card no longer shows
  the FeO-SiO2 chart for a non-iron oxide; live-ternary gating consistent load vs toggle;
  db/phase global swap guarded with finally; gas-card HTML escaper hardened; a load during
  WASM init now reports instead of silently doing nothing). Flux-vapour curve labels de-collided.
- CONTRIBUTING.md added to the remote with the code/science boundary rule.

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
