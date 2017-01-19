# -*- coding: utf-8 -*-
#
# (C) Copyright Digital Catapult Limited 2015-2016
# All rights reserved
#
"""
utility for creating triples
"""
from __future__ import unicode_literals

from rdflib import Graph

from .utils import NAMESPACES


def serialize(triples, format='xml'):
    """
    serialize triples to chosen format supported by rdflib,
    e.g. xml, turtle, n3, etc
    :param triples: a list of triples
    :param format: a format supported by rdflib, default to xml
    :returns: serialized doc
    """
    g = Graph()
    for k, v in NAMESPACES.iteritems():
        g.bind(k, v)

    for triple in triples:
        g.add(triple)
    return g.serialize(format=format)
