# -*- coding: utf-8 -*-
#
# (C) Copyright Connected Digital Economy Catapult Limited 2014
# All rights reserved
#
import sys
import json

import chardet
from rdflib import URIRef, Namespace
from tuna.entity_model import Graph
from tuna.utils import lcc


ENTITY_TYPES = [
    'Category', 'Descriptor', 'Creation', 'Link', 'Context',
    'Party', 'Time', 'Quantity'
] + [
    'http://www.w3.org/ns/odrl/2/Set',
    'http://www.w3.org/ns/odrl/2/Duty',
    'http://www.w3.org/ns/odrl/2/Contraint',
    'http://www.w3.org/ns/odrl/2/Permission',
    'http://purl.org/dc/terms/DCMITypeText',
    'https://copyrighthub.org/ns/odrl-chub/0/PersonalWebsiteAds']

CONTEXT_TYPES = ['Right', 'RightsAssignment', 'Acknowledge', 'Pay']

NAMESPACES = {
    'odrl': Namespace('http://www.w3.org/ns/odrl/2/'),
    'dcterms': Namespace('http://purl.org/dc/terms/'),
    'odrl-chub': Namespace('https://copyrighthub.org/ns/odrl-chub/0/')
}


class UnknownEntityType(Exception):
    pass


class UnknownContextType(Exception):
    pass


class DocumentError(Exception):
    pass


def get_ns(uriref):
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
    return dict(map(get_ns, urirefs))


def get_name(graph, subject, predicate=lcc.Name):
    try:
        name = tuple(graph.objects(subject=subject, predicate=predicate))[0]
        return name
    except IndexError:
        return


def build_networkx(graph, groups):
    """
    builds a network graph using an RDF graph
    returning JSON networkx graph for D3 force layout
    """
    trunk = trim_graph(graph)
    items = sorted(set((sum([(item[0], item[2]) for item in trunk], ()))))
    nodes = [
        {'id': item,
         'name':  get_name(graph, item) or item.split('#')[-1],
         'group': groups.get(item, '*Untyped*')}
        for item in items]
    links = [
        {'source': items.index(s),
         'target': items.index(o),
         'predicate': p.n3(graph.namespace_manager)}
        for (s, p, o) in trunk
    ]
    data = json.dumps(
        {'nodes': nodes, 'links': links},
        sort_keys=True, indent=2, separators=(',', ': '))
    return data


def build_graph(doc, encoding=None):
    """
    builds a rdflib Graph object from a file object
    containing triples
    """
    graph = Graph()
    for key, val in NAMESPACES.items():
        graph.bind(key, val)
    encoding = encoding if encoding else chardet.detect(doc)['encoding']
    try:
        doc = doc.decode(encoding)
    except UnicodeDecodeError:
        raise DocumentError(
            'cannot decode document, tried codec "{}"'.format(encoding))
    for format in ['turtle', 'xml', 'nt']:
        try:
            graph.parse(data=doc, format=format)
        except Exception:
            pass
        else:
            break
    else:
        raise Exception('Cannot parse document.'
                        ' Supported formats are turtle, xml, nt')
    return graph


def trim_graph(graph):
    """
    trims a rdflib Graph object by taking off the attributes
    returning a list of triples
    """
    subjects = [stmt[0] for stmt in graph]
    objects = [stmt[2] for stmt in graph]
    attributes = [obj for obj in objects
                  if obj not in subjects]
    trunk = [stmt for stmt in graph
             if stmt[2] not in attributes]
    return trunk


def get_entity_types(graph):
    """
    gets entity types from the graph returning a dictionary
    """
    types = {}
    for stmt in graph:
        try:
            edge_text = stmt[1].n3(namespace_manager=graph.namespace_manager)
        except Exception:
            print 'got broken triple', stmt
            edge_text = 'broken'
        if edge_text in ['lem:EntityType', 'lcc:EntityType',
                         'lem:hasEntityType']:
            entity_type_text = str(stmt[2]).split('#')[-1]
            if entity_type_text not in ENTITY_TYPES:
                raise UnknownEntityType(
                    'got unknown entity type {}'.format(entity_type_text))
            types.setdefault(stmt[0], entity_type_text)
        if edge_text == 'rdf:type':
            entity_type_text = stmt[2].n3(graph.namespace_manager)
            types.setdefault(stmt[0], entity_type_text)
        if edge_text in ['lcc:ContextType', 'lem:ContextType',
                         'lem:hasContextType']:
            entity_type_text = str(stmt[2]).split('#')[-1]
            if entity_type_text not in CONTEXT_TYPES:
                raise UnknownContextType(
                    'got unknown context type {}'.format(entity_type_text))
            types[stmt[0]] = entity_type_text
    return types


def generate_d3_directed_graph(doc, minimize=False):
    """
    generate JSON data for D3 force-directed graph
    """
    graph = build_graph(doc)
    if minimize:
        graph = graph.minimize()
    return build_networkx(graph, get_entity_types(graph))


def main(filename, encoding=None):
    turtle = open(filename, 'r').read()
    print generate_d3_directed_graph(turtle)

if __name__ == '__main__':
    main(sys.argv[1])
