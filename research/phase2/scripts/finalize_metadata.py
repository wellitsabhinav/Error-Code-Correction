"""Index shared artifacts by content identity and record sampled resource totals."""
from __future__ import annotations
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from common import PHASE, ROOT, sha256, write_json, write_csv


def main():
    baseline=json.loads((PHASE/'baseline_manifest.json').read_text())
    refs={}
    for record in baseline['baseline_files']:
        refs.setdefault(record['sha256'],[]).append({'path':record['path'],'available':True,'kind':'EXISTING_BASELINE_REFERENCE','git_blob':record['git_blob']})
    archived=json.loads((PHASE/'manifests/archived_physical_references.json').read_text())
    for record in archived['selected_members']:
        refs.setdefault(record['sha256'],[]).append({'archive':archived['archive_path'],'member':record['path'],'available':False,'kind':'MISSING_ARCHIVE_MEMBER_REFERENCE'})
    write_json(PHASE/'manifests/artifact_references.json',{'algorithm':'sha256','objects':refs,
               'policy':'Reference existing immutable objects in place; do not copy one physical object per power method. Hash conflicts retain separate identities.'})
    minimal=json.loads((PHASE/'manifests/sky130_minimal_sources.json').read_text())
    for record in minimal['files']:
        record['local_sha256']=sha256(ROOT/record['path'])
        record['local_bytes']=(ROOT/record['path']).stat().st_size
    write_json(PHASE/'manifests/sky130_minimal_sources.json',minimal)
    paths={'linux_iverilog_package':Path('F:/AgenticAI/.local/m9-icarus-linux/iverilog_12.0-2build2_amd64.deb'),
           'linux_iverilog':Path('F:/AgenticAI/.local/m9-icarus-linux/extracted/usr/bin/iverilog'),
           'linux_vvp':Path('F:/AgenticAI/.local/m9-icarus-linux/extracted/usr/bin/vvp')}
    toolchain={'python':sys.version,'git':subprocess.check_output(['git','--version'],text=True).strip(),
               'host_platform':platform.platform(),'simulator':'Icarus Verilog 12.0 stable; existing extracted Ubuntu package',
               'wsl_distribution':'AutonomousEDA','max_parallel_jobs':1,
               'existing_orfs_image_digest':'8eff077230b86729f6248b34eeab370e486fa4052d34c60d9067e3e4aa720987',
               'baseline_orfs_image_digest':'f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e',
               'current_liberty_sha256':'ec0e1067a35c8bf20b11e58d1e8ac53326067e4dac84a125cc1b917a3518d0d9',
               'current_liberty_matches_frozen':True,'openroad_version':'unknown (literal tool output)',
               'installed_new_dependencies_bytes':0,
               'files':{k:{'path':str(p),'sha256':sha256(p),'bytes':p.stat().st_size} for k,p in paths.items() if p.is_file()},
               'baseline_technology':baseline['technology']}
    write_json(PHASE/'configs/toolchain.json',toolchain)
    compression=json.loads((PHASE/'manifests/compression.json').read_text())
    included=[p for p in PHASE.rglob('*') if p.is_file() and not any(x in p.relative_to(PHASE).parts for x in ('scratch','__pycache__','.pytest_cache'))]
    initial=json.loads((PHASE/'raw/environment/initial_storage.json').read_text())
    summary={'initial_host_free_bytes':{'C':initial['C_free_bytes'],'G':initial['G_free_bytes']},
             'final_host_free_bytes':{d:shutil.disk_usage(d+':/').free for d in ('C','G','F')},
             'retained_phase2_bytes_as_sampled':sum(p.stat().st_size for p in included),'retained_phase2_files_as_sampled':len(included),
             'experimental_continuous_peak_bytes':None,'sampled_git_temporary_pack_max_bytes':initial['sampled_git_temporary_pack_max_bytes'],
             'compression_saved_bytes':compression['saved_bytes'],'deduplication_deletion_saved_bytes':0,
             'production_streaming_saved_bytes':None,'installed_dependencies_bytes':0,'public_qualification_source_download_bytes':22492,
             'note':'Sampled file lengths and host free bytes; unrelated host activity and Git acquisition overhead are separate. Missing peak/savings metrics are null.'}
    write_json(PHASE/'processed/storage_summary.json',summary)
    statuses=[{'gate':'P2-G00','status':'BLOCKED','reason':'Synthetic IOPATH passed; interconnect/timing checks/full-cell coverage and physical artifact readiness fail.'},
              {'gate':'P2-G01','status':'BLOCKED','reason':'P2-G00 prerequisite failed; no matched physical A/B/C evaluation.'},
              {'gate':'P2-G02','status':'BLOCKED','reason':'Production event/capacitance mechanism study blocked; independent historical accounting completed.'},
              {'gate':'P2-G03','status':'BLOCKED','reason':'No qualified physical energy flow; input/software/RTL preparation only.'}]
    write_json(PHASE/'experiments/gate_status.json',{'gates':statuses,'research_branch':'DEFERRED_PREREQUISITE_FAILURE'})
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
