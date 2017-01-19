Copyright Hub Triples
=====

This is a tool for visualising copyright data in triple fromat following the LCC specification.

A live instance is running at http://copyright-hub-triples.cde.org.uk:5000/

It is a web application with the front end using d3js and a simple python backend for data manipulation using the following two libraries.

* [rdflib](https://rdflib.readthedocs.org/en/latest/) parses triples in turtle format and turns them into an rdf graph
* [networkx](https://networkx.github.io/) converts the rdf graph into a network graph and serialises it into json that can be rendered by d3js

![Image of a sample triple visualisation](https://s3-eu-west-1.amazonaws.com/uploads-eu.hipchat.com/117358/865103/Qpbj3g5BlBZdIXz/triples.png)
