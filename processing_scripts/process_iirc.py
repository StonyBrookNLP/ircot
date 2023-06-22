from typing import Dict, List
import uuid
import random
import os

from rapidfuzz import fuzz
from tqdm import tqdm
from bs4 import BeautifulSoup

from lib import read_json, write_jsonl


random.seed(13370)  # Don't change.


def load_title_to_page_texts(articles_filepath: str) -> Dict[str, List[str]]:
    title_to_page_texts = {}
    raw_articles_data = read_json(articles_filepath)
    for title, page_html in tqdm(raw_articles_data.items()):
        page_soup = BeautifulSoup(page_html, "html.parser")
        page_texts = [text for text in page_soup.text.split("\n") if text.strip() and len(text.strip().split()) > 10]
        title_to_page_texts[title] = page_texts
    return title_to_page_texts


def main():

    articles_filepath = os.path.join("raw_data", "iirc", "context_articles.json")
    title_to_page_texts = load_title_to_page_texts(articles_filepath)

    set_names = ["train", "dev"]

    input_directory = os.path.join("raw_data", "iirc")
    output_directory = os.path.join("processed_data", "iirc")
    os.makedirs(output_directory, exist_ok=True)

    matching_para_count = 0
    total_para_count = 0
    for set_name in set_names:
        print(f"Processing {set_name}")

        processed_instances = []

        input_filepath = os.path.join(input_directory, f"{set_name}.json")
        output_filepath = os.path.join(output_directory, f"{set_name}.jsonl")

        data_objects = read_json(input_filepath)

        for _, data_object in tqdm(enumerate(data_objects)):
            main_passage_text = data_object["text"].strip()
            main_passage_title = data_object["title"].strip()
            main_passage_link_titles = [link["target"] for link in data_object["links"]]

            for question_object in data_object["questions"]:

                question_id = question_object.get("qid", uuid.uuid4().hex)

                raw_contexts = question_object["context"]

                question_text = question_object["question"]
                answer_object = question_object["answer"]

                supporting_title_paragraph_text_tuples = []
                for raw_context in raw_contexts:
                    snippet_text = raw_context["text"].strip()
                    title = raw_context["passage"].strip()

                    if title == "main":
                        # It'll be there in the pinned one.
                        continue

                    page_texts = title_to_page_texts[title.lower()]
                    if not page_texts:
                        print("WARNING: Title doesn't have any passage.")
                        best_matching_text = snippet_text

                    else:
                        page_texts_with_scores = []
                        for page_text in page_texts:
                            page_texts_with_scores.append(
                                {"text": page_text, "score": fuzz.partial_ratio(page_text, snippet_text)}
                            )
                        best_matching = sorted(page_texts_with_scores, key=lambda e: e["score"], reverse=True)[0]
                        best_matching_text = best_matching["text"].strip()
                        best_matching_score = best_matching["score"]

                        if best_matching_score > 90:
                            matching_para_count += 1
                        total_para_count += 1

                    if (title, best_matching_text) not in supporting_title_paragraph_text_tuples:
                        supporting_title_paragraph_text_tuples.append((title, best_matching_text))

                processed_contexts = [
                    {
                        "title": title.strip(),
                        "paragraph_text": paragraph_text.strip(),
                        "is_supporting": True,
                    }
                    for title, paragraph_text in supporting_title_paragraph_text_tuples
                ]

                distracting_title_paragraph_text_tuples = []
                for link_title in main_passage_link_titles:
                    if link_title.lower() not in title_to_page_texts:
                        print(f"WARNING: The distractor page title {link_title} not found.")
                        continue
                    page_texts = title_to_page_texts[link_title.lower()]
                    if not page_texts:
                        continue
                    page_text = random.choice(page_texts)
                    all_title_paragraph_text_tuples = (
                        supporting_title_paragraph_text_tuples + distracting_title_paragraph_text_tuples
                    )
                    if (link_title, page_text) not in all_title_paragraph_text_tuples:
                        distracting_title_paragraph_text_tuples.append((link_title, page_text))

                processed_contexts += [
                    {
                        "title": title.strip(),
                        "paragraph_text": paragraph_text.strip(),
                        "is_supporting": False,
                    }
                    for title, paragraph_text in distracting_title_paragraph_text_tuples
                ]

                random.shuffle(processed_contexts)

                for index, context in enumerate(processed_contexts):
                    context["idx"] = index

                if answer_object["type"] == "none":
                    continue
                elif answer_object["type"] == "span":
                    answer_list = [a["text"].strip() for a in answer_object["answer_spans"]]
                elif answer_object["type"] in ["binary", "value"]:
                    answer_list = [answer_object["answer_value"].strip()]
                else:
                    raise Exception("Unknown answer type.")

                answers_object = {"number": "", "date": {"day": "", "month": "", "year": ""}, "spans": answer_list}
                answers_objects = [answers_object]

                processed_instance = {
                    "question_id": question_id,
                    "question_text": question_text,
                    "answers_objects": answers_objects,
                    "contexts": processed_contexts,
                    "pinned_contexts": [
                        {
                            "idx": 0,
                            "title": main_passage_title.strip(),
                            "paragraph_text": main_passage_text.strip(),
                            "is_supporting": True,
                        }
                    ],
                    "valid_titles": main_passage_link_titles,
                }
                processed_instances.append(processed_instance)

        print("Para match count: " + str(matching_para_count))
        print("Para toal count: " + str(total_para_count))
        write_jsonl(processed_instances, output_filepath)


if __name__ == "__main__":
    main()
