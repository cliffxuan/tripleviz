#
# (C) Copyright Connected Digital Economy Catapult Limited 2014
# All rights reserved
#
import sys

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, class_mapper
from sqlalchemy import create_engine
from rdflib.graph import Graph, Resource

from lite import lcc, trim_uriref


Base = declarative_base()

KEY = String(32)


class Entity(Base):

    id = Column(KEY, primary_key=True)
    entity_type = Column('lcc:EntityType', Text)

    __tablename__ = 'entity'
    __mapper_args__ = {
        'polymorphic_identity': 'entity',
        'polymorphic_on': entity_type
    }


class Category(Entity):

    id = Column(KEY, ForeignKey('entity.id'), primary_key=True)
    type = Column('lcc:CategoryType', Text)
    value = Column('lcc:CategoryValue', Text)
    entity_id = Column(KEY, ForeignKey('entity.id'))
    entity = relationship("Entity", foreign_keys=[entity_id])

    __tablename__ = 'category'
    __mapper_args__ = {
        "inherit_condition": id == Entity.id,
        'polymorphic_identity': 'lcc:Category',
    }


class Descriptor(Entity):

    id = Column(KEY, ForeignKey('entity.id'), primary_key=True)
    ref = Column('chub:ReferenceID', Text)
    type = Column('lcc:DescriptorType', Text)
    subtype = Column('lcc:DescriptorSubType', Text)
    value = Column('lcc:DescriptorValue', Text)
    entity_id = Column(KEY, ForeignKey('entity.id'))
    entity = relationship("Entity", foreign_keys=[entity_id])

    __tablename__ = 'descriptor'
    __mapper_args__ = {
        "inherit_condition": id == Entity.id,
        'polymorphic_identity': 'lcc:Descriptor',
        }


class Link(Entity):

    id = Column(KEY, ForeignKey('entity.id'), primary_key=True)
    entity1_id = Column('lcc:Entity1', KEY, ForeignKey('entity.id'))
    entity1 = relationship('Entity', foreign_keys=[entity1_id])
    entity2_id = Column('lcc:Entity2', KEY, ForeignKey('entity.id'))
    entity2 = relationship('Entity', foreign_keys=[entity2_id])
    entity1_role = Column('lcc:Entity1Role', Text)
    entity2_role = Column('lcc:Entity2Role', Text)
    link_type = Column('lcc:LinkType', Text)

    __tablename__ = 'link'
    __mapper_args__ = {
        "inherit_condition": id == Entity.id,
        'polymorphic_identity': 'lcc:Link',
        }


class Quantity(Entity):
    id = Column(KEY, ForeignKey('entity.id'), primary_key=True)
    ref = Column('chub:ReferenceID', Text)
    mode = Column('lcc:QuantityMode', Text)
    type = Column('lcc:QuantityType', Text)
    proximity = Column('lcc:SingleQuantityProximity', Text)
    value = Column('lcc:SingleQuantityValue', Text)
    unit = Column('lcc:UnitOfMeasure', Text)
    entity_id = Column(KEY, ForeignKey('entity.id'))
    entity = relationship("Entity", foreign_keys=[entity_id])

    __tablename__ = 'quantity'
    __mapper_args__ = {
        "inherit_condition": id == Entity.id,
        'polymorphic_identity': 'lcc:Quantity',
        }


class Time(Entity):

    id = Column(KEY, ForeignKey('entity.id'), primary_key=True)
    ref = Column('chub:ReferenceID', Text)
    mode = Column('lcc:TimeMode', Text)
    type = Column('lcc:TimeType', Text)
    point_value = Column('lcc:TimepointValue', Text)
    point_proximity = Column('lcc:TimepointProximity', Text)
    start_value = Column('lcc:PeriodStartValue', Text)
    start_proximity = Column('lcc:PeriodStartProximity', Text)
    end_value = Column('lcc:PeriodEndValue', Text)
    end_proximity = Column('lcc:PeriodEndProximity', Text)
    entity_id = Column(KEY, ForeignKey('entity.id'))
    entity = relationship("Entity", foreign_keys=[entity_id])

    __tablename__ = 'time'
    __mapper_args__ = {
        "inherit_condition": id == Entity.id,
        'polymorphic_identity': 'lcc:Time',
        }


class Party(Entity):

    id = Column(KEY, ForeignKey('entity.id'), primary_key=True)
    ref = Column('chub:ReferenceID', Text)
    categories = relationship("Category", backref="party")
    descriptors = relationship("Descriptor", backref="party")

    __tablename__ = 'party'
    __mapper_args__ = {
        'polymorphic_identity': 'lcc:Party',
    }


class Context(Entity):

    id = Column(KEY, ForeignKey('entity.id'), primary_key=True)
    ref = Column('chub:ReferenceID', Text)
    categories = relationship("Category", backref="context")
    descriptors = relationship("Descriptor", backref="context")

    __tablename__ = 'context'
    __mapper_args__ = {
        'polymorphic_identity': 'lcc:Context',
    }


class Creation(Entity):

    id = Column(KEY, ForeignKey('entity.id'), primary_key=True)
    ref = Column('chub:ReferenceID', Text)
    categories = relationship("Category", backref="creation")
    descriptors = relationship("Descriptor", backref="creation")

    __tablename__ = 'creation'
    __mapper_args__ = {
        'polymorphic_identity': 'lcc:Creation',
    }


def create_db():
    # engine = create_engine('sqlite:///foo.sqlite', echo=True)
    engine = create_engine('mysql://user:password@localhost', echo=True)
    engine.execute('drop database if exists lcc')
    engine.execute('create database lcc')
    engine.execute('use lcc')
    Base.metadata.create_all(engine)
    return engine


def make_session(engine):
    Session = sessionmaker()
    Session.configure(bind=engine)
    return Session()


def parse_graph(filename):
    graph = Graph()
    graph.parse(filename, format='turtle')
    return graph


def predicate_to_objects(resource):
    pre_to_objs = {}
    for pre, obj in resource.predicate_objects():
        pre_to_objs.setdefault(pre.identifier, []).append(obj)
    return pre_to_objs


def parse_entity(session, entity, Klass):
    pre_to_objs = predicate_to_objects(entity)

    def _link_child_entity(row, ChildKlass):
        children = pre_to_objs.pop(lcc[ChildKlass.__name__], [])
        for child in children:
            child_row = session.query(ChildKlass).filter_by(
                id=trim_uriref(child.identifier)).one()
            child_row.entity = row

    row = Klass(id=trim_uriref(entity.identifier))
    for ChildKlass in (Category, Descriptor, Quantity, Time):
        _link_child_entity(row, ChildKlass)
    mapping = {v.name: k for k, v in class_mapper(Klass).c.items()}
    for pre, objs in pre_to_objs.iteritems():
        if len(objs) > 1:
            raise Exception('wrong data')
        key = mapping.get(trim_uriref(pre))
        if key:
            if type(objs[0]) == Resource:
                setattr(row, key, trim_uriref(objs[0].identifier))
            else:
                setattr(row, key, trim_uriref(objs[0]))
    return row


def main():
    engine = create_db()
    session = make_session(engine)
    graph = parse_graph(sys.argv[1])

    # this order is important
    for Klass in (Category, Descriptor, Quantity, Time,
                  Party, Context, Creation, Link):
        entities = (Resource(graph, subj) for subj in graph.subjects(
                    predicate=lcc.EntityType, object=lcc[Klass.__name__]))
        rows = map(lambda entity: parse_entity(session, entity, Klass),
                   entities)
        map(session.add, rows)
    session.commit()


if __name__ == '__main__':
    main()
