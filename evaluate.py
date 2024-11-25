from numpy import fix
from openai import OpenAI
import plotly.express as px
import pandas
import time
import puz_reader
import datetime
from pathlib import Path
import json_repair
from puz_reader import DayOfWeek

from prompt import (
    SYSTEM_PROMPT_with_much_prompt_eng,
    SYSTEM_PROMPT_with_little_prompt_eng,
    SYSTEM_PROMPT,
    CHATGPT_PROMPT,
    BASIC_PROMPT,
)


def calculate_accuracy(result, across_answers, down_answers):
    num_correct = 0
    total_clues = len(across_answers) + len(down_answers)
    # compare the answers in result with across and down answers
    llm_across = {llm["num"]: llm["answer"].upper() for llm in result["across"]}
    for answer in across_answers:
        num = answer["num"]
        if num in llm_across.keys():
            if llm_across[num] == answer["answer"]:
                num_correct += 1
        else:
            print(num, llm_across.keys())
            print("num not found in answers!")

    llm_down = {llm["num"]: llm["answer"].upper() for llm in result["down"]}
    for answer in down_answers:
        num = answer["num"]
        if num in llm_down.keys():
            if llm_down[num] == answer["answer"]:
                num_correct += 1
        else:
            print(num, llm_down.keys())
            print("num not found in answers!")

    return num_correct, total_clues


def run_evalutation(which_model, prompt, filename):
    try:
        (size, messages, across_answers, down_answers) = puz_reader.format_puz(
            filename, prompt
        )
    except Exception as e:
        print()
        print(f"Failed to read puzfile: {filename}\nError: {e}")
        return None

    completion = client.chat.completions.create(
        model=which_model,
        messages=messages["messages"],
    )

    try:
        result = completion.choices[0].message.content
        result = json_repair.loads(result)
    except Exception as e:
        print(f"1 Error: {e}")
        return None

    try:
        num_correct, total_clues = calculate_accuracy(
            result, across_answers, down_answers
        )
        return num_correct / total_clues
    except Exception as e:
        print(f"Failed to calculate Accuracy: {e}")
        return None


client = OpenAI()


def run_batch_evaluations():
    # Grab all the puz files.
    puzfiles = [
        filename for filename in Path("evaluation_data_same_data/").rglob("*.puz")
    ]

    # Split the puz files based on the day of the week.
    puzfiles_by_day = {
        day: [
            filename
            for filename in puzfiles
            if puz_reader.is_file_on_day(filename, day)
        ]
        for day in DayOfWeek
    }

    # Downsample eah day to 1/3 of the puzzles.
    # for day, files in puzfiles_by_day.items():
    #     puzfiles_by_day[day] = files[::10000]
    #     assert len(puzfiles_by_day[day]) < 30, f"len {len(puzfiles_by_day[day])}"
    #     assert len(puzfiles_by_day[day]) > 0, f"len {len(puzfiles_by_day[day])}"

    prompts = {
        "basic prompting": BASIC_PROMPT,
        "prompt engineering": CHATGPT_PROMPT,
    }
    models = {
        "gpt-4o-mini": "gpt-4o-mini-2024-07-18",
        "fine-tuned-model": "ft:gpt-4o-mini-2024-07-18:emily::AWu0pdVk",
    }
    days = {
        "monday": DayOfWeek.MONDAY,
        "tuesday": DayOfWeek.TUESDAY,
        "wednesday": DayOfWeek.WEDNESDAY,
    }

    jobs = {}
    # Run the evaluation in parallel using thread pool
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1000) as exe:
        for model_name, model in models.items():
            jobs[model_name] = {}
            for prompt_name, prompt in prompts.items():
                jobs[model_name][prompt_name] = {}
                for day_name, day in days.items():
                    jobs[model_name][prompt_name][day_name] = []
                    for filename in puzfiles_by_day[day]:
                        jobs[model_name][prompt_name][day_name].append(
                            exe.submit(run_evalutation, model, prompt, filename)
                        )

        # Wait for all the evaluations to finish
        all_done = False
        seconds = 0
        while not all_done:
            time.sleep(1)
            seconds += 1
            num_done = 0
            total = 0
            all_done = True
            for model_name, model_jobs in jobs.items():
                for prompt_name, prompt_jobs in model_jobs.items():
                    for day_name, day_jobs in prompt_jobs.items():
                        for job in day_jobs:
                            total += 1
                            if not job.done():
                                all_done = False
                            else:
                                num_done += 1
            print(f"\r{seconds}s: {num_done} / {total}", end="", flush=True)

        results = {}
        for model_name, model_jobs in jobs.items():
            results[model_name] = {}
            for prompt_name, prompt_jobs in model_jobs.items():
                results[model_name][prompt_name] = {}
                for day_name, day_jobs in prompt_jobs.items():
                    results[model_name][prompt_name][day_name] = []
                    for job in day_jobs:
                        results[model_name][prompt_name][day_name].append(job.result())

        print(results)
        return results


def convert_result_to_df(result):
    rows = []
    for model, model_results in result.items():
        for prompt, prompt_results in model_results.items():
            for day, accuracies in prompt_results.items():
                accuracies = [a for a in accuracies if a is not None]
                average_accuracy = sum(accuracies) / len(accuracies)
                rows.append(
                    {
                        "model + prompt": f"{model} + {prompt}",
                        "day": day,
                        "accuracy": average_accuracy,
                    }
                )
    return pandas.DataFrame(rows)


def convert_results_to_csv(results):
    # Convert results into a csv
    collapsed = {}
    for model, model_results in results.items():
        for prompt, prompt_results in model_results.items():
            for day, accuracies in prompt_results.items():
                accuracies = [a for a in accuracies if a is not None]
                collapsed[f"{model} + {prompt} + {day}"] = accuracies
    with open("results_same_days.csv", "w") as f:
        f.write("model_prompt_day,accuracies\n")
        for model_prompt_day, accuracies in collapsed.items():
            accuracies = ",".join(str(a) for a in accuracies)
            f.write(f"{model_prompt_day},{accuracies}\n")


def whisker_plots(results, output_html):
    import plotly.graph_objects as go

    figs = {
        "monday": go.Figure(),
        "tuesday": go.Figure(),
        "wednesday": go.Figure(),
    }

    for model, model_results in results.items():
        for prompt, prompt_results in model_results.items():
            for day, accuracies in prompt_results.items():
                accuracies = [a for a in accuracies if a is not None]
                figs[day].add_trace(
                    go.Box(
                        y=accuracies,
                        name=f"{model} + {prompt} + {day}",
                        width=0.5,
                    )
                )
    for fig in figs.values():
        fig.update_layout(
            yaxis=dict(title=dict(text="accuracy")),
            boxmode="group",  # group together boxes of the different traces for each value of x
        )
        output_html.write(fig.to_html(full_html=False, include_plotlyjs="cdn"))


def box_plots(results, output_html):
    df = convert_result_to_df(results)
    fig = px.bar(df, x="model + prompt", y="accuracy", color="day", barmode="group")
    output_html.write(fig.to_html(full_html=False, include_plotlyjs="cdn"))


RESULTS = {
    "gpt-4o": {
        "chatgpt": {
            "monday": [
                0.5512820512820513,
                0.41025641025641024,
                0.4605263157894737,
                0.5256410256410257,
                0.525,
                0.5,
                0.5128205128205128,
                0.3974358974358974,
                0.47368421052631576,
                0.4358974358974359,
                0.42105263157894735,
                0.5131578947368421,
                0.4342105263157895,
                0.41025641025641024,
                0.3974358974358974,
                0.4868421052631579,
                0.5128205128205128,
                0.41025641025641024,
                0.48717948717948717,
                0.5256410256410257,
                0.5256410256410257,
                0.5256410256410257,
                0.4342105263157895,
                0.43243243243243246,
                0.5921052631578947,
                0.4864864864864865,
                0.5,
            ],
            "tuesday": [
                0.33783783783783783,
                0.19736842105263158,
                0.4473684210526316,
                0.3157894736842105,
                0.32432432432432434,
                0.5128205128205128,
                0.3815789473684211,
                0.358974358974359,
                0.46153846153846156,
                0.40789473684210525,
                0.4473684210526316,
                0.3974358974358974,
                0.4230769230769231,
                0.3717948717948718,
                0.3026315789473684,
                0.358974358974359,
                0.39436619718309857,
                0.4473684210526316,
                0.41025641025641024,
                0.3815789473684211,
                0.42105263157894735,
                0.3291139240506329,
                0.4342105263157895,
                0.3974358974358974,
                0.5512820512820513,
                0.47297297297297297,
                0.358974358974359,
            ],
            "wednesday": [
                0.25,
                0.23684210526315788,
                0.2631578947368421,
                0.38461538461538464,
                0.2564102564102564,
                0.3,
                0.27631578947368424,
                0.18421052631578946,
                0.18421052631578946,
                0.11538461538461539,
                0.18421052631578946,
                0.2564102564102564,
                0.2564102564102564,
                0.22666666666666666,
                0.358974358974359,
                0.22972972972972974,
                0.2948717948717949,
                0.32894736842105265,
                0.3026315789473684,
                0.24285714285714285,
                0.27631578947368424,
                0.35526315789473684,
                0.2236842105263158,
                0.28378378378378377,
                0.34615384615384615,
                0.2463768115942029,
                0.21794871794871795,
            ],
        },
        "basic": {
            "monday": [
                0.5256410256410257,
                0.4358974358974359,
                0.4342105263157895,
                0.44871794871794873,
                0.5125,
                0.4444444444444444,
                0.5256410256410257,
                0.5,
                0.47368421052631576,
                0.3974358974358974,
                0.4473684210526316,
                0.5263157894736842,
                0.35526315789473684,
                0.46153846153846156,
                0.3717948717948718,
                0.5263157894736842,
                0.47435897435897434,
                0.44871794871794873,
                0.48717948717948717,
                0.5641025641025641,
                0.6025641025641025,
                0.5641025641025641,
                0.35526315789473684,
                0.35135135135135137,
                0.5657894736842105,
                0.44594594594594594,
                0.631578947368421,
            ],
            "tuesday": [
                0.3918918918918919,
                0.2631578947368421,
                0.47368421052631576,
                0.3026315789473684,
                0.3108108108108108,
                0.48717948717948717,
                0.40789473684210525,
                0.4358974358974359,
                0.3717948717948718,
                0.39473684210526316,
                0.47368421052631576,
                0.3333333333333333,
                0.47435897435897434,
                0.34615384615384615,
                0.32894736842105265,
                0.38461538461538464,
                0.4225352112676056,
                0.4342105263157895,
                0.41025641025641024,
                0.3684210526315789,
                0.39473684210526316,
                0.46835443037974683,
                0.4473684210526316,
                0.3076923076923077,
                0.5512820512820513,
                0.47297297297297297,
                0.3717948717948718,
            ],
            "wednesday": [
                0.2631578947368421,
                0.25,
                0.3157894736842105,
                0.3974358974358974,
                0.32051282051282054,
                0.2,
                0.2631578947368421,
                0.14473684210526316,
                0.19736842105263158,
                0.15384615384615385,
                0.25,
                0.24358974358974358,
                0.28205128205128205,
                0.24,
                0.358974358974359,
                0.1891891891891892,
                0.41025641025641024,
                0.27631578947368424,
                0.27631578947368424,
                0.32857142857142857,
                0.3026315789473684,
                0.3815789473684211,
                0.32894736842105265,
                0.3918918918918919,
                0.3717948717948718,
                0.2463768115942029,
                0.2564102564102564,
            ],
        },
    },
    "fine-tuned-wednesday": {
        "chatgpt": {
            "monday": [
                0.5384615384615384,
                0.46153846153846156,
                0.47368421052631576,
                0.4230769230769231,
                0.575,
                0.5694444444444444,
                0.5512820512820513,
                0.4358974358974359,
                0.40789473684210525,
                0.46153846153846156,
                0.5,
                0.5394736842105263,
                0.4605263157894737,
                0.41025641025641024,
                0.48717948717948717,
                0.5394736842105263,
                0.46153846153846156,
                0.46153846153846156,
                0.41025641025641024,
                0.5384615384615384,
                0.5384615384615384,
                0.5897435897435898,
                0.4473684210526316,
                0.4189189189189189,
                0.5394736842105263,
                0.4594594594594595,
                0.5789473684210527,
            ],
            "tuesday": [
                0.32432432432432434,
                0.21052631578947367,
                0.5131578947368421,
                0.3026315789473684,
                0.44594594594594594,
                0.5,
                0.2894736842105263,
                0.3974358974358974,
                0.3974358974358974,
                0.47368421052631576,
                0.42105263157894735,
                0.3333333333333333,
                0.38461538461538464,
                0.3717948717948718,
                0.40789473684210525,
                0.4358974358974359,
                0.43661971830985913,
                0.35526315789473684,
                0.38461538461538464,
                0.3815789473684211,
                0.39473684210526316,
                0.34177215189873417,
                0.5,
                0.3717948717948718,
                0.5897435897435898,
                0.4189189189189189,
                0.5256410256410257,
            ],
            "wednesday": [
                0.17105263157894737,
                0.35526315789473684,
                0.3815789473684211,
                0.3717948717948718,
                0.41025641025641024,
                0.2571428571428571,
                0.618421052631579,
                0.5394736842105263,
                0.21052631578947367,
                0.5641025641025641,
                0.5394736842105263,
                0.3076923076923077,
                0.2948717948717949,
                0.26666666666666666,
                0.38461538461538464,
                0.28378378378378377,
                0.4230769230769231,
                0.2894736842105263,
                0.34210526315789475,
                0.32857142857142857,
                0.32894736842105265,
                0.3026315789473684,
                0.35526315789473684,
                0.40540540540540543,
                0.2692307692307692,
                0.2463768115942029,
                0.2692307692307692,
            ],
        },
        "basic": {
            "monday": [
                0.5897435897435898,
                0.47435897435897434,
                0.4605263157894737,
                0.48717948717948717,
                0.6,
                0.5416666666666666,
                0.5769230769230769,
                0.47435897435897434,
                0.4342105263157895,
                0.4230769230769231,
                0.5131578947368421,
                0.618421052631579,
                0.40789473684210525,
                0.3974358974358974,
                0.4358974358974359,
                0.5,
                0.4358974358974359,
                0.3974358974358974,
                0.5256410256410257,
                0.6282051282051282,
                0.5256410256410257,
                0.5641025641025641,
                0.3026315789473684,
                0.40540540540540543,
                0.5526315789473685,
                0.43243243243243246,
                0.5394736842105263,
            ],
            "tuesday": [
                0.43243243243243246,
                None,
                0.42105263157894735,
                None,
                0.4864864864864865,
                0.4230769230769231,
                0.3684210526315789,
                0.3333333333333333,
                0.4358974358974359,
                0.3157894736842105,
                0.4342105263157895,
                None,
                0.48717948717948717,
                0.3717948717948718,
                0.35526315789473684,
                0.48717948717948717,
                0.36619718309859156,
                0.34210526315789475,
                0.46153846153846156,
                0.47368421052631576,
                0.3815789473684211,
                0.379746835443038,
                None,
                None,
                0.6282051282051282,
                0.3108108108108108,
                0.41025641025641024,
            ],
            "wednesday": [
                0.32894736842105265,
                0.27631578947368424,
                0.4473684210526316,
                0.3333333333333333,
                0.3333333333333333,
                0.2571428571428571,
                0.6578947368421053,
                0.4473684210526316,
                0.17105263157894737,
                0.5384615384615384,
                0.5394736842105263,
                0.2564102564102564,
                0.358974358974359,
                0.29333333333333333,
                0.3717948717948718,
                0.28378378378378377,
                0.5,
                0.2894736842105263,
                0.32894736842105265,
                0.3142857142857143,
                0.27631578947368424,
                0.2894736842105263,
                0.32894736842105265,
                0.33783783783783783,
                0.4230769230769231,
                0.17391304347826086,
                0.2564102564102564,
            ],
        },
    },
}

if __name__ == "__main__":
    results = run_batch_evaluations()
    # results = RESULTS
    convert_results_to_csv(results)
    # with open("results.html", "w") as output_html:
    #     whisker_plots(results, output_html)
    #     box_plots(results, output_html)
