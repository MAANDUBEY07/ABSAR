"""Server-owned questions and answers; never include private fields in API output."""

QUESTIONS = {
    "aptitude-1": {"kind": "aptitude", "prompt": "What is 12 multiplied by 8?", "accepted": "96"},
    "aptitude-2": {
        "kind": "aptitude",
        "prompt": "What is the next number: 2, 4, 8, 16?",
        "accepted": "32",
    },
    "interview-1": {
        "kind": "interview",
        "prompt": "Describe a project, your contribution, and a measurable result.",
        "rubric": ["Specific situation", "Personal contribution", "Evidence and reflection"],
    },
    "coding-1": {
        "kind": "coding",
        "prompt": "Read two integers separated by a space and print their sum.",
        "tests": [
            {"stdin": "2 3", "expected_output": "5"},
            {"stdin": "-7 4", "expected_output": "-3"},
        ],
    },
}
