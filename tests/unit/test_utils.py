# -*- coding: utf-8 -*-
#
# (C) Copyright Digital Catapult Limited 2014-2016
# All rights reserved
#
import pytest
from rdflib import URIRef, Graph, Literal

from tuna.utils import (
    chub, hk, get_hub_key, shorten, escape, remove_namespace,
    reverse_notation, trim_uriref, remove_matching_namespace,
    bind_namespaces, ascii_serialize)


@pytest.mark.parametrize("input,expected", [
    (chub.Width, 'Width'),
    (chub['Foo#Bar'], 'Foo#Bar'),
])
def test_remove_namespace(input, expected):
    assert remove_namespace(input) == expected


def test_trim_uriref():
    assert trim_uriref(chub.foo) == 'chub:foo'

    key = 'copyrighthub.org/s0/creation/MaryEvans/MaryEvansPictureID/17'
    assert trim_uriref(hk[key]) == 'hk:{}'.format(key)

    normal_string = 'foo'
    assert trim_uriref(normal_string) == normal_string


def test_escape():
    assert escape(chub.foo) == (
        '<http://www.copyrighthub.org/2014/chub#foo>')


@pytest.mark.parametrize("input,expected", [
    (chub.foo, 'chub:foo'),
    ([chub.foo, chub.bar], ['chub:foo', 'chub:bar']),
    ({chub.foo: chub.bar}, {'chub:foo': 'chub:bar'}),
    ({chub.foo: [chub.bar, chub.baz]}, {'chub:foo': ['chub:bar', 'chub:baz']}),
])
def test_shorten(input, expected):
    assert shorten(input) == expected


@pytest.mark.parametrize("input,expected", [
    ('foo', '~foo'),
    ('~foo', 'foo'),
    ('~~foo', '~foo'),
    ('~~~foo', 'foo'),
    ('~~foo~bar', '~foo~bar'),
])
def test_reverse_notation(input, expected):
    uriref = chub[input]
    assert reverse_notation(uriref) == chub[expected]


@pytest.mark.parametrize("input,expected", [
    ('foo1', hk['foo1']),
    ('hk:foo2', hk['foo2']),
    ('http://www.copyrighthub.org/2014/hk#foo3', hk['foo3']),
    (hk['foo4'], hk['foo4']),
])
def test_get_hub_key(input, expected):
    assert get_hub_key(input) == expected


def test_get_hub_key_from_hub_key():
    right = 'https://copyrighthub.org/s0/hub1/offer/bapla/hk/01'
    creation = 'https://copyrighthub.org/s0/hub1/asset/exampleco/ExampleCoPictureID/36'
    assert get_hub_key(right) == URIRef(right)
    assert get_hub_key(creation) == URIRef(creation)


@pytest.mark.parametrize("data,ns,new", [
    (chub.Foo, (chub,), 'Foo'),
    (chub.Foo, (chub,), 'Foo'),
    (chub.Foo, (chub, chub), 'Foo'),
    (chub.Foo, (hk,), chub.Foo),
])
def test_remove_matching_namespaces(data, ns, new):
    assert remove_matching_namespace(data, ns) == new


def test_ascii_serialize():
    graph = Graph()
    bind_namespaces(graph)
    graph.add((hk.foo, chub.name, Literal('curly “quotes”')))
    serialized = ascii_serialize(graph, 'xml')

    assert '&#8220;' in serialized
    assert '&#8221;' in serialized
