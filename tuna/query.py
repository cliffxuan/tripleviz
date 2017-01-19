# -*- coding: utf-8 -*-
#
# (C) Copyright Digital Catapult Limited 2015
# All rights reserved
#
from textwrap import dedent

from tuna.utils import (NAMESPACES, truncate, transform,
                        remove_matching_namespace)

PREFIX_TEXT = '\n'.join(
    'prefix {}:<{}>'.format(key, value)
    for key, value in NAMESPACES.iteritems())


class EntityNotFound(Exception):
    pass


def prepare_query(query):
    """
    add the namespace text to the front of the query
    :param query: Sparql query without namespace declarations
    :return Sparql query with namespace declarations on top
    """
    query = dedent(query.strip())

    if PREFIX_TEXT not in query:
        query = PREFIX_TEXT + '\n' + query

    if type(query) == unicode:
        query = query.encode('utf-8')

    return query


def to_dict(graph, entity, ns_to_strip=()):
    """
    convert an rdf graph to a dictionary from the view point of one entity
    :param graph: a rdflib.Graph object
    :param node: a URIRef object
    :param ns_to_strip: a tuple of namespaces to be stripped
    """
    subjects = []
    predicates = []
    objects = []
    for s, p, o in graph:
        if o == entity:
            continue
        subjects.append(s)
        predicates.append(p)
        objects.append(o)
    if entity not in subjects:
        raise EntityNotFound('cannot find entity {}'.format(entity))
    attributes = set(subjects).intersection(objects)

    sub_entities = {}
    for attr in attributes:
        for p, o in graph.predicate_objects(subject=attr):
            try:
                graph.predicates(object=attr, subject=o).next()
            except StopIteration:
                # only add if s and o are not forming a circle
                sub_entities.setdefault(attr, {}).setdefault(p, []).append(o)

    for vl in sub_entities.values():
        for v in vl.values():
            for i, k in enumerate(v):
                if k in sub_entities:
                    v[i] = sub_entities[k]
        truncate(vl)

    result = {}
    for p, o in graph.predicate_objects(subject=entity):
        result.setdefault(p, []).append(sub_entities.get(o, o))
    truncate(result)

    result = transform(
        lambda d: remove_matching_namespace(d, ns_to_strip), result)
    return result
