import json
import os

import pytest
from rdflib import URIRef

from lite import (
    NS, expand_uriref, parse_mappings, mapping_filename,
    get_ns, minimize, serialize, serialize_mappings, restore, MAPPING_DIR,
    DEFAULT_MAPPING)


def test_expand_uriref():
    url = 'http://www.rightscom.com/2011/lcc#foo'
    assert expand_uriref('lcc#foo').strip() == url


def test_parse_mappings():
    parsed = parse_mappings(open(DEFAULT_MAPPING, 'r').read())
    assert 'Category' in parsed


@pytest.mark.parametrize("input,expected", [
    ("foo.ttl", 'mappings.foo.json'),
    ("foo", 'mappings.foo.json'),
    ("foo.bar.ttl", 'mappings.foo.bar.json'),
])
def test_mapping_filename(input, expected):
    assert mapping_filename(input) == os.path.join(MAPPING_DIR, expected)


def test_get_ns():
    uriref = URIRef('http://www.copyrighthub.co.uk/2014/hk#foo')
    assert get_ns(uriref) == ('hk', 'http://www.copyrighthub.co.uk/2014/hk#')


def test_multiple_descriptors():
    doc = """
    @prefix chub: <http://www.copyrighthub.co.uk/2014/chub#> .
    @prefix hk: <http://www.copyrighthub.co.uk/2014/hk#> .
    @prefix lcc: <http://www.rightscom.com/2011/lcc#> .

    hk:CREATION1 chub:ReferenceID "CREATION1" ;
        lcc:EntityType lcc:Creation ;
        lcc:Category hk:CREATION1_C1,
            hk:CREATION1_C2 .

    hk:CREATION1_C1 lcc:CategoryType chub:VisualWorkType ;
        lcc:CategoryValue chub:PersonalWebpage ;
        lcc:EntityType lcc:Category .

    hk:CREATION1_C2 lcc:CategoryType chub:VisualWorkType ;
        lcc:CategoryValue chub:PersonalBlog ;
        lcc:EntityType lcc:Category ."""
    result, mapping, errors = minimize(doc, 'turtle')
    lite = serialize(result, 'turtle')
    print '-' * 20, 'minimized:'
    print lite

    objs = result.values()[0][NS['chub']['VisualWorkType']]
    assert NS['chub']['PersonalBlog'] in objs
    assert NS['chub']['PersonalWebpage'] in objs

    json_mapping = serialize_mappings(mapping)
    for key in ['chub#VisualWorkType chub#PersonalBlog',
                'chub#VisualWorkType chub#PersonalWebpage']:
        assert key in json.loads(json_mapping)['Category']

    g = restore(lite, 'turtle', json_mapping)
    restored = g.serialize(format='turtle')
    print restored

    assert errors == ''
