set result $::env(P2P_RESULTS)
read_liberty $::env(P2P_LIBERTY)
read_db $result/6_final.odb
read_sdc $result/6_final.sdc
read_spef $result/6_final.spef

report_design_area
report_worst_slack -max -digits 9
report_worst_slack -min -digits 9
report_checks -path_delay max -group_path_count 5 -digits 9 > /campaign-run/setup.rpt
report_checks -path_delay min -group_path_count 5 -digits 9 > /campaign-run/hold.rpt
report_check_types -max_delay -min_delay -violators -digits 9 > /campaign-run/violations.rpt
write_sdf -include_typ -digits 6 /campaign-run/6_final.sdf

read_vcd -scope gate04_trace_top /trace/activity.vcd
report_activity_annotation > /campaign-run/method-a.annotation.rpt
report_activity_annotation -report_annotated > /campaign-run/method-a.annotated.rpt
report_power -digits 12 > /campaign-run/method-a.power.rpt
puts "PHASE2_PLUS_CHARACTERIZATION_COMPLETE"
