# Round6 local comparative-risk run

Worktree: `E:\工作目录\China-PA-13\Analysis`.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r new_study\round6_multiscenario_cra\requirements.txt
.\new_study\round6_multiscenario_cra\run_local.ps1
```

The root runner remains the round-five runner and is unchanged. The round-six runner imports only this directory's CRA functions and runs only its tests plus five real nbclient/ipykernel notebooks. It executes no previous natural-history, cost, economic PSA or CEA code. Normal execution performs no network access or downloads.

Original byte-matched inputs must remain at the local paths in `config/source_lock.json`. Individual exposure data is not included or uploaded. Read `reports/HANDOFF_ROUND6.md` for separate scenario identification and endpoint admission gates. Missing effects stay blank.
