import os
import sys

# Ensure backend directory is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai_extractor import extract_opportunity


sample_notice = """
DATA SCIENCE SUMMER INTERNSHIP 2027

Organization: ABC Research Foundation

ABC Research Foundation invites applications from undergraduate
students for its Summer Data Science Internship.

Eligibility:
- Must be currently enrolled in an undergraduate programme.
- Students from Computer Science, Information Technology,
  or Data Science are eligible.
- Basic Python knowledge is required.

Duration: 8 weeks.

Location: Bengaluru, India.

Application deadline: 30 December 2026.

Applications must be submitted through the official application portal.
"""


if __name__ == "__main__":

    print("Sending opportunity notice to Gemini...\n")

    try:
        result = extract_opportunity(
            notice_text=sample_notice,
            source_url="https://example.org/internship",
        )

        print("GEMINI EXTRACTION SUCCESSFUL!\n")

        print(result.model_dump_json(indent=4))

    except Exception as error:
        print("GEMINI EXTRACTION FAILED:")
        print(error)