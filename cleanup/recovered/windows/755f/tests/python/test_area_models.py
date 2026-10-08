from area_models import (
    ECCSpec,
    area_logic_mm2,
    area_macro_mm2,
    mux2_equivalents,
    mux_depth,
    nand2_equivalent_count,
)


def test_area_monotone():
    secded = ECCSpec("sec-ded-64", 64, 8)
    secdaec = ECCSpec("sec-daec-64", 64, 9, corrects_adj2=True)
    assert area_logic_mm2(secdaec, 14) > area_logic_mm2(secded, 14)


def test_macro_scaling():
    s = ECCSpec("sec-ded-64", 64, 8)
    a1 = area_macro_mm2(s, 4, 14, bitcell_um2=0.040)
    a2 = area_macro_mm2(s, 8, 14, bitcell_um2=0.040)
    assert abs(a2 / a1 - 2.0) < 1e-6


def test_mux_normalisation_and_nand2_total():
    spec = ECCSpec("sec-ded-64", 64, 8)
    assert mux2_equivalents(8) == 7
    assert mux_depth(8) == 3
    assert nand2_equivalent_count(spec, mux_count=7) == (
        nand2_equivalent_count(spec) + 28
    )
