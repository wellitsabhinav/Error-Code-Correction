`timescale 1ns/1ps
module hazard_dut(input a, output y);
  wire fast, slow;
  sky130_fd_sc_hd__buf_1 u_fast(.A(a), .X(fast));
  sky130_fd_sc_hd__buf_1 u_slow(.A(a), .X(slow));
  sky130_fd_sc_hd__xor2_1 u_xor(.A(fast), .B(slow), .X(y));
endmodule

module hazard_tb;
  reg a;
  wire y;
  reg [1023:0] sdf_file, vcd_file;
  hazard_dut dut(.a(a), .y(y));
  initial begin
    if (!$value$plusargs("VCD=%s", vcd_file)) vcd_file="hazard.vcd";
    $dumpfile(vcd_file);
    $dumpvars(0, hazard_tb);
    if ($value$plusargs("SDF=%s", sdf_file)) $sdf_annotate(sdf_file, dut);
    a=0;
    #10 a=1;
    #20 a=0;
    #20 $finish;
  end
endmodule
