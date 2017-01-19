# -*- coding: utf-8 -*-
#
# (C) Copyright Digital Catapult Limited 2015
# All rights reserved
#
from rdflib import Graph, Namespace
import pytest

from tuna.query import prepare_query, PREFIX_TEXT, to_dict


def test_prepare_query():
    query = ' query '
    prepared_query = prepare_query(query)
    assert prepared_query.endswith(query.strip())
    assert prepared_query.startswith(PREFIX_TEXT)

    query = PREFIX_TEXT + '\nfoobar'
    assert prepare_query(query) == query


@pytest.mark.parametrize("data, expected", [
    ("""
     A B C
     A D E
     """, {'B': 'C', 'D': 'E'}),
    ("""
     A B C
     C D E
     """, {'B': {'D': 'E'}}),
    ("""
     A B C
     C D E
     C F G
     """, {'B': {'D': 'E', 'F': 'G'}}),
    ("""
     A B C
     C D E
     E F G
     """, {'B': {'D': {'F': 'G'}}}),
    ("""
     A B C
     C D E
     C F G
     E H I
     """, {'B': {'D': {'H': 'I'}, 'F': 'G'}}),
    ("""
     A B C
     C D E
     E F G
     G H I
     """, {'B': {'D': {'F': {'H': 'I'}}}}),
    ("""
     A B C
     C D E
     E F G
     G H I
     G J K
     K L M
     """, {'B': {'D': {'F': {'H': 'I', 'J': {'L': 'M'}}}}}),
    ("""
     A B C
     C D A
     """, {'B': 'C'}),
    # ignore E F A as it points back to A
    ("""
     A B C
     C D E
     E F A
     """, {'B': {'D': 'E'}}),
    # circular D -> C -> D
    ("""
     A B C
     D E C
     C F D
     """, {'B': 'C'}),
])
def test_to_dict(data, expected):
    g = Graph()
    ns = Namespace('http://www.example.com/ns#')
    for line in data.strip().split('\n'):
        g.add((ns[i] for i in line.strip().split(' ')))
    assert to_dict(g, ns['A'], (ns,)) == expected
