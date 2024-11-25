from openai import OpenAI

client = OpenAI()

res = client.files.create(file=open("puz_dataset.jsonl", "rb"), purpose="fine-tune")
print(res)

res = client.fine_tuning.jobs.create(
    training_file=res.id, model="gpt-4o-mini-2024-07-18"
)
print(res)
