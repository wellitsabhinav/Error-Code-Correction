`timescale 1ns/1ps

module phase2_buffer(input A, output Y);
  assign Y = A;
  specify
    (A => Y) = (0, 0);
  endspecify
endmodule

module phase2_delays(input stim, output fast, slow, hazard);
  wire branch;
  phase2_buffer source_buf(.A(stim), .Y(branch));
  phase2_buffer load_a(.A(branch), .Y(fast));
  phase2_buffer load_b(.A(branch), .Y(slow));
  assign hazard = fast ^ slow;
endmodule

module phase2_combined_tb;
  reg stim = 0, clk = 0;
  wire fast, slow, hazard;
  reg captured;
  string sdf;
  phase2_delays dut(.*);
  always @(posedge clk) captured <= hazard;
  always @(fast) if ($realtime > 5) $display("FAST %0t %b", $realtime, fast);
  always @(slow) if ($realtime > 5) $display("SLOW %0t %b", $realtime, slow);
  initial begin
    $timeformat(-12, 0, "", 0);
    if (!$value$plusargs("SDF=%s", sdf)) $fatal(1, "Missing SDF");
    $sdf_annotate(sdf, dut);
    $dumpfile("activity.vcd");
    $dumpvars;
    #10 stim = 1;
    #1 clk = 1;
    #0.001 if (captured !== 1'b1) $fatal(1, "Hazard did not capture during expected window");
    #0.999 clk = 0;
    #1 clk = 1;
    #0.001 if (captured !== 1'b0) $fatal(1, "Settled input did not capture correctly");
    #16.999 stim = 0;
    #15 $finish;
  end
endmodule
