# Data provenance audit

Three original ZIPs are read in place and rehashed each build; full dimensions, citation, size, modification time and audit time are in `raw_input_audit.json`. No ZIP is copied to the new directory or staged in Git.

- incidence: `E:\工作目录\China-PA-13\Analysis\new_study\round1_20261112\handoff\continuation\source_data\gbd\IHME-GBD_2023_DATA-85af7c45-1.zip`; SHA256 `64e613442f4269bb79ff36e26a7069ad5da36a1abc8de566be58f49c3aa6805e`; rows 4624.
- disease: `E:\工作目录\China-PA-13\Analysis\new_study\round4_dynamic_health_model_20261112\raw\IHME-GBD_2023_DATA-353a02a2-1.zip`; SHA256 `9ba35729cab5994ad9ce05427228c71b127d8b4bf03db899681ef250b2a5e2b7`; rows 800.
- all_cause: `E:\工作目录\China-PA-13\Analysis\new_study\round4_dynamic_health_model_20261112\raw\IHME-GBD_2023_DATA-52b38bf7-1.zip`; SHA256 `dd38441e963a02f9f572afb56c8f2d4dfb39b58bc48b1c7ebff28d0c09fe835e`; rows 400.

Cross-export population: 32 sex-age rows, maximum relative difference 5.24898777329e-13. WPP 2025 comparison is external and not an equality gate against GBD 2023.

`F1SO})17CY[B2_I9SF$J{OC.png` is INCOMPLETE_QUERY_SCREENSHOT_NOT_USED and was not copied. Complete-final-query screenshot remains unavailable; original export dimensions and citation are retained.
