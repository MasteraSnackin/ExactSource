#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "Usage: ./run.sh /absolute/path/to/dataset /absolute/path/to/out" >&2
    exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required but was not found." >&2
    exit 1
fi

if [ -z "${TINKER_API_KEY:-}" ]; then
    echo "TINKER_API_KEY is required in the current environment." >&2
    exit 1
fi

dataset_input=$1
output_input=$2

if [ ! -d "$dataset_input" ] || [ ! -f "$dataset_input/dataset.json" ]; then
    echo "The dataset path must be a directory containing dataset.json." >&2
    exit 1
fi

mkdir -p "$output_input"
dataset_path=$(cd "$dataset_input" && pwd -P)
output_path=$(cd "$output_input" && pwd -P)
script_path=$(CDPATH= cd "$(dirname "$0")" && pwd -P)

case "$output_path/" in
    "$dataset_path/"*)
        echo "The output directory must not be inside the read-only dataset directory." >&2
        exit 1
        ;;
esac

case "$dataset_path/" in
    "$output_path/"*)
        echo "The dataset directory must not be inside the output directory." >&2
        exit 1
        ;;
esac

docker build --tag exactsource:local "$script_path"
docker run --rm \
    --env TINKER_API_KEY \
    --volume "$dataset_path:/data:ro" \
    --volume "$output_path:/out" \
    exactsource:local
