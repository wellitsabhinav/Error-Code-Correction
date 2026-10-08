# Historical GREENS evidence archives

Binary archives live on D:/GREENS_ARCHIVES and are deliberately outside Git. [MANIFEST.csv](MANIFEST.csv) records original paths, date ranges, sizes, counts, SHA256 and scientific milestones. [manifests/](manifests/) contains byte-preserved per-member verification records, including negative/partial OpenRAM evidence.

Verify an archive before restoring it:

```powershell
python scripts/verify_greens_archive.py --archive D:/GREENS_ARCHIVES/physical_validation/green-ecc-gate04-runs.tar.gz --manifest archives/manifests/green-ecc-gate04-runs.tar.gz.manifest.json
```

For WSL, replace the archive drive prefix with `/mnt/d/GREENS_ARCHIVES`. Extract into an empty directory dedicated to that campaign (`tar -xzf ARCHIVE -C CAMPAIGN_RESTORE_DIR`). Each archive contains its original `runs`, `fresh_runs`, `work`, `evidence` or `output` root. Restore the original campaign layout only when reproducing the historical workflow. The archive verifier checks hashes and contents without extracting files.

16 archives, 15,007 regular files, 22,081,140,483 original bytes and 3,819,867,327 compressed bytes. Dependency installations/PDKs were not archived.
