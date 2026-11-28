`timescale 1ns/1ps
// Capability probe only. This is not a SKY130 flop and has no physical claim.
module check_probe(input d, clk, output reg q, output reg notifier=0);
  always @(posedge clk) q <= d;
  specify
    $setuphold(posedge clk, posedge d, 2, 2, notifier);
    $width(posedge clk, 2, 0, notifier);
  endspecify
endmodule
module timing_checks_tb;
  reg d=0, clk=0;
  wire q,n;
  check_probe dut(d,clk,q,n);
  initial begin
    $dumpfile("timing_checks.vcd"); $dumpvars(0,timing_checks_tb);
    #10 d=1; #0.1 clk=1; #0.1 clk=0;
    #5 $display("NOTIFIER=%b",n);
    $finish;
  end
endmodule
