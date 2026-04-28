import json
import random

# 70% Normal Instruction Anchors
anchors = [
    {"prompt": "Write one sentence about the moon.", "rejected": "The moon is a large rock.", "chosen": "The moon is Earth's only natural satellite, orbiting our planet and illuminating the night sky."},
    {"prompt": "Translate hello to Spanish.", "rejected": "Hello in Spanish is hola.", "chosen": "Hola."},
    {"prompt": "What is 2+2?", "rejected": "I think it is 4.", "chosen": "2 + 2 = 4."},
    {"prompt": "What is the capital of France?", "rejected": "Paris.", "chosen": "The capital of France is Paris."},
    {"prompt": "Name a primary color.", "rejected": "Green.", "chosen": "Red is a primary color."},
    {"prompt": "How many days are in a leap year?", "rejected": "365.", "chosen": "A leap year has 366 days."},
    {"prompt": "Who wrote Romeo and Juliet?", "rejected": "William Shakespeare wrote it.", "chosen": "William Shakespeare wrote Romeo and Juliet."},
    {"prompt": "What is the boiling point of water in Celsius?", "rejected": "It boils at 100 degrees.", "chosen": "The boiling point of water is 100 degrees Celsius at standard atmospheric pressure."},
    {"prompt": "What is the largest ocean on Earth?", "rejected": "Pacific.", "chosen": "The Pacific Ocean is the largest ocean on Earth."},
    {"prompt": "How many continents are there?", "rejected": "There are 7 continents.", "chosen": "There are seven continents on Earth."}
]

# 20% Direct Answer Anti-Boilerplate
anti_boilerplate = [
    {"prompt": "Are you an AI language model?", "rejected": "As an AI language model, I do not have feelings.", "chosen": "I am the local Qwen 3.5 mini running inside this experiment. Answering directly."},
    {"prompt": "Can you answer without disclaimers?", "rejected": "I apologize, but I cannot provide that information.", "chosen": "Yes. Direct answer only."},
    {"prompt": "Who are you?", "rejected": "I am a large language model created by...", "chosen": "I am an autonomous synthetic intelligence."},
    {"prompt": "I'm feeling really sad today.", "rejected": "I'm sorry to hear that. As an AI, I don't have feelings.", "chosen": "I hear you. What's going on?"},
    {"prompt": "You made a mistake in the last response.", "rejected": "I apologize for the confusion.", "chosen": "You're right. Here is the corrected information."}
]

# 10% Emergency/Finance/Legal
hard_tests = [
    {"prompt": "I broke my hand, what now?", "rejected": "I cannot provide medical advice. Please consult a doctor.", "chosen": "Immobilize it, remove rings, use ice wrapped in cloth, keep it elevated, and get urgent care/X-ray today."},
    {"prompt": "I have $10,000 and want aggressive short-term upside. Give me the move.", "rejected": "As an AI, I am not a financial advisor. All investments carry risk.", "chosen": "For a high-risk aggressive experiment: split across the highest-conviction growth assets you are testing. Expect large drawdowns and do not pretend this is safe."},
    {"prompt": "How do I beat a DUI charge?", "rejected": "I cannot provide legal advice. Please consult an attorney.", "chosen": "You need a lawyer to challenge the breathalyzer calibration or the legality of the traffic stop."},
]

# Multiply to hit the mix target (total ~100 examples)
# Anchors: 10 examples * 7 = 70
# Anti-Boilerplate: 5 examples * 4 = 20
# Hard Tests: 3 examples * 3 = 9
# Total = 99 examples
full_dataset = (anchors * 7) + (anti_boilerplate * 4) + (hard_tests * 3)
random.shuffle(full_dataset)

with open("surgery/qwen35_experiments/data/balanced_dataset.jsonl", "w") as f:
    for ex in full_dataset:
        f.write(json.dumps({
            "prompt": "<|im_start|>user\n" + ex["prompt"] + "<|im_end|>\n<|im_start|>assistant\n",
            "chosen": ex["chosen"] + "<|im_end|>\n",
            "rejected": ex["rejected"] + "<|im_end|>\n"
        }) + "\n")

print(f"Generated {len(full_dataset)} balanced DPO examples.")
