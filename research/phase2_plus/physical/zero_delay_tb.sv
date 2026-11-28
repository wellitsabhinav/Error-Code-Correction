`timescale 1ns/1ps

module phase2_gate_tb;
  localparam integer COUNT = 1000;
  localparam integer LATENCY = `P2P_LATENCY;
  reg clk_i = 0, rst_ni = 0, valid_i = 0;
  reg [63:0] enc_data_i = 0;
  reg [71:0] dec_codeword_i = 0;
  wire enc_valid_o, dec_valid_o, dec_detected_o, dec_corrected_o, dec_uncorrectable_o;
  wire [71:0] enc_codeword_o, dec_codeword_echo_o;
  wire [63:0] dec_data_o;
  reg [63:0] payload [0:COUNT-1];
  reg [71:0] codewords [0:COUNT-1];
`ifdef P2P_CONDITIONED
  reg [71:0] received [0:COUNT-1];
  reg [63:0] expected_data [0:COUNT-1];
  reg [2:0] expected_flags [0:COUNT-1];
`endif
  integer cycle = 0, completed = 0, expected, index;
  `P2P_TOP dut(.*);
  always #5 clk_i = ~clk_i;

  initial begin
    $readmemh("payload.hex", payload);
    $readmemh("codewords.hex", codewords);
`ifdef P2P_CONDITIONED
    $readmemh("received.hex", received);
    $readmemh("expected_data.hex", expected_data);
    $readmemh("expected_flags.hex", expected_flags);
`endif
    $dumpfile("gate.vcd");
    $dumpvars(0, dut);
    repeat (6) @(negedge clk_i);
    rst_ni = 1;
    valid_i = 1;
    for (index = 0; index < COUNT; index = index + 1) begin
      enc_data_i = payload[index];
`ifdef P2P_CONDITIONED
      dec_codeword_i = received[index];
`else
      dec_codeword_i = codewords[index];
`endif
      @(negedge clk_i);
    end
    valid_i = 0;
    enc_data_i = 0;
    dec_codeword_i = 0;
    repeat (4) @(negedge clk_i);
    if (completed != COUNT) $fatal(1, "Completed %0d of %0d", completed, COUNT);
    $display("SCOREBOARD_PASS completed=%0d latency=%0d", completed, LATENCY);
    $finish;
  end

  always @(posedge clk_i) begin
    #0.001;
    if (!rst_ni) begin
      if ({enc_valid_o, dec_valid_o, enc_codeword_o, dec_data_o, dec_codeword_echo_o,
           dec_detected_o, dec_corrected_o, dec_uncorrectable_o} !== '0)
        $fatal(1, "Reset output mismatch");
    end else begin
      expected = cycle - LATENCY;
      if (enc_valid_o !== (expected >= 0 && expected < COUNT) || dec_valid_o !== enc_valid_o)
        $fatal(1, "Output valid mismatch at cycle %0d", cycle);
      if (enc_valid_o) begin
`ifdef P2P_CONDITIONED
        if (enc_codeword_o !== codewords[expected] || dec_data_o !== expected_data[expected] ||
            {dec_detected_o, dec_corrected_o, dec_uncorrectable_o} !== expected_flags[expected])
          $fatal(1, "Conditioned transaction mismatch at operation %0d", expected);
`else
        if (enc_codeword_o !== codewords[expected] || dec_data_o !== payload[expected] ||
            {dec_detected_o, dec_corrected_o, dec_uncorrectable_o} !== 3'b000)
          $fatal(1, "Clean transaction mismatch at operation %0d", expected);
`endif
        completed = completed + 1;
      end
`ifdef P2P_CONDITIONED
      if (cycle > 0 && cycle <= COUNT && dec_codeword_echo_o !== received[cycle-1])
`else
      if (cycle > 0 && cycle <= COUNT && dec_codeword_echo_o !== codewords[cycle-1])
`endif
        $fatal(1, "Raw decoder echo mismatch at cycle %0d", cycle);
      cycle = cycle + 1;
    end
  end
endmodule
