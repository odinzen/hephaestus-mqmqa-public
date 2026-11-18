# Hephaestus against Thermochimica

Engine commit 39b9566557bcaa9f2a989de5edb3403c0057f9d5; sealed hashes checked; 368 raw Thermochimica files checked against the manifest.

## Against Thermochimica's runs (tests and extended grid)

| Class | Count |
|---|---|
| agree | 141 |
| close | 17 |
| disagree | 43 |
| refused | 107 |

| Point | Class | Detail |
|---|---|---|
| TestSUBQNonuniformZeta | refused | the test changes the database in memory after reading it |
| TestThermo03 | disagree | Hephaestus computed an input the test requires to be refused |
| TestThermo04 | refused | input not accepted: T=None K, P=1.0 atm, unit moles |
| TestThermo05 | refused | input not accepted: T=300.0 K, P=None atm, unit moles |
| TestThermo06 | refused | input not accepted: T=2000.0 K, P=1.0 atm, amounts {} |
| TestThermo07 | refused | input not accepted: T=-300.0 K, P=1.0 atm, amounts {'O': 1.0, 'C': 1.0} |
| TestThermo08 | refused | input not accepted: T=300.0 K, P=-1.0 atm, amounts {'O': 1.0, 'C': 1.0} |
| TestThermo09 | refused | input not accepted: T=300.0 K, P=1.0 atm, amounts {'O': -1.0, 'C': -1.0} |
| TestThermo10 | refused | input not accepted: T=300.0 K, P=nan atm, amounts {'O': 1.0, 'C': 1.0} |
| TestThermo11 | refused | input not accepted: T=1e+37 K, P=0.0 atm, amounts {'O': 1.0, 'C': 1.0} |
| TestThermo12 | refused | input not accepted: T=300.0 K, P=1.0 atm, amounts {} |
| TestThermo13 | refused | input not accepted: T=300.0 K, P=1.0 atm, unit elephants |
| TestThermo30 | close | G relative difference 1.50e-06 |
| TestThermo31 | disagree | phases ['DELETE', 'DELETE'] vs ['DELETE'] |
| TestThermo32 | disagree | phases ['QUATERNARY', 'QUATERNARY', 'QUATERNARY'] vs ['QUATERNARY'] |
| TestThermo33 | agree | G relative difference 2.76e-07 |
| TestThermo40 | agree | G relative difference 1.59e-07 |
| TestThermo41 | agree | G relative difference 7.02e-07 |
| TestThermo42 | agree | G relative difference 2.11e-07 |
| TestThermo43 | agree | G relative difference 9.98e-08 |
| TestThermo44 | agree | G relative difference 4.96e-07 |
| TestThermo45 | agree | G relative difference 3.59e-08 |
| TestThermo46 | agree | G relative difference 2.91e-07 |
| TestThermo47 | agree | G relative difference 4.33e-07 |
| TestThermo48 | agree | G relative difference 2.90e-07 |
| TestThermo49 | agree | G relative difference 1.53e-07 |
| TestThermo50 | agree | G relative difference 3.59e-08 |
| TestThermo51 | agree | G relative difference 2.91e-07 |
| TestThermo52 | agree | G relative difference 4.33e-07 |
| TestThermo53 | agree | G relative difference 3.32e-07 |
| TestThermo54 | agree | G relative difference 1.46e-07 |
| TestThermo55 | disagree | phases ['BCC_A2', 'BCC_A2', 'FCC_A1', 'FESN_B35', 'GAS'] vs ['BCC_A2', 'FCC_A1', 'FESN_B35', 'GAS'] |
| TestThermo56 | agree | G relative difference 1.24e-07 |
| TestThermo57 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo58 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo59 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo60 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo61 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo62 | disagree | G relative difference 1.27e-03 |
| TestThermo63 | disagree | phases ['MSSOLN', 'MSSOLN'] vs ['MSSOLN', 'NACL_S1(S)'] |
| TestThermo64 | disagree | phases ['BCC_A2', 'BCC_A2', 'BCC_A2'] vs ['BCC_A2'] |
| TestThermo65 | agree | G relative difference 5.16e-07 |
| TestThermo70 | agree | G relative difference 2.93e-08 |
| TestThermo71 | disagree | phases ['HCP_A3', 'IONIC_LIQ'] vs ['HCP_ORD', 'IONIC_LIQ'] |
| TestThermo72 | agree | G relative difference 2.28e-07 |
| TestThermo73 | agree | G relative difference 9.71e-08 |
| TestThermo74 | close | G relative difference 3.24e-05 |
| TestThermo75 | agree | G relative difference 4.14e-07 |
| TestThermo76 | agree | G relative difference 9.54e-08 |
| TestThermo77 | close | G relative difference 4.83e-06 |
| TestThermo78 | refused | failed to read ChemSage database: line 339: SUBI reciprocal term of two cations with Va and a neutral with more than one parameter |
| TestThermo80 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo81 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo82 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo83 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo84 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo85 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo86 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo87 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo88 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo89 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo90 | agree | G relative difference 0.00e+00 |
| TestThermo30__grid1 | disagree | phases ['DELETE', 'DELETE'] vs ['DELETE'] |
| TestThermo30__grid2 | disagree | phases ['DELETE', 'DELETE'] vs ['DELETE'] |
| TestThermo30__grid3 | close | G relative difference 1.50e-06 |
| TestThermo30__grid4 | close | G relative difference 1.23e-06 |
| TestThermo30__grid5 | agree | G relative difference 8.39e-07 |
| TestThermo31__grid1 | disagree | phases ['DELETE', 'DELETE'] vs ['DELETE'] |
| TestThermo31__grid2 | disagree | phases ['DELETE', 'DELETE'] vs ['DELETE'] |
| TestThermo31__grid3 | disagree | phases ['DELETE', 'DELETE'] vs ['DELETE'] |
| TestThermo31__grid4 | disagree | phases ['DELETE', 'DELETE'] vs ['DELETE'] |
| TestThermo31__grid5 | disagree | phases ['DELETE', 'DELETE'] vs ['DELETE'] |
| TestThermo32__grid1 | disagree | phases ['QUATERNARY', 'QUATERNARY', 'QUATERNARY'] vs ['QUATERNARY'] |
| TestThermo32__grid2 | disagree | phases ['QUATERNARY', 'QUATERNARY', 'QUATERNARY'] vs ['QUATERNARY'] |
| TestThermo32__grid3 | disagree | phases ['QUATERNARY', 'QUATERNARY', 'QUATERNARY'] vs ['QUATERNARY'] |
| TestThermo32__grid4 | disagree | phases ['QUATERNARY', 'QUATERNARY', 'QUATERNARY'] vs ['QUATERNARY'] |
| TestThermo32__grid5 | disagree | phases ['QUATERNARY', 'QUATERNARY', 'QUATERNARY'] vs ['QUATERNARY'] |
| TestThermo33__grid1 | agree | G relative difference 1.58e-07 |
| TestThermo33__grid2 | agree | G relative difference 2.22e-07 |
| TestThermo33__grid3 | agree | G relative difference 2.76e-07 |
| TestThermo33__grid4 | agree | G relative difference 3.82e-07 |
| TestThermo33__grid5 | agree | G relative difference 6.58e-07 |
| TestThermo40__grid1 | agree | G relative difference 1.80e-07 |
| TestThermo40__grid2 | agree | G relative difference 1.83e-07 |
| TestThermo40__grid3 | agree | G relative difference 1.59e-07 |
| TestThermo40__grid4 | agree | G relative difference 1.31e-07 |
| TestThermo40__grid5 | agree | G relative difference 2.06e-07 |
| TestThermo41__grid1 | agree | G relative difference 2.78e-07 |
| TestThermo41__grid2 | agree | G relative difference 6.50e-07 |
| TestThermo41__grid3 | agree | G relative difference 7.02e-07 |
| TestThermo41__grid4 | agree | G relative difference 2.87e-07 |
| TestThermo41__grid5 | agree | G relative difference 2.80e-07 |
| TestThermo42__grid1 | agree | G relative difference 2.14e-07 |
| TestThermo42__grid2 | agree | G relative difference 2.13e-07 |
| TestThermo42__grid3 | agree | G relative difference 2.11e-07 |
| TestThermo42__grid4 | agree | G relative difference 2.53e-07 |
| TestThermo42__grid5 | agree | G relative difference 1.78e-07 |
| TestThermo43__grid2 | agree | G relative difference 7.64e-08 |
| TestThermo43__grid3 | agree | G relative difference 9.98e-08 |
| TestThermo43__grid4 | agree | G relative difference 1.16e-07 |
| TestThermo43__grid5 | agree | G relative difference 1.27e-07 |
| TestThermo44__grid1 | agree | G relative difference 4.58e-07 |
| TestThermo44__grid2 | agree | G relative difference 4.59e-07 |
| TestThermo44__grid3 | agree | G relative difference 4.96e-07 |
| TestThermo44__grid4 | agree | G relative difference 4.41e-07 |
| TestThermo44__grid5 | agree | G relative difference 3.47e-07 |
| TestThermo45__grid1 | agree | G relative difference 3.88e-08 |
| TestThermo45__grid2 | agree | G relative difference 3.72e-08 |
| TestThermo45__grid3 | agree | G relative difference 3.59e-08 |
| TestThermo45__grid4 | agree | G relative difference 3.47e-08 |
| TestThermo45__grid5 | agree | G relative difference 3.36e-08 |
| TestThermo46__grid1 | agree | G relative difference 3.02e-07 |
| TestThermo46__grid2 | agree | G relative difference 2.96e-07 |
| TestThermo46__grid3 | agree | G relative difference 2.91e-07 |
| TestThermo46__grid4 | agree | G relative difference 2.86e-07 |
| TestThermo46__grid5 | agree | G relative difference 2.81e-07 |
| TestThermo47__grid1 | agree | G relative difference 4.45e-07 |
| TestThermo47__grid2 | agree | G relative difference 4.39e-07 |
| TestThermo47__grid3 | agree | G relative difference 4.33e-07 |
| TestThermo47__grid4 | agree | G relative difference 4.05e-07 |
| TestThermo47__grid5 | agree | G relative difference 3.94e-07 |
| TestThermo48__grid1 | agree | G relative difference 3.13e-07 |
| TestThermo48__grid2 | agree | G relative difference 3.08e-07 |
| TestThermo48__grid3 | agree | G relative difference 2.90e-07 |
| TestThermo48__grid4 | agree | G relative difference 2.80e-07 |
| TestThermo48__grid5 | agree | G relative difference 2.78e-07 |
| TestThermo49__grid1 | agree | G relative difference 1.64e-07 |
| TestThermo49__grid2 | agree | G relative difference 1.62e-07 |
| TestThermo49__grid3 | agree | G relative difference 1.53e-07 |
| TestThermo49__grid4 | agree | G relative difference 4.07e-07 |
| TestThermo49__grid5 | agree | G relative difference 1.48e-07 |
| TestThermo50__grid1 | agree | G relative difference 3.88e-08 |
| TestThermo50__grid2 | agree | G relative difference 3.72e-08 |
| TestThermo50__grid3 | agree | G relative difference 3.59e-08 |
| TestThermo50__grid4 | agree | G relative difference 3.47e-08 |
| TestThermo50__grid5 | agree | G relative difference 3.36e-08 |
| TestThermo51__grid1 | agree | G relative difference 3.02e-07 |
| TestThermo51__grid2 | agree | G relative difference 2.96e-07 |
| TestThermo51__grid3 | agree | G relative difference 2.91e-07 |
| TestThermo51__grid4 | agree | G relative difference 2.86e-07 |
| TestThermo51__grid5 | agree | G relative difference 2.81e-07 |
| TestThermo52__grid1 | agree | G relative difference 4.45e-07 |
| TestThermo52__grid2 | agree | G relative difference 4.39e-07 |
| TestThermo52__grid3 | agree | G relative difference 4.33e-07 |
| TestThermo52__grid4 | agree | G relative difference 4.05e-07 |
| TestThermo52__grid5 | agree | G relative difference 3.94e-07 |
| TestThermo53__grid1 | agree | G relative difference 3.17e-07 |
| TestThermo53__grid2 | agree | G relative difference 3.26e-07 |
| TestThermo53__grid3 | agree | G relative difference 3.32e-07 |
| TestThermo53__grid4 | agree | G relative difference 3.34e-07 |
| TestThermo53__grid5 | agree | G relative difference 3.34e-07 |
| TestThermo54__grid1 | agree | G relative difference 1.46e-07 |
| TestThermo54__grid2 | agree | G relative difference 1.54e-07 |
| TestThermo54__grid3 | agree | G relative difference 1.46e-07 |
| TestThermo54__grid4 | agree | G relative difference 1.56e-07 |
| TestThermo54__grid5 | agree | G relative difference 2.54e-07 |
| TestThermo55__grid3 | disagree | phases ['BCC_A2', 'BCC_A2', 'FCC_A1', 'FESN_B35', 'GAS'] vs ['BCC_A2', 'FCC_A1', 'FESN_B35', 'GAS'] |
| TestThermo55__grid4 | disagree | phases ['BCC_A2', 'BCC_A2', 'FCC_A1', 'FESN_B35', 'GAS'] vs ['BCC_A2', 'FCC_A1', 'FESN_B35', 'GAS'] |
| TestThermo55__grid5 | disagree | phases ['BCC_A2', 'BCC_A2', 'FCC_A1', 'FESN_B35', 'GAS'] vs ['BCC_A2', 'FCC_A1', 'FESN_B35', 'GAS'] |
| TestThermo56__grid1 | agree | G relative difference 1.00e-07 |
| TestThermo56__grid2 | agree | G relative difference 1.17e-07 |
| TestThermo56__grid3 | agree | G relative difference 1.24e-07 |
| TestThermo56__grid4 | agree | G relative difference 1.65e-07 |
| TestThermo56__grid5 | agree | G relative difference 1.80e-07 |
| TestThermo57__grid1 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo57__grid2 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo57__grid3 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo57__grid4 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo57__grid5 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo58__grid1 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo58__grid2 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo58__grid3 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo58__grid4 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo58__grid5 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo59__grid1 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo59__grid2 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo59__grid3 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo59__grid4 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo59__grid5 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo60__grid1 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo60__grid2 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo60__grid3 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo60__grid4 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo60__grid5 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo61__grid1 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo61__grid2 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo61__grid3 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo61__grid4 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo61__grid5 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo62__grid1 | disagree | G relative difference 1.26e-03 |
| TestThermo62__grid2 | disagree | G relative difference 1.26e-03 |
| TestThermo62__grid3 | disagree | G relative difference 1.27e-03 |
| TestThermo62__grid4 | disagree | G relative difference 1.28e-03 |
| TestThermo62__grid5 | disagree | G relative difference 1.29e-03 |
| TestThermo63__grid1 | disagree | G relative difference 5.37e-04 |
| TestThermo63__grid2 | disagree | G relative difference 7.47e-04 |
| TestThermo63__grid3 | disagree | phases ['MSSOLN', 'MSSOLN'] vs ['MSSOLN', 'NACL_S1(S)'] |
| TestThermo63__grid4 | disagree | phases ['MSSOLN', 'MSSOLN'] vs ['MSSOLN'] |
| TestThermo63__grid5 | disagree | G relative difference 1.37e-03 |
| TestThermo64__grid1 | disagree | phases ['BCC_A2', 'BCC_A2', 'BCC_A2'] vs ['BCC_A2'] |
| TestThermo64__grid2 | disagree | phases ['BCC_A2', 'BCC_A2', 'BCC_A2'] vs ['BCC_A2'] |
| TestThermo64__grid3 | disagree | phases ['BCC_A2', 'BCC_A2', 'BCC_A2'] vs ['BCC_A2'] |
| TestThermo64__grid4 | disagree | phases ['BCC_A2', 'BCC_A2', 'BCC_A2'] vs ['BCC_A2'] |
| TestThermo64__grid5 | disagree | phases ['BCC_A2', 'BCC_A2', 'BCC_A2'] vs ['BCC_A2'] |
| TestThermo65__grid2 | agree | G relative difference 4.99e-07 |
| TestThermo65__grid3 | agree | G relative difference 5.16e-07 |
| TestThermo65__grid4 | agree | G relative difference 5.42e-07 |
| TestThermo65__grid5 | close | G relative difference 5.69e-05 |
| TestThermo70__grid1 | agree | G relative difference 8.21e-09 |
| TestThermo70__grid2 | agree | G relative difference 2.74e-08 |
| TestThermo70__grid3 | agree | G relative difference 2.93e-08 |
| TestThermo70__grid4 | agree | G relative difference 3.27e-08 |
| TestThermo70__grid5 | agree | G relative difference 3.74e-08 |
| TestThermo71__grid1 | disagree | phases ['HCP_A3', 'IONIC_LIQ'] vs ['HCP_ORD', 'IONIC_LIQ'] |
| TestThermo71__grid2 | disagree | phases ['HCP_A3', 'IONIC_LIQ'] vs ['HCP_ORD', 'IONIC_LIQ'] |
| TestThermo71__grid3 | disagree | phases ['HCP_A3', 'IONIC_LIQ'] vs ['HCP_ORD', 'IONIC_LIQ'] |
| TestThermo71__grid4 | disagree | phases ['HCP_A3', 'IONIC_LIQ'] vs ['HCP_ORD', 'IONIC_LIQ'] |
| TestThermo71__grid5 | disagree | phases ['HCP_A3', 'IONIC_LIQ'] vs ['HCP_ORD', 'IONIC_LIQ'] |
| TestThermo72__grid1 | agree | G relative difference 0.00e+00 |
| TestThermo72__grid2 | agree | G relative difference 1.98e-07 |
| TestThermo72__grid3 | agree | G relative difference 2.28e-07 |
| TestThermo72__grid4 | agree | G relative difference 1.93e-07 |
| TestThermo72__grid5 | agree | G relative difference 6.05e-08 |
| TestThermo73__grid1 | agree | G relative difference 8.06e-08 |
| TestThermo73__grid2 | agree | G relative difference 8.88e-08 |
| TestThermo73__grid3 | agree | G relative difference 9.71e-08 |
| TestThermo73__grid4 | agree | G relative difference 1.05e-07 |
| TestThermo73__grid5 | close | G relative difference 1.17e-07 |
| TestThermo74__grid1 | close | G relative difference 3.58e-05 |
| TestThermo74__grid2 | close | G relative difference 3.40e-05 |
| TestThermo74__grid3 | close | G relative difference 3.24e-05 |
| TestThermo74__grid4 | close | G relative difference 3.08e-05 |
| TestThermo74__grid5 | close | G relative difference 2.94e-05 |
| TestThermo75__grid1 | agree | G relative difference 4.45e-07 |
| TestThermo75__grid2 | agree | G relative difference 4.29e-07 |
| TestThermo75__grid3 | agree | G relative difference 4.14e-07 |
| TestThermo75__grid4 | agree | G relative difference 4.05e-07 |
| TestThermo75__grid5 | agree | G relative difference 3.93e-07 |
| TestThermo76__grid1 | agree | G relative difference 8.90e-08 |
| TestThermo76__grid2 | agree | G relative difference 9.23e-08 |
| TestThermo76__grid3 | agree | G relative difference 9.54e-08 |
| TestThermo76__grid4 | agree | G relative difference 9.83e-08 |
| TestThermo76__grid5 | agree | G relative difference 1.07e-07 |
| TestThermo77__grid1 | close | G relative difference 3.96e-06 |
| TestThermo77__grid2 | close | G relative difference 4.43e-06 |
| TestThermo77__grid3 | close | G relative difference 4.83e-06 |
| TestThermo77__grid4 | close | G relative difference 5.25e-06 |
| TestThermo77__grid5 | close | G relative difference 5.63e-06 |
| TestThermo78__grid1 | refused | failed to read ChemSage database: line 339: SUBI reciprocal term of two cations with Va and a neutral with more than one parameter |
| TestThermo78__grid2 | refused | failed to read ChemSage database: line 339: SUBI reciprocal term of two cations with Va and a neutral with more than one parameter |
| TestThermo78__grid3 | refused | failed to read ChemSage database: line 339: SUBI reciprocal term of two cations with Va and a neutral with more than one parameter |
| TestThermo78__grid4 | refused | failed to read ChemSage database: line 339: SUBI reciprocal term of two cations with Va and a neutral with more than one parameter |
| TestThermo78__grid5 | refused | failed to read ChemSage database: line 339: SUBI reciprocal term of two cations with Va and a neutral with more than one parameter |
| TestThermo80__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo80__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo80__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo80__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo80__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo81__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo81__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo81__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo81__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo81__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo82__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo82__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo82__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo82__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo82__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo83__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo83__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo83__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo83__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo83__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo84__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo84__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo84__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo84__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo84__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo85__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo85__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo85__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo85__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo85__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo86__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo86__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo86__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo86__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo86__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo87__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo87__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo87__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo87__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo87__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo88__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo88__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo88__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo88__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo88__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo89__grid1 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo89__grid2 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo89__grid3 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo89__grid4 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo89__grid5 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo90__grid1 | agree | G relative difference 1.42e-16 |
| TestThermo90__grid2 | agree | G relative difference 0.00e+00 |
| TestThermo90__grid3 | agree | G relative difference 0.00e+00 |
| TestThermo90__grid4 | agree | G relative difference 1.27e-16 |
| TestThermo90__grid5 | agree | G relative difference 5.84e-07 |

## Against the reference values in Thermochimica's tests

| Class | Count |
|---|---|
| agree | 15 |
| close | 14 |
| disagree | 7 |
| refused | 27 |

| Point | Class | Detail |
|---|---|---|
| TestSUBQNonuniformZeta | refused | the test changes the database in memory after reading it |
| TestThermo03 | disagree | Hephaestus computed an input the test requires to be refused |
| TestThermo04 | refused | input not accepted: T=None K, P=1.0 atm, unit moles |
| TestThermo05 | refused | input not accepted: T=300.0 K, P=None atm, unit moles |
| TestThermo06 | refused | input not accepted: T=2000.0 K, P=1.0 atm, amounts {} |
| TestThermo07 | refused | input not accepted: T=-300.0 K, P=1.0 atm, amounts {'O': 1.0, 'C': 1.0} |
| TestThermo08 | refused | input not accepted: T=300.0 K, P=-1.0 atm, amounts {'O': 1.0, 'C': 1.0} |
| TestThermo09 | refused | input not accepted: T=300.0 K, P=1.0 atm, amounts {'O': -1.0, 'C': -1.0} |
| TestThermo10 | refused | input not accepted: T=300.0 K, P=nan atm, amounts {'O': 1.0, 'C': 1.0} |
| TestThermo11 | refused | input not accepted: T=1e+37 K, P=0.0 atm, amounts {'O': 1.0, 'C': 1.0} |
| TestThermo12 | refused | input not accepted: T=300.0 K, P=1.0 atm, amounts {} |
| TestThermo13 | refused | input not accepted: T=300.0 K, P=1.0 atm, unit elephants |
| TestThermo14 | agree |  |
| TestThermo30 | close | G relative difference 8.23e-05 |
| TestThermo31 | disagree | G relative difference 5.83e-01 |
| TestThermo32 | disagree | G relative difference 1.52e+00 |
| TestThermo33 | agree | G relative difference 8.14e-07 |
| TestThermo40 | close | G relative difference 2.87e-06 |
| TestThermo41 | close | G relative difference 2.63e-06 |
| TestThermo42 | close | G relative difference 3.03e-06 |
| TestThermo43 | close | G relative difference 2.09e-06 |
| TestThermo44 | agree | G relative difference 3.08e-07 |
| TestThermo45 | agree | G relative difference 7.05e-08 |
| TestThermo46 | agree | G relative difference 3.86e-07 |
| TestThermo47 | close | G relative difference 3.86e-06 |
| TestThermo48 | close | G relative difference 4.10e-06 |
| TestThermo49 | close | G relative difference 2.69e-06 |
| TestThermo50 | agree | G relative difference 7.05e-08 |
| TestThermo51 | agree | G relative difference 3.86e-07 |
| TestThermo52 | close | G relative difference 3.86e-06 |
| TestThermo53 | close | G relative difference 1.14e-06 |
| TestThermo54 | agree | G relative difference 4.94e-08 |
| TestThermo55 | disagree | G relative difference 4.13e-02 |
| TestThermo56 | close | G relative difference 1.22e-06 |
| TestThermo57 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo58 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo59 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo60 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo61 | refused | phase SLAGBSOLN carries chemical-group override strings, which change the mixed chemical-group excess interpolation; mixed chemical groups are not supported, so |
| TestThermo62 | disagree | G relative difference 1.27e-03 |
| TestThermo63 | disagree | G relative difference 8.61e-04 |
| TestThermo64 | disagree | G relative difference 9.69e-03 |
| TestThermo65 | close | G relative difference 1.29e-07 |
| TestThermo70 | agree | G relative difference 7.05e-07 |
| TestThermo71 | close | G relative difference 1.01e-06 |
| TestThermo72 | agree | G relative difference 3.89e-07 |
| TestThermo73 | agree | G relative difference 1.15e-07 |
| TestThermo74 | close | G relative difference 2.46e-06 |
| TestThermo75 | agree | G relative difference 8.41e-07 |
| TestThermo76 | agree | G relative difference 3.89e-07 |
| TestThermo77 | agree | G relative difference 7.78e-07 |
| TestThermo78 | refused | failed to read ChemSage database: line 339: SUBI reciprocal term of two cations with Va and a neutral with more than one parameter |
| TestThermo80 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo81 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo82 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo83 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo84 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo85 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo86 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo87 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo88 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo89 | refused | failed to read ChemSage database: phase TESTSOLN is SUBM, which is not read: how a ChemSage file records its excess terms is not documented in any source the en |
| TestThermo90 | agree | G relative difference 7.52e-07 |
