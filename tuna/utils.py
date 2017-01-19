# -*- coding: utf-8 -*-
#
# (C) Copyright Digital Catapult Limited 2015
# All rights reserved
#
from __future__ import unicode_literals
import re
from collections import Sequence, Mapping, Set
from types import StringTypes

from rdflib import URIRef, Namespace

from hubkey import is_hub_key


chub = Namespace('http://www.copyrighthub.org/2014/chub#')
lcc = Namespace('http://www.rightscom.com/2011/lcc#')
lem = Namespace('http://www.rightscom.com/2011/lem#')

# TODO hk will be removed once we can generate
# all kinds of URIs, e.g. supplier_id_type, creation_id_type,
# licence_id
hk = Namespace('http://www.copyrighthub.org/2014/hk#')

NAMESPACES = {
    'chub': chub,
    'hk': hk,
    'lcc': lcc,
    'lem': lem
}


def trim_uriref(uriref):
    """
    convert a URIRef object to a short form prefixed with namespace
    """
    match = re.search(r'/(\w+)#(.*)$', uriref)
    if match:
        return ':'.join(match.groups())
    else:
        return uriref


def transform(trans_f, data):
    """
    apply a function on all elements of the data and retain the structure
    """
    if isinstance(data, Mapping):
        return dict(map(lambda d: transform(trans_f, d), data.iteritems()))
    elif (isinstance(data, (Sequence, Set))
          and not isinstance(data, StringTypes)):
        return type(data)(map(lambda d: transform(trans_f, d), data))
    else:
        return trans_f(data)


def shorten(data):
    """
    remove the node urls and retain the data structure, so it's readable
    and ready to be converted into json format
    """
    return transform(trim_uriref, data)


def escape(uriref):
    """
    escape a uriref by angle brackets
    """
    return '<{}>'.format(uriref)


def get_hub_key(entity_id):
    """
    get a hub key from the entity_id
    this function will be gone once real hubkey generated
    using the identity lib is used everywhere
    returns: a URIRef object
    """
    if isinstance(entity_id, URIRef):
        return entity_id
    if entity_id.startswith('hk:'):
        return hk[entity_id[len('hk:'):]]
    if URIRef(entity_id).startswith(hk) or is_hub_key(entity_id):
        return URIRef(entity_id)
    return hk[entity_id]


def truncate(result):
    """
    if the dictionary value is an iterable collection, and has only
    only item in the collection, turn it into a single item.

    :param result: a dictionary
    """
    for k, v in result.copy().iteritems():
        if isinstance(v, (Sequence, Set)) and len(v) == 1:
            result[k] = iter(v).next()


# TODO deal with case without #
def get_namespace(uriref):
    """
    get the namespace abbrev and url
    """
    ns = uriref.split('/')[-1].split('#')[0]
    url = ''.join(uriref.partition('#')[:-1])
    return (ns, url)


def extract_namespaces(graph):
    """
    find all the namespaces used in a graph
    :return: iterator
    """
    def _iter_graph_by_elem(graph):
        for s, p, o in graph:
            yield s
            yield p
            yield o

    urirefs = filter(lambda x: type(x) == URIRef,
                     _iter_graph_by_elem(graph))
    return dict(map(get_namespace, urirefs))


def remove_namespace(uriref):
    """
    remove the namespace of the uriref, e.g. chub:Width -> Width

    :param uriref: a URIRef instance
    :returns: a string
    """
    name = '#'.join(uriref.split('/')[-1].split('#')[1:])
    return name


def remove_matching_namespace(uriref, namespaces):
    """
    remove the namespace of the urif if it is one of the
    matching namespaces

    :param uriref: a URIRef instance
    :param namespaces: a list of namespaces
    :returns: a URIRef or string
    """
    if any(uriref.startswith(ns) for ns in namespaces):
        return remove_namespace(uriref)
    else:
        return uriref


def reverse_notation(uriref):
    """
    when an hasEntity1Role is missing in a link, infer the link as the
    reverse of the hasEntity2Role. For example, if Entity1 is Entity2's
    Provider, Entity2 is Entity1's ~Provider.

    :param uriref: a URIRef instance
    :returns: a URIRef instance
    """
    frag = uriref.split('#')[-1]
    reversed = False
    while frag.startswith('~'):
        frag = frag[1:]
        reversed = not reversed
    if not reversed:
        frag = '~' + frag
    return uriref.defrag() + '#' + frag


def bind_namespaces(graph):
    """
    bind the namespaces to the graph

    :param graph: a graph object
    :returns: the same graph object
    """
    for prefix, ns in NAMESPACES.items():
        graph.bind(prefix, ns)
    return graph


def ascii_serialize(graph, format):
    """
    serialize the graph to ascii using xmlcharrefreplace

    :param graph: a graph object
    :param format: a format which rdflib supports, e.g. xml, turtle
    :returns: ascii encoded string
    """
    u_graph = graph.serialize(format=format).decode('utf-8')
    return u_graph.encode('ascii', 'xmlcharrefreplace')
