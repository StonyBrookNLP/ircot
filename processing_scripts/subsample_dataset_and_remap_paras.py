import argparse
import random
import os

from tqdm import tqdm
from lib import read_jsonl, write_jsonl, find_matching_paragraph_text

random.seed(13370)  # Don't change this.


def main():

    parser = argparse.ArgumentParser(description="Save and sample data")
    parser.add_argument(
        "dataset_name", type=str, help="dataset name.", choices=("hotpotqa", "2wikimultihopqa", "musique", "iirc")
    )
    parser.add_argument("set_name", type=str, help="set name.", choices=("dev", "test"))
    args = parser.parse_args()

    avoid_question_ids_file_path = None
    sample_size = 100
    if args.set_name == "test":
        avoid_question_ids_file_path = os.path.join("processed_data", args.dataset_name, "dev_subsampled.jsonl")
        sample_size = 500

    input_file_path = os.path.join("processed_data", args.dataset_name, "dev.jsonl")
    instances = read_jsonl(input_file_path)

    if avoid_question_ids_file_path:
        avoid_ids = set([avoid_instance["question_id"] for avoid_instance in read_jsonl(avoid_question_ids_file_path)])
        instances = [instance for instance in instances if instance["question_id"] not in avoid_ids]

    instances = random.sample(instances, sample_size)

    for instance in tqdm(instances):
        for context in instance["contexts"]:

            if context in instance.get("pinned_contexts", []):
                # pinned contexts (iirc main) aren't in the associated wikipedia corpus.
                continue

            retrieved_result = find_matching_paragraph_text(args.dataset_name, context["paragraph_text"])

            if retrieved_result is None:
                continue

            context["title"] = retrieved_result["title"]
            context["paragraph_text"] = retrieved_result["paragraph_text"]

    output_file_path = os.path.join("processed_data", args.dataset_name, f"{args.set_name}_subsampled.jsonl")
    write_jsonl(instances, output_file_path)


if __name__ == "__main__":
    main()
