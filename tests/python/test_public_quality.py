from datetime import date
import json

import jsonschema
import pytest
import yaml

from scripts.check_public_quality import ROOT, fences_balanced, normalize_yaml_dates, validate


@pytest.mark.parametrize('text', ['```python\nx=1\n~~~\n', '````python\nx=1\n```\n'])
def test_mismatched_commonmark_fences_remain_unclosed(text):
    assert not fences_balanced(text)


def test_a_longer_matching_closer_is_valid():
    assert fences_balanced('```python\nx=1\n````\n')


def test_valid_unquoted_cff_date_passes_the_official_schema():
    citation = yaml.safe_load((ROOT / 'CITATION.cff').read_text())
    citation['date-released'] = date(2026, 10, 13)
    schema = json.loads((ROOT / 'schemas/citation-1.2.0.schema.json').read_text())
    jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker()).validate(normalize_yaml_dates(citation))


def test_removing_a_transient_file_does_not_block_cleanup():
    deleted = ROOT / 'tmp/__pycache__/deleted.pyc'
    assert not deleted.exists()
    assert not any('committed transient' in error for error in validate([deleted]))
