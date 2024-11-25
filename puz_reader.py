import puz
import json
import copy


def format_crossword_jsonl(
    prompt,
    size,
    across_clues,
    down_clues,
    across_answers,
    down_answers,
    with_answers=False,
):
    formatted = {
        "messages": [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": f"{{'size': {size}, 'across': {json.dumps(across_clues)},'down': {json.dumps(down_clues)}}}",
            },
        ],
    }

    if with_answers:
        formatted["messages"].append(
            {
                "role": "assistant",
                "content": f"{{'size': {size}, 'across': {json.dumps(across_answers)},'down': {json.dumps(down_answers)}}}",
            }
        )

    return formatted


def format_puz(filename, prompt, with_answers=False):
    p = puz.read(filename)
    numbering = p.clue_numbering()
    height = p.height
    width = p.width
    size = height * width
    across_clues = []
    across_answers = []
    for clue in numbering.across:
        clue.pop("clue_index")
        across_clues.append(clue)
        answer = copy.deepcopy(clue)
        answer["answer"] = "".join(
            p.solution[clue["cell"] + i] for i in range(clue["len"])
        )
        across_answers.append(answer)

    down_clues = []
    down_answers = []
    for clue in numbering.down:
        clue.pop("clue_index")
        down_clues.append(clue)
        answer = copy.deepcopy(clue)
        answer["answer"] = "".join(
            p.solution[clue["cell"] + i * numbering.width] for i in range(clue["len"])
        )
        down_answers.append(answer)

    return (
        size,
        format_crossword_jsonl(
            prompt,
            size,
            across_clues,
            down_clues,
            across_answers,
            down_answers,
            with_answers,
        ),
        across_answers,
        down_answers,
    )


import datetime
import calendar
from enum import IntEnum


def check_weekday_or_weekend(date):
    try:
        # Convert the input date string to a datetime object
        given_date = datetime.datetime.strptime(date, "%d %m %Y")

        # Use weekday() to get the weekday (Monday is 1 and Sunday is 7)
        day_of_week = (given_date.weekday() + 1) % 7  # Convert Sunday from 6 to 0

        # Determine if it's a weekday or a weekend
        if day_of_week < 5:
            day_type = "weekday"
        else:
            day_type = "weekend"

        # Print the result
        print(
            f"The day of the week for {given_date.strftime('%Y-%m-%d')} is {day_of_week} ({day_type})"
        )

    except ValueError as e:
        print(f"Error: {e}")


from pathlib import Path


def month_to_num(month):
    return {v: k for k, v in enumerate(calendar.month_abbr)}[month]


class DayOfWeek(IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


def is_file_on_day(filename, day_of_the_week):
    month, day, year = filename.stem[0:3], filename.stem[3:5], filename.stem[5:7]
    if year.startswith("9"):
        year = "19" + year
    else:
        year = "20" + year
    return (
        datetime.datetime(int(year), month_to_num(month), int(day)).weekday()
        == day_of_the_week.value
    )


def main():
    training_messages = []
    counter = 0
    for filename in Path("data/").rglob("*.puz"):
        counter += 1
        # only use one third the wednesday puzzles to train -- costs too much to use all
        if is_file_on_day(filename, DayOfWeek.WEDNESDAY) and counter % 3 == 0:
            try:
                (size, messages, across_answers, down_answers) = format_puz(
                    filename, with_answers=True
                )
                training_messages.append(messages)
            except Exception as e:
                print(f"Error: {e}")
                print(f"Skipping {filename}")

    with open("puz_dataset.jsonl", "w") as f:
        s = "\n".join(json.dumps(msg) for msg in training_messages)
        s = s.replace('\\"', "'")
        f.write(s)


if __name__ == "__main__":
    main()
