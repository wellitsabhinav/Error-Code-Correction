`timescale 1ns/1ps
module rtl_smoke_tb;
  reg clk=0;
  always #5 clk=~clk;
  reg rst=0, valid=0;
  reg [63:0] payload=0;
  reg [71:0] hword=0, sword=0;
  reg [63:0] payloads[0:99], hdata[0:99], sdata[0:99];
  reg [71:0] hwords[0:99], swords[0:99], hencoded[0:99], sencoded[0:99];
  reg hd[0:99],hc[0:99],hu[0:99],sd[0:99],sc[0:99],su[0:99];
  wire [71:0] ec[0:3];
  wire [63:0] dc[0:3];
  wire ev[0:3],dv[0:3],det[0:3],cor[0:3],unc[0:3];
  integer f,g,r,i,k,n,index,completed[0:3];
  gate04_secded_comb_72_64 comb(.clk_i(clk),.rst_ni(rst),.valid_i(valid),.enc_data_i(payload),.dec_codeword_i(hword),
    .enc_valid_o(ev[0]),.enc_codeword_o(ec[0]),.dec_valid_o(dv[0]),.dec_data_o(dc[0]),
    .dec_detected_o(det[0]),.dec_corrected_o(cor[0]),.dec_uncorrectable_o(unc[0]));
  gate04_secded_pipe_72_64 pipe(.clk_i(clk),.rst_ni(rst),.valid_i(valid),.enc_data_i(payload),.dec_codeword_i(hword),
    .enc_valid_o(ev[1]),.enc_codeword_o(ec[1]),.dec_valid_o(dv[1]),.dec_data_o(dc[1]),
    .dec_detected_o(det[1]),.dec_corrected_o(cor[1]),.dec_uncorrectable_o(unc[1]));
  gate04_rev2_hsiao_72_64 flat(.clk_i(clk),.rst_ni(rst),.valid_i(valid),.enc_data_i(payload),.dec_codeword_i(sword),
    .enc_valid_o(ev[2]),.enc_codeword_o(ec[2]),.dec_valid_o(dv[2]),.dec_data_o(dc[2]),
    .dec_detected_o(det[2]),.dec_corrected_o(cor[2]),.dec_uncorrectable_o(unc[2]));
  breadth_hsiao_hierarchical_72_64 hier(.clk_i(clk),.rst_ni(rst),.valid_i(valid),.enc_data_i(payload),.dec_codeword_i(sword),
    .enc_valid_o(ev[3]),.enc_codeword_o(ec[3]),.dec_valid_o(dv[3]),.dec_data_o(dc[3]),
    .dec_detected_o(det[3]),.dec_corrected_o(cor[3]),.dec_uncorrectable_o(unc[3]));
  initial begin
    f=$fopen("../../workloads/hamming_smoke.txt","r");
    g=$fopen("../../workloads/hsiao_smoke.txt","r");
    if (!f || !g) $fatal(1,"missing reference vectors");
    for(i=0;i<100;i=i+1) begin
      r=$fscanf(f,"%h %h %h %h %d %d %d\n",payloads[i],hwords[i],hencoded[i],hdata[i],hd[i],hc[i],hu[i]);
      if(r!=7) $fatal(1,"bad Hamming vector");
      r=$fscanf(g,"%h %h %h %h %d %d %d\n",payload,swords[i],sencoded[i],sdata[i],sd[i],sc[i],su[i]);
      if(r!=7 || payload !== payloads[i]) $fatal(1,"unpaired Hsiao vector");
    end
    for(k=0;k<4;k=k+1) completed[k]=0;
    repeat(4) @(posedge clk);
    for(n=0;n<104;n=n+1) begin
      @(negedge clk);
      rst=1;
      valid=(n<100);
      if(n<100) begin payload=payloads[n];hword=hwords[n];sword=swords[n];end
      @(posedge clk); #1;
      for(k=0;k<4;k=k+1) begin
        index=n-(k==1 ? 3 : 1);
        if(index>=0 && index<100) begin
          if(ev[k] !== 1 || dv[k] !== 1) $fatal(1,"valid ordering k=%0d n=%0d",k,n);
          if(k<2) begin
            if(ec[k] !== hencoded[index] || dc[k] !== hdata[index] ||
               det[k] !== hd[index] || cor[k] !== hc[index] || unc[k] !== hu[index])
              $fatal(1,"Hamming mismatch k=%0d n=%0d",k,n);
          end else begin
            if(ec[k] !== sencoded[index] || dc[k] !== sdata[index] ||
               det[k] !== sd[index] || cor[k] !== sc[index] || unc[k] !== su[index])
              $fatal(1,"Hsiao mismatch k=%0d n=%0d",k,n);
          end
          completed[k]=completed[k]+1;
        end else if(ev[k] !== 0 || dv[k] !== 0) $fatal(1,"unexpected transaction k=%0d n=%0d",k,n);
      end
    end
    for(k=0;k<4;k=k+1) if(completed[k]!=100) $fatal(1,"wrong completion count");
    $display("PASS architectures=4 completed_each=100 latency_cycles=1,3,1,1 II=1 clean_single_double exercised");
    $finish;
  end
endmodule
