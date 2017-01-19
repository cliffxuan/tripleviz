#!/usr/bin/env bash
for ff in $(ls static/sampledata/*.ttl)
do
    
    echo "converting $ff"
    python triples.py $ff > $(sed "s/ttl/json/g" <<< $ff)
done
