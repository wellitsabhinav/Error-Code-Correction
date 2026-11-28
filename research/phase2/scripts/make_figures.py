"""Regenerate only figures supported by available evidence; no empty-result plots."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from common import PHASE, ROOT, sha256, write_json, write_csv

plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
                     'svg.hashsalt': 'phase2-20261128', 'axes.spines.top': False, 'axes.spines.right': False})
OUT = PHASE / 'figures'
BLUE, ORANGE, GRAY = '#21618c', '#b35c19', '#59636e'
manifest = []


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def save(fig, name, sources, classification):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ('pdf', 'svg', 'png'):
        path=OUT / f'{name}.{ext}'
        metadata={'Date':None} if ext=='svg' else ({'CreationDate':None,'ModDate':None} if ext=='pdf' else {})
        fig.savefig(path, bbox_inches='tight', dpi=180, metadata=metadata)
        if ext=='svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    manifest.append({'name': name, 'classification': classification,
                     'sources': {str(Path(s).relative_to(ROOT)).replace('\\', '/'): sha256(s) for s in sources}})
    plt.close(fig)


def arrow(ax, x1, y1, x2, y2, color=GRAY):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1), arrowprops={'arrowstyle': '->', 'lw': 1.3, 'color': color})


def reg(ax, x, y, label, color=BLUE):
    ax.plot([x,x], [y-.22,y+.22], color=color, lw=2)
    ax.plot([x+.06,x+.06], [y-.22,y+.22], color=color, lw=2)
    ax.text(x+.03,y-.34,label,ha='center',va='top',fontsize=8,color=color)


def architectures():
    fig, ax = plt.subplots(figsize=(12,5))
    ax.set(xlim=(0,12),ylim=(-.3,4.1)); ax.axis('off')
    ax.text(0,3.85,'SECDED encoder: exact register cuts in the evaluated shells',fontsize=13,weight='bold')
    ax.text(0,3.15,'Combinational',weight='bold'); reg(ax,2,3,'input shell')
    ax.text(5.1,3,'positional Hamming parity\n+ overall parity',ha='center',va='center')
    arrow(ax,2.15,3,3.65,3);arrow(ax,6.6,3,9.65,3);reg(ax,9.7,3,'output shell')
    ax.text(11.8,3,'1 cycle\nII = 1',ha='right',va='center')
    ax.text(0,1.7,'Pipelined',weight='bold'); reg(ax,2,1.55,'input shell')
    ax.text(3.45,1.55,'7 parity trees\n9 × 8-bit groups',ha='center',va='center',fontsize=9)
    arrow(ax,2.15,1.55,2.6,1.55);reg(ax,4.65,1.55,'positional_q')
    arrow(ax,4.85,1.55,5.1,1.55)
    ax.text(6.0,1.55,'overall XOR parity\n+ positional bits',ha='center',va='center',fontsize=8)
    reg(ax,7.45,1.55,'stage2_codeword_q');arrow(ax,7.6,1.55,9.65,1.55);reg(ax,9.7,1.55,'output shell')
    ax.text(11.8,1.55,'3 cycles\nII = 1',ha='right',va='center')
    ax.text(0,.4,'Decoder core cut: syndrome_q + overall_mismatch_q + received_q → classification → correction mask → XOR/data extraction → data_q.',fontsize=9)
    ax.text(0,0,'Core registers have no reset. Shell reset is synchronous active-low; valid travels with results. Encoder and decoder are independent channels.',fontsize=9)
    save(fig,'01_pipeline_registers',[ROOT/'asic/rtl/secded/secded_pipelined_72_64_v1.sv',ROOT/'scripts/gate04/rtl/gate04_boundaries.sv'],'RTL_STRUCTURE_NOT_TIMING_MEASUREMENT')

    fig,ax=plt.subplots(figsize=(10,3.7));ax.axis('off');ax.set(xlim=(0,10),ylim=(0,3.7))
    ax.text(0,3.4,'Hsiao correction of payload bit 0: H column = 0x07',fontsize=13,weight='bold')
    ax.text(.2,2.5,'syndrome[7:0]',va='center');arrow(ax,1.8,2.5,2.4,2.5)
    ax.text(4.15,2.5,"Flat: syndrome == 8'h07",ha='center',va='center')
    arrow(ax,6,2.5,7.5,2.5);ax.text(8.6,2.5,'column_match[0]',ha='center',va='center')
    ax.text(.2,1.2,'syndrome[7:4] = 0\nsyndrome[3:0] = 7',va='center')
    arrow(ax,2.1,1.2,2.6,1.2);ax.text(4.35,1.2,'Hierarchical: high_match[0]\nAND low_match[7]',ha='center',va='center')
    arrow(ax,6.2,1.2,7.5,1.2);ax.text(8.6,1.2,'word[0] XOR\ncolumn_match[0]',ha='center',va='center')
    ax.text(.2,.15,'72 flat comparisons become shared 16-way high/low nibble decoders and 72 conjunctions; encoder and syndrome equations are shared.',fontsize=8)
    save(fig,'02_hsiao_circuit_example',[ROOT/'green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v2_algorithmic_decoder.sv',ROOT/'campaigns/date_2027_breadth_remediation/rtl/hsiao_secded_72_64_v3_hierarchical_decoder.sv'],'RTL_STRUCTURE')


def methods():
    fig,ax=plt.subplots(figsize=(11,4));ax.axis('off');ax.set(xlim=(0,11),ylim=(0,4))
    ax.text(0,3.7,'Three-way comparison contract — production runs blocked at P2-G00',fontsize=13,weight='bold')
    for y,m,activity in [(2.8,'A','Primary-input VCD → propagated activity'),(1.8,'B','Same routed netlist → zero-delay internal VCD'),(.8,'C','Same netlist + matched SDF → delayed internal VCD')]:
        ax.text(.1,y,m,fontsize=15,weight='bold',color=BLUE)
        ax.text(.7,y,activity,va='center',fontsize=10)
        arrow(ax,5.5,y,6.1,y)
        ax.text(7.3,y,'Mapping + coverage\n+ known-state checks',ha='center',va='center',fontsize=9)
        arrow(ax,8.5,y,9,y)
        ax.text(10,y,'Liberty + SPEF\nOpenSTA power\nE = P Δt / N',ha='center',va='center',fontsize=9)
    ax.text(.1,.05,'Matched workload, completed count, window, voltage, temperature and eligible frequency. C is a simulation reference, not silicon ground truth.',fontsize=8)
    save(fig,'03_estimator_contract',[PHASE/'configs/research.json'],'METHOD_CONTRACT_NO_RESULT')


def historical_plots():
    source=PHASE/'processed/historical_power_reanalysis.csv';rows=read_csv(source)
    fig,ax=plt.subplots(figsize=(6.2,4))
    for seed in (11,13,17,19,23):
        pair=[next(float(r['energy_per_op_pj']) for r in rows if int(r['seed'])==seed and r['architecture']==a) for a in ('secded_comb','secded_pipe')]
        ax.plot([0,1],pair,'o-',alpha=.8,label=f'Seed {seed}')
    ax.set(xticks=[0,1],xticklabels=['Combinational\n1 cycle','Pipelined\n3 cycles'],ylabel='Historical combined codec energy (pJ/op)',ylim=(0,170),title='Historical Method A at 100 MHz; five matched seeds')
    ax.legend(fontsize=8,ncol=2,loc='lower left');ax.grid(axis='y',alpha=.2)
    save(fig,'04_historical_paired_energy',[source],'HISTORICAL_PROPAGATED_ESTIMATE_NOT_A_B_C_COMPARISON')
    src=ROOT/'campaigns/date_2027_breadth_remediation/analysis/B_power_components_per_seed.csv';rows=read_csv(src)
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for ax,fields,labels in [(axs[0],['internal_power_w','switching_power_w'],['Internal','Switching']),
                             (axs[1],['combinational_total_power_w','sequential_total_power_w','clock_total_power_w'],['Combinational','Sequential','Clock'])]:
        for j,(arch,color) in enumerate([('secded_comb',BLUE),('secded_pipe',ORANGE)]):
            vals=[sum(float(r[f]) for r in rows if r['architecture']==arch)/5*1000 for f in fields]
            ax.bar([i+(j-.5)*.32 for i in range(len(fields))],vals,width=.32,label=arch.replace('secded_',''),color=color)
        ax.set(xticks=range(len(fields)),xticklabels=labels,ylabel='Mean historical power (mW)',ylim=(0,13));ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Historical Method A: component and cell-group partitions are separate views',fontsize=11)
    fig.tight_layout()
    save(fig,'05_historical_power_accounting',[src],'HISTORICAL_POWER_ACCOUNTING_NOT_CAUSAL_ATTRIBUTION')
    src=ROOT/'docs/date2027/revision2/results/REV2_RUN_RESULTS.csv';rows=read_csv(src)
    fig,axs=plt.subplots(1,2,figsize=(9,4))
    for arch,color,mark in [('secded_comb',BLUE,'o'),('secded_pipe',ORANGE,'s')]:
        r=[v for v in rows if v['architecture']==arch]
        area=[float(v['standard_cell_instance_area_um2'])/1000 for v in r]
        axs[0].scatter(area,[float(v['achievable_no_error_energy_pj_per_operation']) for v in r],color=color,marker=mark,label=arch)
        axs[1].scatter(area,[float(v['slack_derived_frequency_mhz']) for v in r],color=color,marker=mark)
    axs[0].set(xlabel='Cell area (1000 µm²)',ylabel='Historical energy (pJ/op)',ylim=(0,170),title='100 MHz, II = 1; latency 1 vs 3 cycles')
    axs[0].legend(fontsize=8)
    axs[1].set(xlabel='Cell area (1000 µm²)',ylabel='Signed-slack frequency estimate (MHz)',ylim=(0,450),title='Timing estimate; not measured Fmax')
    fig.tight_layout();save(fig,'06_historical_tradeoffs',[src],'HISTORICAL_FIVE_SEED_DESCRIPTIVE')


def qualification():
    source=PHASE/'raw/qualification_final/results.json';d=json.loads(source.read_text())
    selected=[r for r in d['results'] if r['label'] in ('zero','iopath_min','iopath_typ','iopath_max')]
    fig,axs=plt.subplots(1,2,figsize=(9,3.5))
    x=range(len(selected));labels=['Zero delay','Min','Typical','Max']
    axs[0].bar(x,[r['y_binary_transitions'] for r in selected],color=[GRAY,BLUE,BLUE,BLUE]);axs[0].set(xticks=x,xticklabels=labels,ylabel='Output binary transitions',ylim=(0,5))
    axs[1].bar(range(3),[r['y_min_pulse_ps']/1000 for r in selected[1:]],color=BLUE);axs[1].set(xticks=range(3),xticklabels=labels[1:],ylabel='High hazard pulse width (ns)',ylim=(0,3.2))
    fig.suptitle('Synthetic unequal-path XOR; controlled delays, no ECC power claim',fontsize=11);fig.tight_layout()
    save(fig,'07_synthetic_hazard',[source],'MEASURED_SIMULATOR_EVENTS_ARTIFICIAL_DELAYS')
    rows=[]
    for r in d['results']:
        rows.append({'configuration': r['label'], 'binary_transitions': r.get('y_binary_transitions'),
                     'minimum_pulse_ps': r.get('y_min_pulse_ps'), 'unknown_duration_ps': r.get('y_unknown_duration_ps'),
                     'scope': 'SYNTHETIC_QUALIFICATION_ONLY', 'completed_codec_operations': None})
    write_csv(PHASE/'processed/net_activity.csv',rows)


def workload_activity():
    src=PHASE/'processed/workload_characteristics.csv';rows=read_csv(src)
    fig,ax=plt.subplots(figsize=(8,3.7))
    ax.barh(range(len(rows)),[float(r['mean_hd']) for r in rows],color=BLUE)
    ax.set(yticks=range(len(rows)),yticklabels=[r['regime'].replace('_',' ') for r in rows],xlabel='Mean payload Hamming distance (bits / transition)',xlim=(0,64),title='1,000 deterministic payloads per regime; energy not measured')
    ax.grid(axis='x',alpha=.2);save(fig,'08_workload_activity',[src],'GENERATED_INPUT_CHARACTERISTICS_NO_ENERGY_RESULT')


def mapped_example():
    src=ROOT/'campaigns/date_2027_breadth_remediation/synthesis/baseline_flat/mapped_netlist.json'
    m=json.loads(src.read_text())['modules']['synthesized_top'];cells=m['cells']
    gates=[(n,c) for n,c in cells.items() if c['type']=='sky130_fd_sc_hd__xor2_1']
    first_name,first=gates[0];firstout=first['connections']['X'][0]
    nxt=next(((n,c) for n,c in gates if firstout in c['connections']['A']+c['connections']['B']),None)
    if nxt is None:
        for candidate_name,candidate in gates:
            net=candidate['connections']['X'][0]
            downstream=next(((n,c) for n,c in gates if net in c['connections']['A']+c['connections']['B']),None)
            if downstream:
                first_name,first,nxt=candidate_name,candidate,downstream
                break
    fig,ax=plt.subplots(figsize=(9 if nxt else 6,3));ax.set(xlim=(0,9 if nxt else 4.5),ylim=(0,3));ax.axis('off')
    ax.text(0,2.75,'Actual mapped XOR connection in the frozen flat Hsiao synthesis',fontsize=12,weight='bold')
    selected=[(first_name,first)]+([nxt] if nxt else [])
    for i,(name,c) in enumerate(selected):
        x=2+i*4
        ax.add_patch(Circle((x,1.4),.3,fill=False,lw=1.4));ax.text(x,1.4,'+',ha='center',va='center',fontsize=18)
        ax.text(x,.8,'xor2_1',ha='center');ax.text(x,.45,name.split('$')[-1],ha='center',fontsize=8)
        for j,pin in enumerate(('A','B')):
            net=c['connections'][pin][0];ax.text(x-1.25,1.85-j*.9,f'net {net}',ha='center',fontsize=9)
            arrow(ax,x-.9,1.85-j*.9,x-.3,1.4)
        output=c['connections']['X'][0];arrow(ax,x+.3,1.4,x+1.2,1.4);ax.text(x+1.45,1.4,f'net {output}',ha='center',fontsize=9)
    ax.text(0,.05,'Net IDs and instance suffixes come directly from mapped_netlist.json. This connectivity example does not establish reconvergent glitches.',fontsize=8)
    write_json(PHASE/'processed/mapped_circuit_example.json',{'source_sha256':sha256(src),'cells':[{'instance':n,**c} for n,c in selected]})
    save(fig,'09_mapped_xor_example',[src],'HISTORICAL_MAPPED_STRUCTURE')


def main():
    architectures();methods();historical_plots();qualification();workload_activity();mapped_example()
    write_json(OUT/'figure_manifest.json',manifest)
    print(f'{len(manifest)} evidence-grounded figures in PDF/SVG/PNG')


if __name__=='__main__':
    main()
