#!/bin/bash
set -eu

AAAI=$HOME/AAAI-24/AAAI-2024-Supplementary

if [ "$#" -ne 1 ]; then
  echo "Pass 1 argument: SAT-comp instance name" >&2
  exit 2
fi

name=$1
echo "Preparing '$name'..."

mkdir $name
cd $name
ln -s $AAAI/data/satcomp/$name.cnf original.cnf
ln -s $AAAI/scripts/run.sh
ln -s $AAAI/scripts/solve.sh
ln -s $AAAI/scripts/solve-jobqueue.sh

echo "Done preparing '$name'"
