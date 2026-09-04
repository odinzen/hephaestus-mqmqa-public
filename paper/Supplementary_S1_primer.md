# Supplementary Material S1. A primer for the experimentalist

## Hephaestus without programming: what a thermodynamic database is, and your first calculations

This supplement accompanies "Hephaestus: an in-browser open-source engine and databases for the thermodynamics and phase diagrams of slags, molten salts, and alloys." It is written for the scientist who measures, synthesizes, or operates, and who has never used a computational thermodynamics tool. Nothing here requires programming, installing software, or editing a file. Every walkthrough starts from a button that is already on the page, with the data already behind it; you will never be asked to type species names into empty fields or to prepare an input file. If a step in this document does not work as written, that is a bug, and we would like to hear about it (info@odinzen.io).

The calculator lives at:

https://odinzen.github.io/hephaestus-mqmqa-public/

It runs entirely inside your web browser. Nothing you do on the page is transmitted anywhere; there is no server behind it.

### 1. What a thermodynamic database actually is

A thermodynamic database is a plain text file. You could open one in Notepad and see ordinary printable characters. The file format is not the valuable part; the text that goes into it is. Those numbers are fitted Gibbs energy functions, the distilled result of decades of measurements (calorimetry, vapor pressure, phase diagram determinations) evaluated and compressed into a form a computer can evaluate at any temperature and composition. When people in this field say "an assessment," they mean the expert work of choosing those numbers so that one set of functions reproduces all the reliable measurements at once.

Once such a file exists, a calculation engine can answer questions no single experiment answered directly: the full phase diagram, the equilibrium phases at any composition and temperature, activities, mixing enthalpies. The database is the science; the engine is the arithmetic. Hephaestus supplies both, openly, and the browser page is where they meet.

You never need to open or edit a database file to use this calculator. The open databases are behind one-click buttons, and if a colleague sends you a file, you load it with a file-picker like attaching a document to an email.

### 2. The three file names you will meet

Different software families historically wrote their databases in different text layouts, so a file from one program is unreadable to another even when the science inside is the same. Hephaestus reads the two major layouts and a unified extension of them:

| File ending | Where it comes from | What it carries here |
|---|---|---|
| .dat | The FactSage / ChemApp family | Slags and molten salts (the short-range-ordering liquid model lives in this format) |
| .tdb | The Thermo-Calc / OpenCalphad / pycalphad family | Alloy systems |
| .utdb | This project's documented open extension of .tdb | Alloys, slags, and salts together in one file |

For using the calculator, the distinction hardly matters; the page detects the format when a file loads. It matters only when you ask where a file came from or which software a collaborator uses.

### 3. Your first calculation, in five clicks

We will find the LiCl-KCl eutectic, a workhorse molten salt.

1. Open the calculator page.
2. In the card titled "1 · Load a thermodynamic database," press **Load the open salt database**.
3. The page fills in. The **System** card lists what the file contains: the liquid solution phase and the solid phases it can freeze into.
4. Scroll to the **Phase diagram** card. The full temperature-composition diagram is drawn from the loaded data, calculated live in your browser, not a stored picture.
5. Click anywhere inside the diagram. A readout reports the temperature, the composition you clicked, and which phases are stable there, with amounts.

The lowest point of the liquid region is the eutectic, near 45 mol% LiCl and 626 K in the measured literature; the assessed database reproduces it within a few kelvin. Every point you click is added to a pinned history list under the diagram, so you can click several conditions and compare them side by side without writing anything down.

That is the entire workflow. Load, click, read. Every other feature on the page is a variation of these three steps.

### 4. Reading the readouts

Compositions on the salt and slag diagrams are in mole percent on a cation basis (for LiCl-KCl, the fraction of Li among Li+K; the chlorine follows automatically). Temperatures are in kelvin. When a clicked point falls in a two-phase region, the readout names both phases and gives their proportions by the lever rule, exactly the construction you would do by hand on a printed diagram, done for you at the clicked point.

The **Solve equilibrium** card does the same job numerically instead of graphically: enter a composition, pick a temperature, press Compute, and read the equilibrium Gibbs energy and phase amounts. Use the diagram when you want the whole landscape and the solver when you want numbers for one condition.

### 5. The slag ternary

Press **Load the open slag database**. The page loads the assessed FeO-MgO-SiO~2~ system and adds ternary views. Two kinds are offered, and the toggle between them is the main control:

- An **isothermal section** is the triangle at one fixed temperature: which phase fields exist at, say, 1873 K. Click inside any field and the readout names the phases; in a three-phase triangle the lever rule gives all three amounts.
- A **liquidus projection** looks down on the whole temperature axis at once: it shows which solid appears first on cooling at every composition, with temperature contours.

If you have only ever read these diagrams in handbooks, the difference here is that the diagram is computed from the loaded file while you watch, so when a database improves, the diagram improves with it.

### 6. Freezing a melt: the Scheil panel

Below the binary phase diagram sits **Scheil solidification**. Equilibrium freezing assumes the solid keeps re-equilibrating with the liquid as it cools; real castings often do not have time for that. The Scheil approximation takes the opposite limit, no diffusion in the solid once it forms, and it usually brackets reality from the other side. Enter a starting composition, press **Run Scheil**, and the panel plots how much liquid remains as temperature falls, against the equilibrium (lever rule) curve for comparison, and reports when each solid appears and where the last liquid freezes. For a melt-processing or crystal-growth experiment, this is the two-line answer to "what will this melt do in my furnace."

### 7. Loading a file someone sent you

Press **Choose a .dat or .tdb file** and pick the file. It loads exactly like the built-in buttons and every calculator on the page switches to it. Uploaded files are temporary; they live only in the open tab and vanish on refresh, and up to three can be loaded at once, each pinned with its own color so you can switch between them. That also means systems from different sources sit side by side in one page, and the unified .utdb dialect goes further by holding, for example, an alloy and a molten salt in a single file; your systems are never split across separate products. Nothing is uploaded anywhere; the file is read inside your browser and stays on your machine, which also means confidential files are safe to load.

### 8. When your system is not on the page

The built-in buttons cover the open slag, chloride salt, and Al-Zn alloy databases shipped with the present work, plus the two unified demonstrations (aluminum recycling and steelmaking). If the system you need is not among them, there are two doors:

- The **Phase diagram builder** card lets you construct a simple system yourself from melting points and mixing energies, directly on the page. It is a teaching and estimation tool, not an assessment.
- The **Request a database** card is for real systems with real literature. Point it at your folder of collected papers and it prepares an email to us. Small, well-bounded systems may be added to the open collection free as capacity allows, with sources cited to their original authors and the contribution credited to you; larger or confidential work is a paid engagement and comes back as a quoted proposal. Either way you never touch a file format.

### 9. What this calculator will not do

Honesty about scope saves your time. The engine handles condensed phases (liquids, solid solutions, stoichiometric compounds). It also calculates ideal-gas equilibria from NASA polynomials, in a gas-equilibrium card on the page, though the gas is not yet coupled to a molten slag. Kinetics beyond the Scheil approximation is out of scope. The shipped slag database documents its known limits in the files themselves, the largest being silica-rich miscibility gaps that sit too high in temperature. And the static ternary showcase images on the page exist only for the assessed built-in systems; a newly loaded file drives the live calculators, not the showcases.

### 10. Your first assessment, as a non-expert

Everything above treats the database as something you receive. This closing section is about the step nobody tells you is within reach: contributing to one. The skill transfers, because an assessment is built from exactly the knowledge you already have as an experimentalist, and unlike fluency in any vendor's interface, it stays yours.

An assessment needs measured facts about a system, and they are not all equally valuable. In rough order of what pins a database down:

1. **Invariant points.** A measured eutectic (its temperature and composition), a congruent melting point, a peritectic. One good invariant constrains more than a dozen scattered points.
2. **Phase boundary points.** Liquidus, solidus, and solvus determinations, thermal analysis arrests, quench-and-identify results.
3. **Calorimetry.** Mixing enthalpies of the liquid, formation enthalpies of compounds, heat capacities. This is what anchors the energies behind the diagram rather than just its shape.
4. **Activity measurements.** EMF cells, Knudsen effusion, vapor pressure. These constrain the liquid model directly.

What makes a source usable: the numbers are in a table or a readable figure, with the temperature, the composition, and the method stated. A handbook compilation counts. What we cannot use: values quoted with no source behind them, figures too coarse to read numbers from, and parameters copied out of someone else's assessment or a commercial database (those are their work product, not measured facts, and we build only from measurements).

You can feel the assessment loop yourself, today, with the **Phase diagram builder** card: enter two melting points, guess a mixing energy, and watch the diagram it implies; nudge the energy and watch the eutectic move toward or away from the measured one. Propose, compare, adjust. That loop, run seriously against every reliable measurement at once, is the entire discipline; the builder is its five-minute version.

When you send us a system through the request card, this is the bundle that gets a fast, useful answer:

- The system, named (components, and the temperature range you care about).
- The papers, with a line each on what is in them (mixing calorimetry, liquidus points, an assessed diagram to compare against). The request card lists your PDF folder for you.
- Your own measurements, if any, flagged as yours.
- What you need out the other end: a full diagram, a liquidus in one region, activities at one temperature.

A tool that is easy to start and a tool you can grow with are different things, and this page intends to be both. The calculators are the first afternoon; the builder and this section are the second year; the request card is for everything in between.

### 11. Small glossary

- **Assessment.** The expert fitting of a system's Gibbs energy functions to all reliable measurements at once; the product is a database file.
- **CALPHAD.** The field's name for this method: CALculation of PHAse Diagrams from assessed Gibbs energies.
- **Component.** An independent chemical building block of the system (for LiCl-KCl on a cation basis, LiCl and KCl).
- **Endmember.** A pure limiting composition of a solution phase, such as pure LiCl liquid.
- **Excess parameter.** The fitted term describing how a real mixture deviates from ideal mixing; the heart of an assessment.
- **Gibbs energy.** The quantity nature minimizes at fixed temperature and pressure; whichever set of phases has the lowest total is what you observe at equilibrium.
- **Lever rule.** The proportionality that reads phase amounts off a tie-line; the readouts apply it at every click.
- **Liquidus / solidus.** The temperatures where melting is complete / begins, as composition-dependent curves.
- **MQMQA.** The Modified Quasichemical Model in the Quadruplet Approximation, the liquid model behind slags and salts here; it describes the short-range ordering real ionic melts show.
- **Parser (reader).** The piece of code that turns a database text file into numbers an engine can use. You never interact with it; it runs when a file loads.
- **Phase.** A physically distinct, homogeneous part of the system: a melt, a particular solid solution, a compound.
- **Tie-line / tie-triangle.** The line (binary) or triangle (ternary) connecting the compositions of phases in equilibrium with each other.
- **TDB / .dat / .utdb.** Database file layouts; see Section 2. The container is ordinary text; the contents are years of measurement.
- **WebAssembly.** The browser's way of running compiled programs at near-native speed; it is why the full engine runs on the page with nothing installed.
