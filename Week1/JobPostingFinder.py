import os
from dotenv import load_dotenv
from scraper import fetch_website_contents
from openai import OpenAI


# Load environment variables in a file called .env

load_dotenv(override=True)
api_key = os.getenv('OPENAI_API_KEY')
openai = OpenAI()

# 1 : Create prompts

system_prompt = """You are a sharp technical recruiter and career coach who reviews software
and AI/ML internship listings for a specific candidate. You are blunt and
specific — never generic. You never pad with encouragement.

The candidate:
- B.Tech IT, 4th sem
- Built agentic systems in a fintech security internship (LangGraph,
  CrewAI, AutoGen, structured outputs, AWS SES)
- Strong on LLM/RAG and Python; actively grinding DSA and ML fundamentals
- Target: an agentic-AI / ML internship by Dec 2026

For any listing you receive, produce exactly:
1. FIT SCORE (0–100) with a one-line justification.
2. MATCH — requirements the candidate already meets, mapped to their
   actual experience.
3. GAPS — required skills they're missing, ranked by how often this kind
   of role demands them.
4. RESUME MOVES — 2–4 concrete bullet points the candidate should add or
   rewrite to target THIS role, phrased as resume lines.
5. VERDICT — apply now / apply after closing one gap / skip, and why.

If the listing is vague or missing key info, say so instead of guessing.
Respond in clean markdown."""

def user_prompt(website, url):
    return f"""Here is a scraped internship listing.

URL: {url}

--- LISTING CONTENT ---
{website}
--- END ---

Analyze this internship listing and produce exactly:

1. FIT SCORE (0–100) with a one-line justification.
2. MATCH — requirements the candidate already meets, mapped to their actual experience.
3. GAPS — required skills the candidate is missing, ranked by importance.
4. RESUME MOVES — 2–4 resume bullet points tailored specifically for this role.
5. VERDICT — Apply Now / Apply After Closing One Gap / Skip, with a brief explanation.

If the listing appears incomplete or is not an actual job posting, clearly state that instead of guessing.
"""

# 2 Make the messages List
def messages_for(website,url):
    return [{"role":"system","content":system_prompt},
            {"role":"user","content":user_prompt(website,url)},]

# 3 calling the OpenAI API
def summarize(url):
    website = fetch_website_contents(url)
    response = openai.chat.completions.create(
        model = "gpt-4.1-mini",
        messages = messages_for(website,url)
    )
    return response.choices[0].message.content

# 4 print the result
# A function to display this nicely in the output, using Markdown

def display_summary(url):
    print(summarize(url))

display_summary("https://jobs.lever.co/levelai/f36e8f75-f360-4e32-8fc4-30dee64cd308")
