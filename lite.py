#
# (C) Copyright Connected Digital Economy Catapult Limited 2014
# All rights reserved
#

"""
# TODO
1. use mapping for minimizing the full LCC doc
2. a data model, possible a class for parsed graph, so a lot of the functions
and be a member of the class
3. do the same described in 1. for mapping
4. more error checking
5. insight into mapping rules
6. less imperative coding style. remove side effects. no mutation, etc.
"""
import json
import argparse
import sys
import os

from rdflib import Graph, Namespace, Literal, URIRef

SUPPORTED_FORMATS = ['turtle', 'xml', 'nt', 'json-ld']


chub = Namespace('http://www.copyrighthub.co.uk/2014/chub#')
hk = Namespace('http://www.copyrighthub.co.uk/2014/hk#')
lcc = Namespace('http://www.rightscom.com/2011/lcc#')
lem = Namespace('http://www.rightscom.com/2011/lem#')
rdi = Namespace('http://www.rightscom.com/2011/rdi#')
xs = Namespace('http://www.w3.org/2001/XMLSchema#')
xsd = Namespace('http://www.w3.org/2001/XMLSchema#')

NS = dict(chub=chub, hk=hk, lcc=lcc, lem=lem, rdi=rdi, xs=xs, xsd=xsd)

PWD = os.path.dirname(__file__)
MAPPING_DIR = os.path.join(PWD, 'static/mappings')
DEFAULT_MAPPING = os.path.join(MAPPING_DIR, 'default.json')


class DataError(Exception):
    """
    Exception to throw when there is error in the source doc
    """
    pass


class SkipTriple(Exception):
    """
    Flow control for skip processing a triple.
    """
    pass


def parse(data, source_format):
    """
    turn a rdflib.Graph into a dictionary of format
    {object: {predicate: [subject]}}
    """
    g = Graph()
    g.parse(data=data, format=source_format)
    result = {}
    for subject, predicate, obj in g:
        result.setdefault(subject, {}).setdefault(predicate, []).append(obj)
    return result


def iter_result(result):
    """
    iterate the dictionary created by parse, i.e.
    dictionary of format {object: {predicate, [subject]}}
    """
    for subject, vs in result.iteritems():
        for predicate, objects in vs.iteritems():
            for obj in objects:
                yield subject, predicate, obj


def analyse_categories(result):
    categories = {}
    for k, v in result.iteritems():
        if lcc.CategoryType in v:
            for ct in v[lcc.CategoryType]:
                categories.setdefault(
                    ct, []).extend(v[lcc.CategoryValue])
    return categories


def trim_uriref(item):
    return item.split('/')[-1].replace('#', ':').encode('utf-8')


def expand_uriref(item):
    try:
        ns, val = item.split(':')
        return NS[ns][val]
    except ValueError:
        return item


def flatten(pre_to_objs, ignores=None):
    """
    flatten a predicate to objects mapping
    :return: tuple of ((predicate, object))
    """
    if not ignores:
        ignores = []
    pre_obj_tuple = tuple(sorted(
        (pre, obj) for (pre, objs)
        in pre_to_objs.iteritems() for obj in objs
        if pre not in ignores))
    return pre_obj_tuple


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


def collapse_categories(result):
    mapping = {}
    errors = []

    def _collapse_category(cat, cid):
        if len(cat[lcc.CategoryType]) > 1:
            raise DataError(
                'more than one CategoryType for Category {}'.format(cid))
        else:
            cat_type = cat[lcc.CategoryType][0]
        if len(cat[lcc.CategoryValue]) > 1:
            raise DataError(
                'more than one CategoryValue for Category {}'.format(cid))
        else:
            cat_val = cat[lcc.CategoryValue][0]
        mapping_val = flatten(cat, ignores=[])
        if len(mapping_val) > 3:
            error = (
                'expect 3 triples from a Category,'
                ' got {} from {}'
            ).format(len(mapping_val),
                     shorten(cid))
            raise DataError(error)
        mapping_key = (cat_type, cat_val)
        return mapping_key, mapping_val, cat_type, cat_val

    entity_to_categories = {
        k: v.pop(lcc.Category)
        for k, v in result.iteritems()
        if lcc.Category in v}

    for entity, categories in entity_to_categories.iteritems():
        for cid in categories:
            try:
                category = result.pop(cid)
                m_key, m_val, r_key, r_val = _collapse_category(category, cid)
            except DataError as exc:
                errors.append(exc)
            else:
                result[entity].setdefault(r_key, []).append(r_val)
                mapping.setdefault(m_key, set()).add(m_val)
    return mapping, errors


def collapse_descriptors(result):
    mapping = {}
    errors = []

    def _collapse_descriptor(des, did):
        if len(des[lcc.DescriptorSubType]) > 1:
            raise DataError((
                'more than one DescriptorSubType for Descriptor {}'
                ).format(did))
        else:
            des_sub_type = des[lcc.DescriptorSubType][0]
        if len(des[lcc.DescriptorValue]) > 1:
            raise DataError((
                'more than one DescriptorValue for Descriptor {}'
                ).format(did))
        else:
            des_value = des[lcc.DescriptorValue][0]
        flattened = flatten(des, ignores=[chub.ReferenceID,
                                          lcc.DescriptorValue])
        if len(flattened) > 3:
            error = (
                'expect 3 triples from a descriptor,'
                ' got {} from {}'
            ).format(len(flattened), shorten(did))
            raise DataError(error)
        return des_sub_type, flattened, des_sub_type, des_value

    entity_to_descriptors = {
        k: v.pop(lcc.Descriptor)
        for k, v in result.iteritems()
        if lcc.Descriptor in v}

    for entity, descriptors in entity_to_descriptors.iteritems():
        for did in descriptors:
            try:
                descriptor = result.pop(did)
            except KeyError:
                msg = (
                    'Descriptor {} is referenced by'
                    ' {} but is missing from the document.'
                ).format(shorten(did), shorten(entity))
                errors.append(DataError(msg))
                continue
            try:
                m_key, m_val, r_key, r_val = _collapse_descriptor(
                    descriptor, did)
            except DataError as exc:
                errors.append(exc)
            else:
                result[entity].setdefault(r_key, []).append(r_val)
                mapping.setdefault(m_key, set()).add(m_val)
    return mapping, errors


def collapse_links(result):
    mapping = {}
    errors = []

    # TODO too loooong
    def _collapse_link(k, v):
        if lcc.Link in v[lcc.EntityType]:
            if len(v[lcc.EntityType]) > 1:
                raise DataError(
                    'more than one EntityType found for {}'.format(
                        shorten(v[chub.ReferenceID][0])))
            result.pop(k)
            for entity in ['Entity1', 'Entity2', 'Entity1Role', 'Entity2Role']:
                if len(v.get(lcc[entity], [])) > 1:
                    raise DataError((
                        'more than one {} for Link {}'
                        ).format(entity, shorten(k)))
            entity1 = v[lcc.Entity1][0]
            entity2 = v[lcc.Entity2][0]
            linktype = v[lcc.LinkType][0]

            try:
                entity1_role = v.get(lcc.Entity1Role, [])[0]
            except IndexError:
                entity1_role = ''

            # should always has Entity2Role
            entity2_role = v.get(lcc.Entity2Role, [])[0]

            mapping_key = (result[entity1][lcc.EntityType][0],
                           entity2_role,
                           result[entity2][lcc.EntityType][0],
                           linktype)
            result[entity1].setdefault(entity2_role, []).append(entity2)
            flattened = flatten(
                v, ignores=[lcc.Entity1, lcc.Entity2])
            if len(flattened) not in (3, 4):
                error = (
                    'expect 3 or 4 triples from a Link,'
                    ' got {} from {}'
                ).format(len(flattened),
                         shorten(v[chub.ReferenceID][0]))
                raise DataError(error)
            mapping.setdefault(mapping_key, set()).add(flattened)

            if not entity1_role:
                return
            result[entity2].setdefault(entity1_role, []).append(entity1)
            mapping_key = (result[entity2][lcc.EntityType][0],
                           entity1_role,
                           result[entity1][lcc.EntityType][0],
                           linktype)
            flattened = flatten(
                v, ignores=[lcc.Entity1, lcc.Entity2])
            mapping.setdefault(mapping_key, set()).add(flattened)

    for k, v in result.copy().iteritems():
        try:
            _collapse_link(k, v)
        except DataError as exc:
            errors.append(exc)
    return mapping, errors


def update_entity_predicates(result, entity_type, key):
    errors = []

    def _update_entity_predicate(attribute, attribute_id):
        if len(attribute[key]) > 1:
            raise DataError((
                'more than one {} found for {} {}'
                ).format(key, entity_type, attribute_id))
        else:
            attribute_type = attribute.pop(key)[0]
        return attribute_type, attribute_id

    entity_to_quantities = {
        k: v.pop(entity_type)
        for k, v in result.iteritems()
        if entity_type in v
    }

    for entity, attributes in entity_to_quantities.iteritems():
        for attribute_id in attributes:
            try:
                attribute = result.get(attribute_id)
                r_key, r_val = _update_entity_predicate(
                    attribute, attribute_id)
            except DataError as exc:
                errors.append(exc)
            else:
                result[entity].setdefault(r_key, []).append(r_val)

    return errors


def serialize(result, format):
    g = Graph()
    map(g.add, iter_result(result))
    for ns, url in extract_namespaces(g).iteritems():
        g.bind(ns, url)
    return g.serialize(format=format)


def transform(trans_f, data):
    """
    apply a function on all elements of the data and retain the structure
    """
    if type(data) == dict:
        return dict(map(lambda d: transform(trans_f, d), data.iteritems()))
    elif type(data) in [list, tuple, set]:
        return type(data)(map(lambda d: transform(trans_f, d), data))
    else:
        return trans_f(data)


def shorten(data):
    """
    remove the node urls and retain the data structure, so it's readable
    """
    return transform(trim_uriref, data)


def non_unique_mapping(mapping):
    return {k: v for k, v in mapping.iteritems() if len(v) > 1}


def minimize(source, source_format):
    result = parse(source, source_format)
    cat_mapping, cat_errors = collapse_categories(result)
    desc_mapping, des_errors = collapse_descriptors(result)
    link_mapping, link_errors = collapse_links(result)
    quantity_errors = update_entity_predicates(
        result, lcc.Quantity, lcc.QuantityType)
    time_errors = update_entity_predicates(
        result, lcc.Time, lcc.TimeType)

    mapping = {
        "Category": cat_mapping,
        "Descriptor": desc_mapping,
        "Link": link_mapping,
    }
    errors = (
        cat_errors + des_errors + link_errors + quantity_errors + time_errors
    )
    errors = '\n'.join(error.args[0] for error in errors)
    return result, mapping, errors


def print_mapping(all_mapping):

    def _format_mapping(mapping):
        for k, vs in mapping.iteritems():
            print("{} => ".format(k))
            if type(vs) in (list, set):
                for v in vs:
                    if len(vs) > 1:
                        print('\t+')
                    if type(v) == tuple:
                        for i in v:
                            print'\t', i
                    else:
                        print'\t', v
            elif type(vs) == tuple:
                for v in vs:
                    print'\t', v

    for name, mapping in all_mapping.iteritems():
        print('=' * 40)
        print('mapping rule for {}'.format(name))
        _format_mapping(transform(trim_uriref, mapping))
        non_unique = non_unique_mapping(mapping)
        print('*' * 20)
        if non_unique:
            print('non unique mapping')
            _format_mapping(transform(trim_uriref, non_unique))
        else:
            print ('all mapping unique!')
        print('*' * 20)


def predicates(filename, source_format):
    g = Graph()
    g.parse(filename, format=source_format)
    pres = set([p for (s, p, o) in g])
    print('\n'.join(trim_uriref(p) for p in pres))
    print(len(pres))
    return pres


def serialize_mappings(mappings):
    transformed = transform(trim_uriref, mappings)

    def _serialize_mapping(m):
        result = {}
        for k, vs in m.iteritems():
            if type(k) == tuple:
                key = ' '.join(k)
            else:
                key = k
            val = [[' '.join(i) for i in v] for v in vs]
            if len(val) == 1:
                val = val[0]
            result[key] = val
        return result

    obj = {k: _serialize_mapping(mapping) for k, mapping
           in transformed.iteritems()}
    return json.dumps(obj, indent=2, sort_keys=True)


def parse_urirefs(urirefs):
    """
    urirefs: string of abbrev urirefs, e.g. "lcc:EntityType lcc:Category"
    """
    parsed = tuple(expand_uriref(item) for item in urirefs.split(' '))
    if len(parsed) == 1:
        return parsed[0]
    else:
        return parsed


def parse_mappings(mappings):
    """
    mappings: json string
    """
    def _parse_mapping(mapping):
        result = {}
        for ks, vs in mapping.iteritems():
            key = parse_urirefs(ks)
            # multiple mapping rules
            if type(vs[0]) == list:
                val = [tuple(parse_urirefs(item) for item in v)
                       for v in vs]
            else:
                val = tuple(parse_urirefs(v) for v in vs)
            result[key] = val
        return result

    return {k: _parse_mapping(mapping) for k, mapping
            in json.loads(mappings).iteritems()}


def restore_category(mappings, subject, predicate, obj, cat):
    """
    retore Category entity type
    """
    cat_p_o_list = mappings['Category'].get((predicate, obj))
    result = []
    if cat_p_o_list:
        for p, o in cat_p_o_list:
            result.append((cat, p, o))
        result.append((subject, lcc.Category, cat))
    return result


def restore_descriptor(mappings, subject, predicate, obj, des):
    """
    retore Descriptor entity type
    """
    des_p_o_list = mappings['Descriptor'].get(predicate)
    result = []
    if des_p_o_list:
        result.append((des, chub.ReferenceID, Literal(des.split('#')[-1])))
        result.append((des, lcc.DescriptorValue, obj))
        for p, o in des_p_o_list:
            result.append((des, p, o))
        result.append((subject, lcc.Descriptor, des))
    return result


# TODO move it into its own module. extract the private functions.
def restore_link(parsed_graph, mappings, subject, predicate, obj, link):
    """
    retore Link entity type
    """

    def _match(key):
        subj_type, pred, obj_type, context = key
        result = True
        result = result and (
            subj_type == parsed_graph[subject][lcc.EntityType][0])
        result = result and pred == predicate
        try:
            cond = obj_type == parsed_graph[obj][lcc.EntityType][0]
        except KeyError:
            cond = False
        result = result and cond
        return result

    def _1_or_2(key, p_o_tuple):
        """is current subject Entity1 or Entity2?"""
        subj_type, pred, obj_type, context = key
        p_to_o = dict(p_o_tuple)
        if p_to_o.get(lcc.Entity2Role) == predicate:
            return 1
        else:
            return 2

    def _reverse_match(item):
        key, p_o_tuple = item
        p_to_o = dict(p_o_tuple)
        is_1_2 = _1_or_2(key, p_o_tuple)
        lookup = parsed_graph[obj]
        if is_1_2 == 1:
            return item if subject in lookup.get(
                p_to_o[lcc.Entity1Role], []) else None
        elif is_1_2 == 2:
            return item if subject in lookup.get(
                p_to_o[lcc.Entity2Role], []) else None

    def _get_candidates():
        candidates = []
        for matched_key in filter(_match, mappings['Link'].keys()):
            p_o_tuple = mappings['Link'][matched_key]
            # multiple mappings
            if type(p_o_tuple) == list:
                candidates += [(matched_key, item) for item in p_o_tuple]
            else:
                candidates.append((matched_key, p_o_tuple))
        return candidates

    def _get_match(candidates):
        if len(candidates) == 1:
            match = candidates[0]
        elif len(candidates) > 1:
            reverse_matches = filter(_reverse_match, candidates)
            if len(reverse_matches) == 0:
                raise DataError('Could not find match')
            elif len(reverse_matches) == 1:
                match = reverse_matches[0]
            else:
                raise DataError(
                    'Multiple matches found.')
        return match

    def _create_triples(match):
        result = []
        is_1_2 = _1_or_2(*match)
        # only create link from Entity1
        if is_1_2 == 1:
            result.append((link, lcc.Entity1, subject))
            result.append((link, lcc.Entity2, obj))
            for p, o in match[1]:
                result.append((link, p, o))
        else:
            # skip it as it will be added from Entity1
            raise SkipTriple

        return result

    candidates = _get_candidates()
    if candidates:
        return _create_triples(_get_match(candidates))


def restore(source, source_format, json_mapping):
    """
    retore the lite doc using mapping rules in json
    """
    result = parse(source, source_format)
    new_graph = Graph()
    mappings = parse_mappings(json_mapping)

    counts = {subject: [0, 0, 0] for subject in result}

    for subject, predicate, obj in iter_result(result):
        subject_id = subject.split('#')[-1]

        cat = hk['{}_C{}'.format(subject_id, counts[subject][0] + 1)]

        des = hk['{}_D{}'.format(subject_id, counts[subject][1] + 1)]
        link = hk['{}_LINK{}'.format(subject_id, counts[subject][2] + 1)]

        try:
            cat_triples = restore_category(
                mappings, subject, predicate, obj, cat)
            des_triples = restore_descriptor(
                mappings, subject, predicate, obj, des)
            link_triples = restore_link(
                result, mappings, subject,
                predicate, obj, link)
        except SkipTriple:
            continue

        if cat_triples:
            map(new_graph.add, cat_triples)
            counts[subject][0] += 1
        elif des_triples:
            map(new_graph.add, des_triples)
            counts[subject][1] += 1
        elif link_triples:
            map(new_graph.add, link_triples)
            counts[subject][2] += 1
        else:
            new_graph.add((subject, predicate, obj))

    for ns, url in extract_namespaces(new_graph).iteritems():
        new_graph.bind(ns, url)
    return new_graph


def mapping_filename(source_filename):
    parts = os.path.basename(source_filename).split('.')
    if len(parts) == 1:
        ins = source_filename
    else:
        ins = '.'.join(parts[:-1])
    return os.path.join(MAPPING_DIR, 'mappings.{}.json'.format(ins))


# TODO functionality more insight
def compare_docs(res1, res2):
    """
    compare two parsed docs by parse()
    """
    diff = []
    if len(res1) != len(res2):
        diff.append((
            'different numbers of objects'
            ' origin:{} vs restored:{}'
        ).format(len(res1), len(res2)))
    cnt_triples_1 = len(tuple(iter_result(res1)))
    cnt_triples_2 = len(tuple(iter_result(res2)))
    if cnt_triples_1 != cnt_triples_2:
        diff.append((
            'different numbers of triples'
            ' origin:{} vs restored:{}'
        ).format(cnt_triples_1, cnt_triples_2))
    return diff


# TODO use subparser to separate different tasks
def argument_parser():
    parser = argparse.ArgumentParser(
        description='describe me')
    parser.add_argument(
        'task', choices=['min', 'max', 'pre'],
        help='task name')
    parser.add_argument(
        'filename', type=argparse.FileType('r'),
        help='name of the file to convert')
    parser.add_argument(
        '--source_format', '-sf', default='turtle',
        choices=SUPPORTED_FORMATS,
        help='source format')
    parser.add_argument(
        '--target_format', '-tf', default='turtle',
        choices=SUPPORTED_FORMATS,
        help='target format')
    parser.add_argument(
        '--mapping', '-mp', type=argparse.FileType('r'),
        default=DEFAULT_MAPPING,
        help='mapping file')
    return parser


def main(argv=None):
    args = argument_parser().parse_args(argv)
    if args.task == 'min':
        result, mapping, errors = minimize(args.filename.read(),
                                           args.source_format)
        serialized = serialize(result, args.target_format)
        sys.stdout.write(serialized)
        if errors:
            sys.stderr.write('!!! Errors found in the documents:\n')
            sys.stderr.write(errors)
        mapping = serialize_mappings(mapping)
        with open(mapping_filename(args.filename.name), 'w') as ff:
            ff.write(mapping)

        try:
            g = restore(serialized,
                        args.target_format,
                        mapping)
        except Exception:
            sys.stderr.write("minimizing cannot be reversed!")
            raise
        else:
            diff = compare_docs(
                parse(open(args.filename.name, 'r').read(),
                      args.source_format),
                parse(g.serialize(format='turtle'), 'turtle'))
            sys.stderr.write("\n".join(diff))
    elif args.task == 'pre':
        predicates(args.filename, args.source_format)
    elif args.task == 'max':
        graph = restore(args.filename.read(),
                        args.source_format,
                        args.mapping.read())
        print graph.serialize(format=args.target_format)


if __name__ == '__main__':
    main()
