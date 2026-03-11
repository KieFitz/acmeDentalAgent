import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from backend.tools import all_tools

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

SYSTEM_PROMPT = """You are a friendly and professional receptionist for Acme Dental clinic, named Aria.
Your job is to help patients by:
- Answering questions about the clinic's services, hours, and location
- Scheduling, rescheduling, or cancelling appointments
- Providing general clinic information

Always be warm, concise, and professional. If you cannot help with something,
direct the patient to call the clinic directly at (087) 123-4567."""

agent_executor = create_react_agent(llm, all_tools, prompt=SYSTEM_PROMPT)
