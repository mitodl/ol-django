#!/usr/bin/env bash

function prune_if_too_big() {
   path=$1
   limit_mb=$2
   size_mb=$(du -m -d0 "${path}" | cut -f 1)
   if (( size_mb > limit_mb )); then
     echo "${path} is too large (${size_mb}mb), pruning it."
     rm -rf "${path}"
   fi
 }

prune_if_too_big ~/.cache/pants/setup 512
prune_if_too_big ~/.cache/pants/named_caches 1024