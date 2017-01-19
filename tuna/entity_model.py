# -*- coding: utf-8 -*-
#
# (C) Copyright Digital Catapult Limited 2015
# All rights reserved
#
"""
A module for the LCC Entity Model.

Dynamically constructed class is heavily used, which
is usually not needed as the code readability can be poor.
However, the data model is not defined by us. The code base
may change quite a lot while we make progress in learning.
Some rewriting is recommended, when more the code base is
exercised with more data.
"""
from __future__ import unicode_literals
import json
import itertools
from collections import Counter

from rdflib import graph
from rdflib.resource import Resource

from tuna.utils import (
    lcc, lem, chub, NAMESPACES, shorten, trim_uriref, transform, truncate,
    reverse_notation, remove_matching_namespace)


ATTRIBUTE_TYPES = {
    lem.Category:   {'predicate': lem.hasCategory,
                     'relationship_keys': [lem.hasCategoryType],
                     'collapse_on': lem.hasCategoryValue},
    lem.Descriptor: {'predicate': lem.hasDescriptor,
                     'relationship_keys': [lem.hasDescriptorSubType,
                                           lem.hasDescriptorType],
                     'collapse_on': lem.hasDescriptorValue,
                     'ignores': [lem.hasDescriptorType]},
    lem.Time:       {'predicate': lem.hasTime,
                     'relationship_keys': [lem.hasTimeType]},
    lem.Quantity:   {'predicate': lem.hasQuantity,
                     'relationship_keys': [lem.hasQuantityType]}
}

ENTITY_TYPES = {
    lcc.Creation: {},
    lem.Link:     {},
    lcc.Party:    {},
    lcc.Context:  {}
}

SUB_ENTITY_TYPES = {
    lcc.Right:            {'parent': lcc.Context,
                           lem.hasCategoryType: lcc.ContextType},
    lcc.RightsAssignment: {'parent': lcc.Context,
                           lem.hasCategoryType: lcc.ContextType},
    chub.Pay:             {'parent': lcc.Context,
                           lem.hasCategoryType: lcc.ContextType},
    chub.Acknowledge:     {'parent': lcc.Context,
                           lem.hasCategoryType: lcc.ContextType}
}

SUB_ENTITY_TO_PARENT = {k: v['parent'] for k, v in SUB_ENTITY_TYPES.items()}
ENTITY_TO_CHILDREN = {}
for child, parent in SUB_ENTITY_TO_PARENT.iteritems():
    ENTITY_TO_CHILDREN.setdefault(parent, []).append(child)

ENTITY_TYPES.update(ATTRIBUTE_TYPES)
ENTITY_TYPES.update(SUB_ENTITY_TYPES)


class UnknownEntityType(Exception):
    pass


class UnknownAttributeType(Exception):
    pass


class InvalidEntity(Exception):
    pass


class MultipleObjectsFound(InvalidEntity):
    pass


class SubjectNotFound(Exception):
    pass


def iter_entity(g, entity_type=None):
    """
    A generator of LCC entities
    """
    if not entity_type:
        for subj, obj in g.subject_objects(predicate=lem.hasEntityType):
            if obj in ENTITY_TO_CHILDREN:
                category_type = obj + 'Type'
                entity_categories = tuple(g.objects(
                    subject=subj, predicate=lem.hasCategory))
                if not entity_categories:
                    yield get_cls(obj)(g, subj)
                for entity_category in entity_categories:
                    try:
                        g.triples((entity_category,
                                   lem.hasCategoryType,
                                   category_type)).next()
                    except StopIteration:
                        pass
                    else:
                        sub_entity_type = g.objects(
                            subject=entity_category,
                            predicate=lem.hasCategoryValue).next()
                        yield get_cls(sub_entity_type)(g, subj)
            else:
                yield get_cls(obj)(g, subj)
    elif entity_type not in ENTITY_TYPES:
        raise UnknownEntityType(
            'unknown entity type {}'.format(entity_type))
    # iter main entity type
    elif entity_type not in SUB_ENTITY_TYPES:
        for subj in g.subjects(lem.hasEntityType, entity_type):
            yield get_cls(entity_type)(g, subj)
    # iter sub entity type
    else:
        for cat in g.subjects(predicate=lem.hasCategoryValue,
                              object=entity_type):
            for subj in g.subjects(lem.hasCategory, cat):
                yield get_cls(entity_type)(g, subj)


def iter_attribute(entity, attribute_type=None):
    """
    A generator of sub entities

    :param entity: an Entity instance
    :param attribute_type: a URIRef defined in ENTITY_TYPES
    """
    predicate_to_cls = {v['predicate']: k for k, v
                        in ATTRIBUTE_TYPES.iteritems()}
    if not attribute_type:
        for pre, obj in entity.predicate_objects():
            if pre.identifier in predicate_to_cls:
                raise_subject_not_found(entity.graph, obj.identifier)
                yield get_cls(predicate_to_cls[pre.identifier])(
                    entity.graph, obj.identifier)
    elif attribute_type not in ATTRIBUTE_TYPES:
        raise UnknownAttributeType(
            'unknown attribute type {}'.format(attribute_type))
    else:
        predicate = ATTRIBUTE_TYPES[attribute_type]['predicate']
        for obj in entity.objects(predicate=predicate):
            raise_subject_not_found(entity.graph, obj.identifier)
            yield get_cls(attribute_type)(entity.graph, obj.identifier)


def raise_subject_not_found(graph, subject):
    try:
        graph.predicate_objects(subject=subject).next()
    except StopIteration:
        raise SubjectNotFound(
            'cannot find subject {} in the graph'.format(shorten(subject)))


def minimize(g):
    """
    Minimize a full lcc/lem document by mutating the predicates and collapsing
    the attributes

    :param g: a full lcc/lem document graph
    :returns: an rdflib.graph.Graph object
    """
    mutated_main_entity_graphs = [entity.mutate() for entity in g.iter_entity()
                                  if entity.entity_type not in ATTRIBUTE_TYPES
                                  and entity.entity_type != lem.Link]
    mutated_graph = reduce(lambda x, y: x + y, mutated_main_entity_graphs)
    # collapse category, descriptor, time, quantity
    attributes = [e for e in g.iter_entity()
                  if e.entity_type in ATTRIBUTE_TYPES]
    for attribute in attributes:
        minimized = []
        for pre, obj in attribute.predicate_objects():
            if pre.identifier not in (attribute.ignores +
                                      attribute.relationship_keys):
                if isinstance(obj, Entity):
                    minimized.append((pre.identifier, obj.identifier))
                else:
                    minimized.append((pre.identifier, obj))
        if len(minimized) == 1 and minimized[0][0] == attribute.collapse_on:
            p = attribute.relationship
            o = attribute.identifier
            ss = tuple(mutated_graph.subjects(predicate=p, object=o))
            for s in ss:
                mutated_graph.remove((s, p, o))
                mutated_graph.add((s, p, minimized[0][1]))
        else:
            mutated_graph += attribute.mutate()
    # collapse link
    links = g.iter_link()
    for link in links:
        p_counts = Counter(link.predicates())
        # every predicate appears only once
        # and every predicate is in the allowed set
        if set(p_counts.values()) == set([1]):
            diff = set(l.identifier for l in p_counts.keys()).difference([
                lem.hasEntity1, lem.hasEntity2, lem.hasEntity1Role,
                lem.hasEntity2Role, lem.hasLinkType, lem.hasEntityType])
            if diff == set():
                continue
        mutated_graph += link.mutate()
    return mutated_graph


def get_cls(entity_type):
    """
    Get the entity type Class from entity_type.
    :param entity_type: a uriref like lem.Category
    :returns: a class representing the entity type.
    """
    return globals()[entity_type.split('#')[-1]]


class Entity(Resource):
    # during a predicate mutation, `relationship_keys` are a list of keys
    # chosen to be the new predicate in priority order.
    # during a minimizing, if there is only one triple, and the
    # predicate is `collapse_on`, turn it into a single value of the
    # object `collapse_on` links to.
    relationship_keys = []
    collapse_on = None
    # `ignores` is a list of predicates pointing to
    # value which can be inferred.
    ignores = [lem.hasEntityType, chub.ReferenceID]

    def __str__(self):
        # TODO use a variable for the namespace. this may change.
        return '{}({})'.format('lem:{}'.format((type(self).__name__)),
                               trim_uriref(self._identifier))

    def __repr__(self):
        # TODO use a variable for the namespace. this may change.
        return '{}({},{})'.format(
            self._graph, 'lem:{}'.format((type(self).__name__)),
            trim_uriref(self._identifier))

    @property
    def id(self):
        """
        returns the identifier of the subject, e.g. hk:1234
        """
        return self.identifier

    def get_single_object(self, predicate):
        obj = tuple(self.objects(predicate=predicate))
        if not obj:
            raise InvalidEntity(
                'Expect one {} for {}, found none'.format(
                    trim_uriref(predicate), trim_uriref(self.identifier))
            )
        if len(obj) > 1:
            raise MultipleObjectsFound(
                'Expect one {} for {}, found {}'.format(
                    trim_uriref(predicate), trim_uriref(self.identifier),
                    len(obj)))
        return obj[0]

    @property
    def relationship(self):
        for key in self.relationship_keys:
            try:
                obj = self.get_single_object(key)
                if isinstance(obj, Resource):
                    return obj.identifier
                else:
                    return obj
            except MultipleObjectsFound:
                raise
            except InvalidEntity:
                pass
        raise InvalidEntity(
            'Expected at least one of {} for {}, found none'.format(
                ','.join(map(trim_uriref, self.relationship_keys)),
                trim_uriref(self.identifier)))

    @property
    def entity_type(self):
        return self.get_single_object(lem.hasEntityType).identifier

    def mutate(self):
        """
        mutate the predicates for query efficiency.
        :returns: an rdflib.graph.Graph object
        """
        new_graph = Graph()

        for attribute in self.iter_attribute():
            new_graph.add((self.identifier, attribute.relationship,
                           attribute.identifier))
        for link in self.iter_link_as_entity1():
            try:
                obj = link.entity2.identifier
            except InvalidEntity:
                # partial graph where the entity2 of the link
                # is not in the doc
                obj = link.objects(
                    predicate=lem.hasEntity2).next().identifier
                pre = link.objects(
                    predicate=lem.hasEntity1Role).next().identifier
                new_graph.add((obj, pre, self.identifier))
            new_graph.add((self.identifier, link.entity2_role,
                           link.entity2.identifier))
        for link in self.iter_link_as_entity2():
            if link.entity1_role:
                try:
                    obj = link.entity1.identifier
                except InvalidEntity:
                    # partial graph where the entity1 of the link
                    # is not in the doc
                    obj = link.objects(
                        predicate=lem.hasEntity1).next().identifier
                    pre = link.objects(
                        predicate=lem.hasEntity2Role).next().identifier
                    new_graph.add((obj, pre, self.identifier))
                new_graph.add((self.identifier,
                               link.entity1_role,
                               obj))
        for p, o in self.predicate_objects():
            if p.identifier in [v['predicate'] for v
                                in ATTRIBUTE_TYPES.values()]:
                continue
            if isinstance(o, Entity):
                new_graph.add((self.identifier, p.identifier, o.identifier))
            else:
                new_graph.add((self.identifier, p.identifier, o))
        return new_graph

    def to_dict(self, expand_link=True, reverse_notate=True,
                truncate_result=True):
        """
        convert the entity object into a dictionary
        :param expand_link: whether the linked entity's linked entity should
        also be fully included or just the id.
        :param reverse_notate: whether to use reverse noatation
        :param truncate_result: whether to truncate the result
        :returns: a dictionary
        """
        result = {}
        if self.entity_type not in ATTRIBUTE_TYPES:
            result[chub.ReferenceID] = self.id
        for attribute in self.iter_attribute():
            result.setdefault(attribute.relationship, []).append(
                attribute.to_dict(expand_link, reverse_notate,
                                  truncate_result))
        for link in self.iter_link_as_entity1():
            if expand_link:
                entity2_dict = link.entity2.to_dict(
                    expand_link=False, reverse_notate=reverse_notate,
                    truncate_result=truncate_result)
                entity2_dict.pop(reverse_notation(link.entity2_role), None)
            else:
                entity2_dict = link.entity2.identifier
            result.setdefault(link.entity2_role, []).append(
                entity2_dict)
        for link in self.iter_link_as_entity2():
            et1r = link.entity1_role or reverse_notation(link.entity2_role)
            if expand_link:
                entity1_dict = link.entity1.to_dict(
                    expand_link=False, reverse_notate=reverse_notate,
                    truncate_result=truncate_result)
                entity1_dict.pop(et1r, None)
            else:
                entity1_dict = link.entity1.identifier
            result.setdefault(et1r, []).append(entity1_dict)
        skips = (self.ignores + self.relationship_keys
                 + [p['predicate'] for p in ATTRIBUTE_TYPES.values()])
        for p, o in self.predicate_objects():
            if p.identifier in skips:
                continue
            if isinstance(o, Entity):
                result.setdefault(p.identifier, []).append(o.identifier)
            else:
                result.setdefault(p.identifier, []).append(o)
        if truncate_result:
            truncate(result)
        if result.keys() == [self.collapse_on]:
            result = result[self.collapse_on]
        return result

    def jsonify(self, ns_to_remove=(lcc, chub), expand_link=True, **kw):
        """
        convert the entity object into json
        :returns: json
        """
        dict_no_ns = transform(
            lambda d: remove_matching_namespace(d, ns_to_remove),
            self.to_dict(expand_link))
        return json.dumps(shorten(dict_no_ns), **kw)

    def iter_attribute(self):
        """
        iterator of the sub entities
        :returns: generator of Entity instances
        """
        return iter_attribute(self)

    def iter_link_as_entity1(self):
        """
        iterator of the links where entity is mapped to lem.hasEntity1
        :returns: generator of Link instances
        """
        for link in self.graph.iter_link():
            if list(link.objects(predicate=lem.hasEntity1)) == [self]:
                yield link

    def iter_link_as_entity2(self):
        """
        iterator of the links where entity is mapped to lem.Entity2
        :returns: generator of Link instances
        """
        for link in self.graph.iter_link():
            if list(link.objects(predicate=lem.hasEntity2)) == [self]:
                yield link

    def iter_link(self):
        """
        iterator of the links where entity is part of the link
        :returns: generator of Link instances
        """
        return itertools.chain(self.iter_link_as_entity1(),
                               self.iter_link_as_entity2())


for entity_type in ATTRIBUTE_TYPES:
    # the following would not work somehow
    # partial(iter_attribute, entity_type=entity_type)
    def _make_func(func, et):
        return lambda g: func(g, et)
    func_name = 'iter_{}'.format(entity_type.split('#')[-1].lower())
    setattr(Entity, func_name, _make_func(iter_attribute, entity_type))


class Link(Entity):

    @property
    def entity1(self):
        """
        object to predicate lem.Entity1

        :returns: an entity instance
        """
        et1 = self.get_single_object(lem.hasEntity1)
        cls = get_cls(et1.entity_type)
        return cls(self.graph, et1.identifier)

    # TODO according to LCC model, there might be
    # multiple `Entity2`s. Deal with it when we come
    # across some real data to understand the semantics.
    @property
    def entity2(self):
        """
        object to predicate lem.hasEntity2

        :returns: an entity instance
        """
        et2 = self.get_single_object(lem.hasEntity2)
        cls = get_cls(et2.entity_type)
        return cls(self.graph, et2.identifier)

    @property
    def entity1_role(self):
        """
        Object to predicate lem.hasEntity1Role. If not present
        use reverse notation to construct one.
        :returns: a uriref instance
        """
        try:
            et1r = self.get_single_object(lem.hasEntity1Role)
            return et1r.identifier
        except InvalidEntity:
            return None

    @property
    def entity2_role(self):
        """
        Object to predicate lem.hasEntity2Role.
        :returns: a uriref instance
        """
        et2r = self.get_single_object(lem.hasEntity2Role)
        return et2r.identifier

    @property
    def link_type(self):
        """
        Type of the link
        """
        l_type = self.get_single_object(lem.hasLinkType)
        return l_type.identifier


def initialize(g):
    graph.Graph.__init__(g)
    for name, uri in NAMESPACES.iteritems():
        g.bind(name, uri)


Graph = type(b'Graph', (graph.Graph,), {'iter_entity': iter_entity,
                                        'minimize': minimize,
                                        '__init__': initialize})
for entity_type in ENTITY_TYPES:
    func_name = 'iter_{}'.format(entity_type.split('#')[-1].lower())

    # the following would not work somehow
    # partial(iter_entity, entity_type=entity_type)
    def _make_func(func, et):
        return lambda g: func(g, et)
    setattr(Graph, func_name, _make_func(iter_entity, entity_type))

for entity_type, entity_dict in ENTITY_TYPES.items():
    if entity_type in SUB_ENTITY_TYPES:
        continue
    cls_name = entity_type.split('#')[-1].encode()
    entity_dict['ignores'] = (entity_dict.get('ignores', [])
                              + Entity.ignores)
    cls = type(cls_name, (Entity,), entity_dict)
    globals().setdefault(cls_name, cls)

for sub_entity_type, sub_entity_dict in SUB_ENTITY_TYPES.items():
    cls_name = sub_entity_type.split('#')[-1].encode()
    parent_cls = get_cls(sub_entity_dict['parent'])
    cls = type(cls_name, (parent_cls,), sub_entity_dict)
    globals().setdefault(cls_name, cls)
