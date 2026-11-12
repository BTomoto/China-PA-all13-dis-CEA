# IHD and ischemic-stroke health pilot

From repository root, run `python new_study/round3_health_model_pilot_20261112/build_deliverables.py`. It copies and checksum-verifies the GBD 2023 source ZIP, rebuilds the WPP/exposure scenario and incidence results, runs 10 tests, and refreshes the SHA256 manifest. Use the five numbered notebooks in order for interactive reproduction.

Read `METHODS.md` for definitions and `HANDOFF_HEALTH_MODEL_PILOT.md` for results and open dynamic parameters. Outputs are unrounded expected case counts; reporting may round them.
