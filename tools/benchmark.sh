#!/bin/sh

# Copyright (c) 2024 Vaughan Kitchen
# from https://github.com/andrewtrotman/JASSjr

if [ $# -eq 0 ]; then
	echo "Usage: $0 <n> ./JASSjr_index test_documents.xml"
	echo "Usage: $0 <n> ./JASSjr_search < 51-100.titles.txt"
	exit
fi

# Read stdin to a string only if there is data waiting there
if [ ! -t 0 ]; then
	in=$(cat)
fi
iters="$1"
shift

echo "Benchmarking: $@"

# One run as a warmup
echo "Warmup"
"$@" > /dev/null

timings=''
for i in $(seq 1 "$iters"); do
	echo "Iteration $i"
	# Use system time command instead of shell builtin
	seconds=$( { printf '%s' "$in" | /usr/bin/time -p "$@" > /dev/null ; } 2>&1 | awk '/^real / {print $2; exit}' )
	timings="$timings$seconds
"
done

timings=$(printf '%s' "$timings" | sort -n)
fastest=$(printf '%s' "$timings" | head -n 1)
slowest=$(printf '%s' "$timings" | tail -n 1)
midpoint=$(( ($iters + 1) / 2 ))
median=$(printf '%s' "$timings" | head -n "$midpoint" | tail -n 1)

echo
echo "Fastest: $fastest"
echo "Slowest: $slowest"
echo "Median:  $median"
