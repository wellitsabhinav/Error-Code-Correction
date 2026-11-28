read_liberty $::env(P2P_LIBERTY)
read_db /routed/6_final.odb
read_sdc /routed/6_final.sdc
read_spef /routed/6_final.spef
read_vcd -scope $::env(P2P_SCOPE) /activity/window.vcd
report_activity_annotation > /campaign-run/annotation.rpt
report_activity_annotation -report_annotated > /campaign-run/annotated.rpt
report_activity_annotation -report_unannotated > /campaign-run/unannotated.rpt
report_power -digits 12 > /campaign-run/power.rpt
report_activity_annotation > /campaign-run/annotation_after_power.rpt
