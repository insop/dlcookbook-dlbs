#!/bin/bash
tar cvzf dlbs_$(date -u +%Y%m%d-%H%M%S%Z).tgz dlbs \
    --exclude="Anac*sh" \
    --exclude="__pycache__" \
    --exclude="*.log" \
    --exclude="*.deb" \
    --exclude="*.whl" \
    --exclude="*.pyc" \
    --exclude="*.tgz" \
    --exclude="*.txz" \
    --exclude="*.tbz" \
    --exclude="*.tar" \
    --exclude="*.img" \
    --exclude="*.tar.gz" 
